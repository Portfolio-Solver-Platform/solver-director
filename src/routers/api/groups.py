from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from src.database import get_db
from src.models import Group

router = APIRouter()


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None


@router.get("/groups", response_model=list[GroupResponse])
def get_groups(db: Session = Depends(get_db)):
    """Get all groups"""
    return db.query(Group).all()


@router.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    """Get a specific group"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.post("/groups", response_model=GroupResponse, status_code=201)
def create_group(group_data: GroupCreate, db: Session = Depends(get_db)):
    """Create a new group"""
    # Check if group with same name already exists
    if group_data.name.strip() == "":
        raise HTTPException(status_code=422, detail="Group name cannot be empty")
    existing = db.query(Group).filter(Group.name == group_data.name).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="Group with this name already exists"
        )

    group = Group(**group_data.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, db: Session = Depends(get_db)):
    """Delete a group and all associated problems and instances"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db.delete(group)
    db.commit()
    return None
