from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
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
def get_instances(problem_id: int, db: Session = Depends(get_db)):
    """Get all instances for a specific problem"""
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    # Get all instances for this problem
    instances = db.query(Instance).filter(Instance.problem_id == problem_id).all()
    return instances


@router.post(
    "/problems/{problem_id}/instances", response_model=InstanceResponse, status_code=201
)
async def upload_instance(
    problem_id: int,
    file: UploadFile = File(..., description="Instance file (required)"),
    db: Session = Depends(get_db),
):
    """Upload a new instance file for a problem"""
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    # Read file data
    file_data = await file.read()
    if not file_data:
        raise HTTPException(status_code=422, detail="File cannot be empty")

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
