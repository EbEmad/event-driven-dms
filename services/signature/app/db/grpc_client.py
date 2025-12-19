import logging

import grpc

from . import document_service_pb2, document_service_pb2_grpc
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentServiceClient:
    """gRPC client for Document Service.

    Replaces HTTP calls with high-performance gRPC calls
    """

    def __init__(self):
        self.channel: grpc.aio.Channel | None = None
        self.stub: document_service_pb2_grpc.DocumentServiceStub | None = None

    async def connect(self):
        """Initialize gRPC channel."""
        try:
            # Create async channel
            self.channel = grpc.aio.insecure_channel(
                "document-service:50051",
                options=[
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 10000),
                    ("grpc.keepalive_permit_without_calls", True),
                    ("grpc.http2.max_pings_without_data", 0),
                ],
            )

            # Create stub
            self.stub = document_service_pb2_grpc.DocumentServiceStub(self.channel)

            logger.info("gRPC client connected to document-service:50051")

        except Exception as e:
            logger.error(f"✗ gRPC client connection failed: {e}")
            raise

    async def disconnect(self):
        """Close gRPC channel."""
        if self.channel:
            await self.channel.close()
            logger.info("gRPC client disconnected")

    async def update_document_status(
        self, document_id: str, status: str, timeout: float = 5.0
    ) -> document_service_pb2.DocumentResponse | None:
        """Update document status via gRPC."""
        try:
            request = document_service_pb2.UpdateDocumentStatusRequest(
                document_id=document_id, status=status
            )

            logger.info(
                f"gRPC: Calling UpdateDocumentStatus - {document_id} -> {status}"
            )

            response = await self.stub.UpdateDocumentStatus(request, timeout=timeout)

            logger.info(
                f"gRPC: Document {response.id} updated to '{response.status}' "
                f"(version {response.version})"
            )

            return response

        except grpc.RpcError as e:
            logger.error(f"✗ gRPC error: {e.code()} - {e.details()}")
            return None
        except Exception as e:
            logger.error(f"✗ Unexpected error in gRPC call: {e}")
            return None

    async def get_document(
        self, document_id: str, timeout: float = 5.0
    ) -> document_service_pb2.DocumentResponse | None:
        """Get document by ID via gRPC."""
        try:
            request = document_service_pb2.GetDocumentRequest(document_id=document_id)

            response = await self.stub.GetDocument(request, timeout=timeout)

            logger.info(f"gRPC: Retrieved document {response.id}")
            return response

        except grpc.RpcError as e:
            logger.error(f"✗ gRPC error: {e.code()} - {e.details()}")
            return None
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}")
            return None

    async def document_exists(self, document_id: str, timeout: float = 5.0) -> bool:
        """Check if document exists via gRPC."""
        try:
            request = document_service_pb2.DocumentExistsRequest(
                document_id=document_id
            )

            response = await self.stub.DocumentExists(request, timeout=timeout)

            logger.info(
                f"gRPC: Document {document_id} exists={response.exists} "
                f"status={response.status}"
            )

            return response.exists

        except grpc.RpcError as e:
            logger.error(f"✗ gRPC error: {e.code()} - {e.details()}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}")
            return False


grpc_client = DocumentServiceClient()