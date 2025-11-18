from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Any
import requests

from src.database import get_db
from src.models import Project
from src.spawner.start_service import start_solver_controller
from src.config import Config

router = APIRouter()


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    solver_controller_id: str
    created_at: datetime


class ProjectWithStatusResponse(ProjectResponse):
    status: Any


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(db: Session = Depends(get_db)):
    """Create a new project and start a solver controller"""
    # TODO: Get user_id from authentication when implemented. Also make sure to implement tests for user_id handling.
    user_id = "sofus"

    # Start solver controller
    try:
        solver_controller_id = start_solver_controller(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start solver controller: {str(e)}",
        )

    # Create project in database
    project = Project(
        user_id=user_id,
        solver_controller_id=solver_controller_id,
    )

    db.add(project)

    try:
        db.commit()
        db.refresh(project)
    except Exception as e:
        db.rollback()
        # Check if it's a unique constraint violation
        if "UNIQUE constraint failed" in str(e) or "duplicate key" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail="Project with this solver controller already exists",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create project: {str(e)}",
        )

    return project


@router.get("/projects", response_model=list[ProjectResponse])
def get_projects(user_id: str | None = None, db: Session = Depends(get_db)):
    """Get all projects, optionally filtered by user_id"""
    query = db.query(Project)

    if user_id is not None:
        query = query.filter(Project.user_id == user_id)

    return query.all()


@router.get("/projects/{project_id}", response_model=ProjectWithStatusResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get project by id with solver controller status"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build URL to solver controller's status endpoint
    url = f"http://{Config.SolverController.SVC_NAME}.{project.solver_controller_id}.svc.cluster.local:{Config.SolverController.SERVICE_PORT}/v1/status"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        status_data = response.json()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to solver controller: {str(e)}",
        )

    return ProjectWithStatusResponse(
        id=project.id,
        user_id=project.user_id,
        solver_controller_id=project.solver_controller_id,
        created_at=project.created_at,
        status=status_data,
    )
