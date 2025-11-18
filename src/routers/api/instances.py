from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from src.database import get_db
from src.models import Instance, Problem

router = APIRouter()


class InstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    problem_id: int
    filename: str
    content_type: str | None
    file_size: int
    uploaded_at: datetime


@router.get("/problems/{problem_id}/instances", response_model=list[InstanceResponse])
def get_instances(problem_id: int, db: Annotated[Session, Depends(get_db)]):
    """Get all instances for a specific problem"""
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )

    # Get all instances for this problem
    instances = db.query(Instance).filter(Instance.problem_id == problem_id).all()
    return instances


@router.post(
    "/problems/{problem_id}/instances",
    response_model=InstanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_instance(
    problem_id: int,
    file: Annotated[UploadFile, File(description="Instance file (required)")],
    db: Annotated[Session, Depends(get_db)],
):
    """Upload a new instance file for a problem"""
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )

    # Read file data
    file_data = await file.read()
    if not file_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File cannot be empty",
        )

    # Create instance
    instance = Instance(
        problem_id=problem_id,
        filename=file.filename or "unknown",
        file_data=file_data,
        content_type=file.content_type,
        file_size=len(file_data),
    )

    db.add(instance)
    db.commit()
    db.refresh(instance)

    return instance


@router.get(
    "/problems/{problem_id}/instances/{instance_id}", response_model=InstanceResponse
)
def get_instance(
    problem_id: int, instance_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Get instance metadata"""
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )

    # Verify instance exists and belongs to the problem
    instance = (
        db.query(Instance)
        .filter(Instance.id == instance_id, Instance.problem_id == problem_id)
        .first()
    )
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found"
        )

    return instance


@router.get("/problems/{problem_id}/instances/{instance_id}/file")
def download_instance(
    problem_id: int, instance_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Download instance file"""
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )

    # Verify instance exists and belongs to the problem
    instance = (
        db.query(Instance)
        .filter(Instance.id == instance_id, Instance.problem_id == problem_id)
        .first()
    )
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found"
        )

    return Response(
        content=instance.file_data,
        media_type=instance.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{instance.filename}"'},
    )


@router.delete(
    "/problems/{problem_id}/instances/{instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_instance(
    problem_id: int, instance_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Delete an instance"""
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )

    # Verify instance exists and belongs to the problem
    instance = (
        db.query(Instance)
        .filter(Instance.id == instance_id, Instance.problem_id == problem_id)
        .first()
    )
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found"
        )

    # Delete instance
    db.delete(instance)
    db.commit()
    return None
