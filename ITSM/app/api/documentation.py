"""Documentation API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List
import logging
import os
from datetime import datetime

from app.db import get_db
from app.models.documentation import ProblemResolution, GeneralDocument, DocumentAttachment
from app.schemas.documentation import (
    ProblemResolutionCreate, ProblemResolutionResponse,
    GeneralDocumentCreate, GeneralDocumentResponse,
    DocumentAttachmentResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documentation", tags=["documentation"])

# Upload directory
UPLOAD_DIR = "uploads/documentation"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============ PROBLEM RESOLUTIONS ============

@router.get("/problems", response_model=List[ProblemResolutionResponse])
async def list_problem_resolutions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: str = Query(None),
    severity: str = Query(None),
    db: Session = Depends(get_db),
):
    """List all problem resolutions"""
    query = db.query(ProblemResolution).filter(ProblemResolution.is_active == True)

    if category:
        query = query.filter(ProblemResolution.problem_category == category)
    if severity:
        query = query.filter(ProblemResolution.severity == severity)

    resolutions = query.order_by(ProblemResolution.created_at.desc()).offset(skip).limit(limit).all()
    return resolutions


@router.get("/problems/{problem_id}", response_model=ProblemResolutionResponse)
async def get_problem_resolution(
    problem_id: int,
    db: Session = Depends(get_db),
):
    """Get specific problem resolution"""
    resolution = db.query(ProblemResolution).filter(
        ProblemResolution.id == problem_id,
        ProblemResolution.is_active == True
    ).first()
    if not resolution:
        raise HTTPException(status_code=404, detail="Problem resolution not found")
    return resolution


@router.post("/problems", response_model=ProblemResolutionResponse, status_code=201)
async def create_problem_resolution(
    problem: ProblemResolutionCreate,
    db: Session = Depends(get_db),
):
    """Create new problem resolution"""
    try:
        resolution = ProblemResolution(**problem.model_dump())
        db.add(resolution)
        db.commit()
        db.refresh(resolution)

        logger.info(f"Problem resolution created: {resolution.title}")
        return resolution

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating problem resolution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/problems/{problem_id}", response_model=ProblemResolutionResponse)
async def update_problem_resolution(
    problem_id: int,
    problem_update: ProblemResolutionCreate,
    db: Session = Depends(get_db),
):
    """Update problem resolution"""
    try:
        resolution = db.query(ProblemResolution).filter(ProblemResolution.id == problem_id).first()
        if not resolution:
            raise HTTPException(status_code=404, detail="Problem resolution not found")

        for field, value in problem_update.model_dump(exclude_unset=True).items():
            setattr(resolution, field, value)

        db.commit()
        db.refresh(resolution)

        logger.info(f"Problem resolution updated: {resolution.title}")
        return resolution

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating problem resolution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/problems/{problem_id}", status_code=204)
async def delete_problem_resolution(
    problem_id: int,
    db: Session = Depends(get_db),
):
    """Delete problem resolution"""
    try:
        resolution = db.query(ProblemResolution).filter(ProblemResolution.id == problem_id).first()
        if not resolution:
            raise HTTPException(status_code=404, detail="Problem resolution not found")

        resolution.is_active = False
        db.commit()

        logger.info(f"Problem resolution deleted: {resolution.title}")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting problem resolution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ GENERAL DOCUMENTS ============

@router.get("/documents", response_model=List[GeneralDocumentResponse])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    document_type: str = Query(None),
    category: str = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
):
    """List all documents"""
    query = db.query(GeneralDocument).filter(GeneralDocument.is_active == True)

    if document_type:
        query = query.filter(GeneralDocument.document_type == document_type)
    if category:
        query = query.filter(GeneralDocument.category == category)
    if status:
        query = query.filter(GeneralDocument.status == status)

    documents = query.order_by(GeneralDocument.created_at.desc()).offset(skip).limit(limit).all()
    return documents


@router.get("/documents/{document_id}", response_model=GeneralDocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """Get specific document"""
    document = db.query(GeneralDocument).filter(
        GeneralDocument.id == document_id,
        GeneralDocument.is_active == True
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post("/documents", response_model=GeneralDocumentResponse, status_code=201)
async def create_document(
    doc: GeneralDocumentCreate,
    db: Session = Depends(get_db),
):
    """Create new document"""
    try:
        document = GeneralDocument(**doc.model_dump())
        db.add(document)
        db.commit()
        db.refresh(document)

        logger.info(f"Document created: {document.title}")
        return document

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/documents/{document_id}", response_model=GeneralDocumentResponse)
async def update_document(
    document_id: int,
    doc_update: GeneralDocumentCreate,
    db: Session = Depends(get_db),
):
    """Update document"""
    try:
        document = db.query(GeneralDocument).filter(GeneralDocument.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        for field, value in doc_update.model_dump(exclude_unset=True).items():
            setattr(document, field, value)

        db.commit()
        db.refresh(document)

        logger.info(f"Document updated: {document.title}")
        return document

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """Delete document"""
    try:
        document = db.query(GeneralDocument).filter(GeneralDocument.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        document.is_active = False
        db.commit()

        logger.info(f"Document deleted: {document.title}")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ FILE UPLOADS ============

@router.post("/problems/{problem_id}/upload", response_model=DocumentAttachmentResponse, status_code=201)
async def upload_problem_attachment(
    problem_id: int,
    file: UploadFile = File(...),
    description: str = Query(None),
    db: Session = Depends(get_db),
):
    """Upload attachment for problem resolution"""
    try:
        # Verify problem exists
        problem = db.query(ProblemResolution).filter(ProblemResolution.id == problem_id).first()
        if not problem:
            raise HTTPException(status_code=404, detail="Problem resolution not found")

        # Save file
        file_path = os.path.join(UPLOAD_DIR, f"problem_{problem_id}_{file.filename}")
        with open(file_path, "wb") as buffer:
            contents = await file.read()
            buffer.write(contents)

        # Create attachment record
        attachment = DocumentAttachment(
            problem_resolution_id=problem_id,
            filename=file.filename,
            file_path=file_path,
            file_type=file.content_type or "unknown",
            file_size=len(contents),
            description=description,
            uploaded_by=1  # TODO: Get from current user
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)

        logger.info(f"File uploaded for problem {problem_id}: {file.filename}")
        return attachment

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{document_id}/upload", response_model=DocumentAttachmentResponse, status_code=201)
async def upload_document_attachment(
    document_id: int,
    file: UploadFile = File(...),
    description: str = Query(None),
    db: Session = Depends(get_db),
):
    """Upload attachment for document"""
    try:
        # Verify document exists
        document = db.query(GeneralDocument).filter(GeneralDocument.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Save file
        file_path = os.path.join(UPLOAD_DIR, f"doc_{document_id}_{file.filename}")
        with open(file_path, "wb") as buffer:
            contents = await file.read()
            buffer.write(contents)

        # Create attachment record
        attachment = DocumentAttachment(
            documentation_id=document_id,
            filename=file.filename,
            file_path=file_path,
            file_type=file.content_type or "unknown",
            file_size=len(contents),
            description=description,
            uploaded_by=1  # TODO: Get from current user
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)

        logger.info(f"File uploaded for document {document_id}: {file.filename}")
        return attachment

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
