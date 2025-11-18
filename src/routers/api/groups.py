from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from src.database import get_db
from src.models import Group, Solver

router = APIRouter()


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    solver_ids: list[int] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v:
            raise ValueError("Name cannot be empty")
        return v

    @field_validator("solver_ids")
    @classmethod
    def validate_solver_ids(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        # Allow empty list
        # Deduplicate while preserving order
        seen = set()
        return [sid for sid in v if not (sid in seen or seen.add(sid))]


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    solvers: list = Field(serialization_alias="solver_ids", default=[])

    @field_serializer("solvers")
    def serialize_solvers(self, solvers, _info):
        """Convert list of Solver objects to list of solver IDs"""
        return [solver.id for solver in solvers]


@router.get("/groups", response_model=list[GroupResponse])
def get_groups(db: Annotated[Session, Depends(get_db)]):
    """Get all groups"""
    return db.query(Group).all()


@router.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(group_id: int, db: Annotated[Session, Depends(get_db)]):
    """Get a specific group"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    return group


@router.patch("/groups/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: int,
    request: GroupUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Update a group's name, description, and/or supported solvers"""
    # Verify group exists
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # Check at least one field provided
    if (
        request.name is None
        and request.description is None
        and request.solver_ids is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided for update",
        )

    # Update name if provided
    if request.name is not None:
        normalized_name = request.name.strip()

        if normalized_name == "":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Name cannot be empty",
            )

        # Check for duplicate
        existing = (
            db.query(Group)
            .filter(Group.name == normalized_name, Group.id != group_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group with this name already exists",
            )
        group.name = normalized_name

    # Update description if provided
    if request.description is not None:
        group.description = request.description

    # Update solvers if provided
    if request.solver_ids is not None:
        # Validate all solvers exist
        solvers = db.query(Solver).filter(Solver.id.in_(request.solver_ids)).all()
        if len(solvers) != len(request.solver_ids):
            found_ids = {s.id for s in solvers}
            missing_ids = set(request.solver_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Solvers not found: {missing_ids}",
            )
        group.solvers = solvers

    db.commit()
    db.refresh(group)

    return group


@router.post(
    "/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED
)
def create_group(group_data: GroupCreate, db: Annotated[Session, Depends(get_db)]):
    """Create a new group"""
    # Check if group with same name already exists
    if group_data.name.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Group name cannot be empty",
        )
    existing = db.query(Group).filter(Group.name == group_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group with this name already exists",
        )

    group = Group(**group_data.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, db: Annotated[Session, Depends(get_db)]):
    """Delete a group and all associated problems and instances"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    db.delete(group)
    db.commit()
    return None
