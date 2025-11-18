from pydantic import BaseModel, Field


class ProblemConfig(BaseModel):
    """Configuration for a single problem with its instances"""

    problem: int = Field(..., description="Problem ID", gt=0)
    instances: list[int] = Field(
        ..., description="List of instance IDs", min_length=1
    )


class ProblemGroupConfig(BaseModel):
    """Configuration for a problem group with solvers and problems"""

    problemGroup: int = Field(..., description="Problem group ID", gt=0)
    solvers: list[int] = Field(..., description="List of solver IDs", min_length=1)
    problems: list[ProblemConfig] = Field(
        ..., description="Problems to solve", min_length=1
    )


class ProjectConfiguration(BaseModel):
    """Full project configuration with multiple problem groups"""
    name: str = Field(..., description="Name of the project")
    configuration: list[ProblemGroupConfig] = Field(
        ..., description="List of problem group configurations", min_length=1
    )
