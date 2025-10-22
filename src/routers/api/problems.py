from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from src.database import get_db
from src.models import Problem, Group

router = APIRouter()


class ProblemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    filename: str | None
    content_type: str | None
    file_size: int | None
    is_instances_self_contained: bool
    uploaded_at: datetime
    group_id: int


@router.post("/problems", response_model=ProblemResponse, status_code=201)
async def upload_problem(
    name: str = Form(...),
    group_id: int = Form(...),
    file: UploadFile = File(None, description="File must be in bytes"),
    db: Session = Depends(get_db),
):
    """Upload a new problem with optional file.

    If file is provided: instances are NOT self-contained (need problem file)
    If no file: instances ARE self-contained (contain everything)
    """
    name = name.strip()
    if name == "":
        raise HTTPException(status_code=422, detail="Invalid name")

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Check if problem with same name already exists
    existing = db.query(Problem).filter(Problem.name == name).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="Problem with this name already exists"
        )

    if file:  # if file is provided
        file_data = await file.read()
        if not file_data:
            raise HTTPException(status_code=422, detail="File cannot be empty")

        problem = Problem(
            name=name,
            filename=file.filename or "unknown",
            file_data=file_data,
            content_type=file.content_type,
            file_size=len(file_data),
            is_instances_self_contained=False,
            group_id=group_id,
        )
    else:
        problem = Problem(
            name=name,
            filename=None,
            file_data=None,
            content_type=None,
            file_size=None,
            is_instances_self_contained=True,
            group_id=group_id,
        )

    db.add(problem)
    db.commit()
    db.refresh(problem)

    return problem


@router.get("/problems", response_model=list[ProblemResponse])
def get_problems(group_id: int | None = None, db: Session = Depends(get_db)):
    """Get all problems, optionally filtered by group_id"""
    query = db.query(Problem)

    if group_id is not None:
        # Verify group exists
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # Filter by group
        query = query.filter(Problem.group_id == group_id)

    return query.all()


@router.get("/problems/{id}", response_model=ProblemResponse)
def get_problem(id: int, db: Session = Depends(get_db)):
    """Get problem metadata"""
    problem = db.query(Problem).filter(Problem.id == id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem


@router.get("/problems/{id}/download")
def download_problem(id: int, db: Session = Depends(get_db)):
    """Download problem file"""
    problem = db.query(Problem).filter(Problem.id == id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    if not problem.file_data:
        raise HTTPException(
            status_code=404,
            detail="No file uploaded for this problem (instances are self-contained)",
        )

    return Response(
        content=problem.file_data,
        media_type=problem.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{problem.filename}"'},
    )
