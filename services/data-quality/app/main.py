import asyncio
import logging
from typing import Any

import aioboto3
from quixstreams import Application
from .config import get_settings
from llm.LLMProviderFactory import LLMProviderFactory

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings=get_settings()



class DataQualityProcessor:
    """Process CDC events and validate document quality using LLM."""
    
    def __init__(self):
        self.app = Application(
            broker_address=settings.kafka_bootstrap_servers,
            consumer_group=settings.kafka_consumer_group,
            auto_offset_reset="earliest",
        )
        self.llm_provider_factory = LLMProviderFactory(settings)
        self.llm_provider = self.llm_provider_factory.create_llm_provider(settings.llm_provider)
        self.s3_session = aioboto3.Session()
        logger.info(f"Data Quality Processor initialized with {settings.llm_provider} provider")
    
    async def fetch_document_content(self, s3_key: str) -> str:
        """Fetch document content from MinIO."""
        try:
            async with self.s3_session.client(
                's3',
                endpoint_url=f"http://{settings.minio_endpoint}",
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                use_ssl=settings.minio_secure
            ) as s3_client:
                response = await s3_client.get_object(
                    Bucket=settings.minio_bucket_documents,
                    Key=s3_key
                )
                async with response['Body'] as stream:
                    content_bytes = await stream.read()
                    return content_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to fetch document from MinIO: {e}")
            return ""
    
    async def process_document_event(
        self,
        value: dict[str, Any],
        key: Any,
        timestamp: int,
        headers: list[tuple[str, bytes]] | None,
    ) -> dict[str, Any] | None:
        """Process a CDC event and add quality validation."""
        try:
            op = value.get("op")
            
            # Only process creates and updates, skip snapshots and deletes
            if op in ["r", "d"]:
                logger.debug(f"Skipping operation: {op}")
                return None
            
            after = value.get('after', {})
            document_id = after.get("id")
            s3_key = after.get("s3_key")
            
            # Skip if no content yet
            if not s3_key:
                logger.warning(f"Document {document_id} has no S3 key, skipping")
                return None
            
            title = after.get("title", "")
            
            # Fetch content from MinIO
            logger.info(f"Fetching content for document {document_id}")
            content = await self.fetch_document_content(s3_key)
            
            if not content:
                logger.warning(f"No content found for document {document_id}")
                # Still publish event but with low quality score
                return self._create_no_content_event(after)
            
            # Validate with LLM
            logger.info(f"Validating document {document_id} with {settings.llm_provider}")
            quality_result = await self.llm_provider.validate_document(
                title=title,
                content=content,
                document_id=str(document_id)
            )
            
            # Check if we should block low-quality documents
            if settings.block_low_quality and not quality_result.is_valid:
                logger.warning(
                    f"Blocking low-quality document {document_id} "
                    f"(score: {quality_result.overall_score:.2f})"
                )
                return None
            
            # Enrich the event with quality metadata
            enriched_event = {
                "id": str(document_id),
                "title": title,
                "status": after.get("status", "created"),
                "created_by": after.get("created_by", ""),
                "content_type": after.get("content_type"),
                "content_size": after.get("content_size", 0),
                "created_at": after.get("created_at"),
                "updated_at": after.get("updated_at"),
                "version": after.get("version", 1),
                "s3_key": s3_key,
                
                # Quality metadata
                "quality_score": quality_result.overall_score,
                "quality_is_valid": quality_result.is_valid,
                "quality_issues": [
                    {
                        "type": issue.issue_type,
                        "severity": issue.severity,
                        "description": issue.description,
                        "field": issue.field
                    }
                    for issue in quality_result.all_issues
                ],
                "has_pii": quality_result.has_pii,
                "quality_checks": {
                    "completeness": quality_result.completeness_check.score,
                    "consistency": quality_result.consistency_check.score,
                    "pii_detection": quality_result.pii_check.score,
                    "language_quality": quality_result.language_check.score,
                },
                "quality_checked_at": quality_result.checked_at.isoformat(),
                "quality_provider": quality_result.llm_provider,
                "quality_model": quality_result.llm_model,
            }
            
            logger.info(
                f"Document {document_id} validated - "
                f"Score: {quality_result.overall_score:.2f}, "
                f"Valid: {quality_result.is_valid}, "
                f"Issues: {len(quality_result.all_issues)}"
            )
            
            return enriched_event
            
        except Exception as e:
            logger.error(f"Error processing document event: {e}", exc_info=True)
            return None
    
    def _create_no_content_event(self, after: dict) -> dict:
        """Create event for document with no content."""
        return {
            "id": str(after.get("id")),
            "title": after.get("title", ""),
            "status": after.get("status", "created"),
            "created_by": after.get("created_by", ""),
            "content_type": after.get("content_type"),
            "content_size": after.get("content_size", 0),
            "created_at": after.get("created_at"),
            "updated_at": after.get("updated_at"),
            "version": after.get("version", 1),
            "s3_key": after.get("s3_key"),
            "quality_score": 0,
            "quality_is_valid": False,
            "quality_issues": [{
                "type": "completeness",
                "severity": "high",
                "description": "No content available",
                "field": "content"
            }],
            "has_pii": False,
            "quality_checks": {
                "completeness": 0,
                "consistency": 0,
                "pii_detection": 100,
                "language_quality": 0,
            },
        }
    
    def start(self):
        """Start the data quality processor."""
        logger.info(f"{settings.service_name} starting...")
        
        try:
            # Input topic: CDC events
            input_topic = self.app.topic(
                settings.cdc_documents_topic,
                value_deserializer="json"
            )
            
            # Output topic: Quality-checked events
            output_topic = self.app.topic(
                settings.quality_checks_topic,
                value_serializer="json"
            )
            
            # Create streaming dataframe
            sdf = self.app.dataframe(input_topic)
            
            # Apply quality validation
            sdf = sdf.apply(self.process_document_event, metadata=True)
            
            # Filter out None values (skipped documents)
            sdf = sdf.filter(lambda v: v is not None)
            
            # Publish to output topic
            sdf.to_topic(output_topic)
            
            logger.info(
                f"Processing: {settings.cdc_documents_topic} -> "
                f"{settings.quality_checks_topic}"
            )
            logger.info(f"LLM Provider: {settings.llm_provider}")
            logger.info(f"Min Quality Score: {settings.min_quality_score}")
            logger.info(f"Block Low Quality: {settings.block_low_quality}")
            
            # Run the application
            self.app.run()
            
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise


def main():
    """Main entry point."""
    processor = DataQualityProcessor()
    processor.start()


if __name__ == "__main__":
    main()
