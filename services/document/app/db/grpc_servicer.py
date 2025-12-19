import logging

import grpc
from sqlalchemy import select

from . import document_service_pb2, document_service_pb2_grpc
from .database import AsyncSessionLocal
from .models import Document

logger = logging.getLogger(__name__)


class DocumentServicer(document_service_pb2_grpc.DocumentServiceServicer):
    """gRPC servicer for Document Service.

    Implements the DocumentService defined in document_service.proto
    """

    async def UpdateDocumentStatus(
        self,
        request: document_service_pb2.UpdateDocumentStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> document_service_pb2.DocumentResponse:
        """Update document status via gRPC.

        This replaces the HTTP PATCH endpoint for inter-service communication
        """
        try:
            logger.info(
                f"gRPC: UpdateDocumentStatus called - "
                f"document_id={request.document_id}, status={request.status}"
            )

            async with AsyncSessionLocal() as db:
                # Get document
                result = await db.execute(
                    select(Document).where(Document.id == request.document_id)
                )
                document = result.scalar_one_or_none()

                if not document:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Document {request.document_id} not found")
                    return document_service_pb2.DocumentResponse()

                # Update status
                document.status = request.status
                document.version += 1

                await db.commit()
                await db.refresh(document)

                logger.info(
                    f"Document {document.id} status updated to '{document.status}' "
                    f"via gRPC (version {document.version})"
                )

                # Return response
                return self._document_to_proto(document)

        except Exception as e:
            logger.error(f"✗ gRPC error in UpdateDocumentStatus: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return document_service_pb2.DocumentResponse()

    async def GetDocument(
        self,
        request: document_service_pb2.GetDocumentRequest,
        context: grpc.aio.ServicerContext,
    ) -> document_service_pb2.DocumentResponse:
        """Get document by ID via gRPC."""
        try:
            logger.info(f"gRPC: GetDocument called - document_id={request.document_id}")

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Document).where(Document.id == request.document_id)
                )
                document = result.scalar_one_or_none()

                if not document:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Document {request.document_id} not found")
                    return document_service_pb2.DocumentResponse()

                return self._document_to_proto(document)

        except Exception as e:
            logger.error(f"✗ gRPC error in GetDocument: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return document_service_pb2.DocumentResponse()

    async def DocumentExists(
        self,
        request: document_service_pb2.DocumentExistsRequest,
        context: grpc.aio.ServicerContext,
    ) -> document_service_pb2.DocumentExistsResponse:
        """Check if document exists via gRPC."""
        try:
            logger.info(
                f"gRPC: DocumentExists called - document_id={request.document_id}"
            )

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Document.status).where(Document.id == request.document_id)
                )
                status = result.scalar_one_or_none()

                return document_service_pb2.DocumentExistsResponse(
                    exists=status is not None, status=status or ""
                )

        except Exception as e:
            logger.error(f"✗ gRPC error in DocumentExists: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return document_service_pb2.DocumentExistsResponse(exists=False)

    def _document_to_proto(
        self, document: Document
    ) -> document_service_pb2.DocumentResponse:
        """Convert SQLAlchemy model to protobuf message."""
        return document_service_pb2.DocumentResponse(
            id=str(document.id),
            title=document.title,
            status=document.status,
            created_by=document.created_by,
            content_type=document.content_type or "",
            content_size=document.content_size or 0,
            s3_key=document.s3_key or "",
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
            version=document.version,
        )