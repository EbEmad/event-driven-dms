import logging
import signal
from typing import Any

from quixstreams import Application
from quixstreams.sinks.base.item import SinkItem
from quixstreams.sinks.community.elasticsearch import ElasticsearchSink

from .config import get_settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


class EventProcessor:
    """CDC event processor with Elasticsearch indexing."""


    def __init__(self):
        self.app=Application(
            broker_address=settings.KAFKA_BOOTSTRAP_SERVERS,
            consumer_group=settings.KAFKA_CONSUMER_GROUP,
            auto_offset_reset="earliest",
        )

    def _transform_for_elasticsearch(
        self,
        value: dict[str, Any],
        key: Any,
        timestamp: int,
        headers: list[tuple[str, bytes]] | None,
    )->dict[str,Any] | None:
        """Transform CDC event to Elasticsearch document."""
        try:
            op=value.get("op")
            # Skip snapshots and deletes
            if op in ["r","d"]:
                return None
            
            # Document is already enriched with quality metadata from data-quality service
            # Just pass it through to Elasticsearch
            return {
                "id": str(value.get("id")),
                "title": value.get("title", ""),
                "status": value.get("status", "created"),
                "created_by": value.get("created_by", ""),
                "content_type": value.get("content_type"),
                "content_size": value.get("content_size", 0),
                "created_at": value.get("created_at"),
                "updated_at": value.get("updated_at"),
                "version": value.get("version", 1),
                
                # Quality metadata from data-quality service
                "quality_score": value.get("quality_score", 0),
                "quality_is_valid": value.get("quality_is_valid", False),
                "quality_issues": value.get("quality_issues", []),
                "has_pii": value.get("has_pii", False),
                "quality_checks": value.get("quality_checks", {}),
            }

        except Exception as e:
            logger.error(f"Failed to transform event: {e}")
            return None
    def start(self):
        logger.info(f"{settings.SERVICE_NAME} starting...")

        try:
            # Document ID extractor for ES
            def get_document_id(item:SinkItem)->str:
                return str(item.value.get("id"))
            
            es_sink = ElasticsearchSink(
                url=settings.ELASTICSEARCH_URL,
                index=settings.ELASTICSEARCH_INDEX_DOCUMENTS,
                document_id_setter=get_document_id,
                batch_size=50,
                mapping={
                    "mappings": {
                        "properties": {
                            "id": {"type": "keyword"},
                            "title": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword"}},
                            },
                            "status": {"type": "keyword"},
                            "created_by": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword"}},
                            },
                            "content_type": {"type": "keyword"},
                            "content_size": {"type": "long"},
                            "created_at": {
                                "type": "date",
                                "format": "strict_date_optional_time||epoch_millis",
                            },
                            "updated_at": {
                                "type": "date",
                                "format": "strict_date_optional_time||epoch_millis",
                            },
                            "version": {"type": "integer"},
                            
                            # Quality metadata fields
                            "quality_score": {"type": "float"},
                            "quality_is_valid": {"type": "boolean"},
                            "has_pii": {"type": "boolean"},
                            "quality_issues": {
                                "type": "nested",
                                "properties": {
                                    "type": {"type": "keyword"},
                                    "severity": {"type": "keyword"},
                                    "description": {"type": "text"},
                                    "field": {"type": "keyword"},
                                }
                            },
                            "quality_checks": {
                                "properties": {
                                    "completeness": {"type": "float"},
                                    "consistency": {"type": "float"},
                                    "pii_detection": {"type": "float"},
                                    "language_quality": {"type": "float"},
                                }
                            },
                        }
                    }
                },
            )

            # Documents topic - now consuming quality-checked events from settings
            topic = self.app.topic(settings.CDC_DOCUMENTS_TOPIC, value_deserializer="json")

            sdf = self.app.dataframe(topic)
            sdf = sdf.apply(self._transform_for_elasticsearch, metadata=True)
            sdf = sdf.filter(lambda v: v is not None)
            sdf.sink(es_sink)

            logger.info(f"Processing: {settings.CDC_DOCUMENTS_TOPIC} -> Elasticsearch")

            self.app.run()
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise



def main():
    EventProcessor().start()


if __name__ == "__main__":
    main()
