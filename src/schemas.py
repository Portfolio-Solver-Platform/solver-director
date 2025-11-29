from typing import Any
from pydantic import BaseModel, Field


class ProblemConfig(BaseModel):
    """Configuration for a single problem with its instances"""

    problem: int = Field(..., description="Problem ID", gt=0)
    instances: list[int] = Field(..., description="List of instance IDs", min_length=1)

    
    
# class SolverConfig(BaseModel):
#     """Solver Configuration"""
#     id: int = Field(..., description="Solver ID", gt=0)
#     vcpus: int = Field(..., description="number of vCPUs", gt=0)


class ProblemGroupConfig(BaseModel):
    """Configuration for a problem group with solvers and problems"""

    problem_group: int = Field(..., description="Problem group ID", gt=0)
    # solvers: list[SolverConfig] = Field(..., description="List of solver IDs", min_length=1)
    problems: list[ProblemConfig] = Field(
        ..., description="Problems to solve", min_length=1
    )
    extras: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra configurations (e.g., repetitions, solvers)"
    )

class ProjectConfiguration(BaseModel):
    """Full project configuration with multiple problem groups"""

    name: str = Field(..., description="Name of the project")
    problem_groups: list[ProblemGroupConfig] = Field(
        ..., description="List of problem group configurations", min_length=1
    )
