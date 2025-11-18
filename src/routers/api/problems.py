from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from datetime import datetime

from src.database import get_db
from src.models import Problem, Group

router = APIRouter()


class ProblemCreateRequest(BaseModel):
    name: str
    group_ids: list[int]

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v:
            raise ValueError("Name cannot be empty")
        return v

    @field_validator("group_ids")
    @classmethod
    def validate_group_ids(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("At least one group_id is required")
        # Deduplicate while preserving order
        seen = set()
        return [gid for gid in v if not (gid in seen or seen.add(gid))]


class ProblemUpdateRequest(BaseModel):
    name: str | None = None
    group_ids: list[int] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v:
            raise ValueError("Name cannot be empty")
        return v

    @field_validator("group_ids")
    @classmethod
    def validate_group_ids(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if not v:
            raise ValueError("At least one group_id is required")
        # Deduplicate while preserving order
        seen = set()
        return [gid for gid in v if not (gid in seen or seen.add(gid))]


class ProblemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    filename: str | None
    content_type: str | None
    file_size: int | None
    is_instances_self_contained: bool
    uploaded_at: datetime
    groups: list = Field(serialization_alias="group_ids")

    @field_serializer("groups")
    def serialize_groups(self, groups, _info):
        """Convert list of Group objects to list of group IDs"""
        return [group.id for group in groups]


@router.post("/problems", response_model=ProblemResponse, status_code=201)
def create_problem(
    request: ProblemCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new problem (without file).

    Problems are initially self-contained. Use PUT /problems/{problem_id}/file to upload a file.
    """
    # Strip whitespace from name
    normalized_name = request.name.strip()

    if normalized_name == "":
        raise HTTPException(status_code=422, detail="Name cannot be empty")

    # Validate all groups exist
    groups = db.query(Group).filter(Group.id.in_(request.group_ids)).all()
    if len(groups) != len(request.group_ids):
        found_ids = {g.id for g in groups}
        missing_ids = set(request.group_ids) - found_ids
        raise HTTPException(status_code=404, detail=f"Groups not found: {missing_ids}")

    # Check if problem with same name already exists
    existing = db.query(Problem).filter(Problem.name == normalized_name).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="Problem with this name already exists"
        )

    # Create problem without file (self-contained by default)
    problem = Problem(
        name=normalized_name,
        filename=None,
        file_data=None,
        content_type=None,
        file_size=None,
        is_instances_self_contained=True,
    )

    # Associate problem with groups
    problem.groups = groups

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

        # Filter by group using join on many-to-many relationship
        query = query.join(Problem.groups).filter(Group.id == group_id)

    return query.all()


@router.get("/problems/{problem_id}", response_model=ProblemResponse)
def get_problem(problem_id: int, db: Session = Depends(get_db)):
    """Get problem metadata"""
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem


@router.patch("/problems/{problem_id}", response_model=ProblemResponse)
def update_problem(
    problem_id: int,
    request: ProblemUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update a problem's name and/or groups (partial update)"""
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    # Check that at least one field is provided
    if request.name is None and request.group_ids is None:
        raise HTTPException(
            status_code=422, detail="At least one field must be provided for update"
        )

    # Update name if provided
    if request.name is not None:
        # Strip whitespace
        normalized_name = request.name.strip()

        if normalized_name == "":
            raise HTTPException(status_code=422, detail="Name cannot be empty")

        # Check if another problem with same name exists
        existing = (
            db.query(Problem)
            .filter(Problem.name == normalized_name, Problem.id != problem_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400, detail="Problem with this name already exists"
            )
        problem.name = normalized_name

    # Update groups if provided
    if request.group_ids is not None:
        # Validate all groups exist
        groups = db.query(Group).filter(Group.id.in_(request.group_ids)).all()
        if len(groups) != len(request.group_ids):
            found_ids = {g.id for g in groups}
            missing_ids = set(request.group_ids) - found_ids
            raise HTTPException(
                status_code=404, detail=f"Groups not found: {missing_ids}"
            )
        problem.groups = groups

    db.commit()
    db.refresh(problem)

    return problem


@router.get("/problems/{problem_id}/file")
def download_problem(problem_id: int, db: Session = Depends(get_db)):
    """Download problem file"""
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
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


@router.put("/problems/{problem_id}/file", response_model=ProblemResponse)
async def upload_problem_file(
    problem_id: int,
    file: UploadFile = File(..., description="Problem file"),
    db: Session = Depends(get_db),
):
    """Upload or update a file for an existing problem.

    This changes the problem from self-contained to requiring a problem file.
    """
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    file_data = await file.read()
    if not file_data:
        raise HTTPException(status_code=422, detail="File cannot be empty")

    problem.filename = file.filename or "unknown"
    problem.file_data = file_data
    problem.content_type = file.content_type
    problem.file_size = len(file_data)
    problem.is_instances_self_contained = False

    db.commit()
    db.refresh(problem)

    return problem
