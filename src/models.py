from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Table,
    LargeBinary,
    DateTime,
    Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

solver_supported_groups = Table(
    "solver_supported_groups",
    Base.metadata,
    Column(
        "solver_id",
        Integer,
        ForeignKey("solvers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "group_id",
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

problem_groups = Table(
    "problem_groups",
    Base.metadata,
    Column(
        "problem_id",
        Integer,
        ForeignKey("problems.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "group_id",
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class SolverImage(Base):
    __tablename__ = "solver_images"
    id = Column(Integer, primary_key=True, autoincrement=True)
    image_path = Column(String, nullable=False)

    solvers = relationship("Solver", back_populates="solver_image")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)

    problems = relationship(
        "Problem", secondary=problem_groups, back_populates="groups"
    )
    solvers = relationship(
        "Solver", secondary=solver_supported_groups, back_populates="supported_groups"
    )


class Solver(Base):
    __tablename__ = "solvers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    solver_images_id = Column(
        Integer, ForeignKey("solver_images.id", ondelete="CASCADE"), nullable=False
    )

    solver_image = relationship("SolverImage", back_populates="solvers")
    supported_groups = relationship(
        "Group", secondary=solver_supported_groups, back_populates="solvers"
    )


class Problem(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    filename = Column(String, nullable=True)
    file_data = Column(LargeBinary, nullable=True)
    content_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    is_instances_self_contained = Column(Boolean, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())

    groups = relationship("Group", secondary=problem_groups, back_populates="problems")
    instances = relationship(
        "Instance", back_populates="problem", cascade="all, delete-orphan"
    )


class Instance(Base):
    __tablename__ = "instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    problem_id = Column(
        Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False
    )
    filename = Column(String, nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    content_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())

    problem = relationship("Problem", back_populates="instances")

    # problem, if group deleted, then all problems are also deleted


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    solver_controller_id = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
