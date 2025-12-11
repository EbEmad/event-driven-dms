from pg.schemes import DocumentCreate, DocumentResponse, DocumentUpdate
from pg.models import Document,DocumentStatus
from pg.database import get_db,engine,Base
from pg.config import get_settings
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from uuid_extensions import uuid7
from contextlib import asynccontextmanager
import asyncio
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app:FastAPI):
    logger.info(f"{settings.service_name} starting...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"{settings.service_name} started - HTTP: 8000")
    yield

    logger.info(f"{settings.service_name} shutting down...")
    await engine.dispose()
app=FastAPI(title="Document Service",version="1.0.0",lifespan=lifespan)



@app.get("/health/live")
async def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness(db:AsyncSession=Depends(get_db)):
    try:
        await db.execute(select(1))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service is not ready")

@app.post("/documents",response_model=DocumentResponse,status_code=201)
async def create_document(document:DocumentCreate,db: AsyncSession = Depends(get_db)):
    """Create document with async pg upload."""

    document_id=uuid7()
    content_bytes = document.content.encode("utf-8")
    s3_key=""

    db_document=Document(
        id=document_id,
        title=document.title,
        content_type=document.content_type,
        content_size=len(content_bytes),
        s3_key=s3_key,
        created_by=document.created_by,
        status=DocumentStatus.CREATED.value,
    )

    db.add(db_document)
    await db.commit()
    await db.refresh(db_document)
    logger.info(f"Document created: {document_id}")
    return db_document
