"""Tests for ResourceDefaults, UserResourceConfig models and Project resource columns."""

from src.models import ResourceDefaults, UserResourceConfig, Project
import uuid


def test_resource_defaults_can_be_created(test_db):
    defaults = ResourceDefaults(
        id=1,
        per_user_cpu_cores=3.0,
        per_user_memory_gib=8.0,
        global_max_cpu_cores=4.0,
        global_max_memory_gib=12.0,
    )
    test_db.add(defaults)
    test_db.commit()

    row = test_db.query(ResourceDefaults).filter_by(id=1).one()
    assert row.per_user_cpu_cores == 3.0
    assert row.per_user_memory_gib == 8.0
    assert row.global_max_cpu_cores == 4.0
    assert row.global_max_memory_gib == 12.0
    assert row.updated_at is not None


def test_resource_defaults_singleton(test_db):
    """Only one row should ever exist."""
    test_db.add(ResourceDefaults(
        id=1,
        per_user_cpu_cores=3.0,
        per_user_memory_gib=8.0,
        global_max_cpu_cores=4.0,
        global_max_memory_gib=12.0,
    ))
    test_db.commit()

    count = test_db.query(ResourceDefaults).count()
    assert count == 1


def test_user_resource_config_with_explicit_values(test_db):
    config = UserResourceConfig(
        user_id="user-abc",
        vcpus=8,
        memory_gib=16.0,
    )
    test_db.add(config)
    test_db.commit()

    row = test_db.query(UserResourceConfig).filter_by(user_id="user-abc").one()
    assert row.vcpus == 8
    assert row.memory_gib == 16.0
    assert row.updated_at is not None


def test_user_resource_config_null_means_use_default(test_db):
    """NULL vcpus/memory_gib signals 'use the global per-user default'."""
    config = UserResourceConfig(
        user_id="user-xyz",
        vcpus=None,
        memory_gib=None,
    )
    test_db.add(config)
    test_db.commit()

    row = test_db.query(UserResourceConfig).filter_by(user_id="user-xyz").one()
    assert row.vcpus is None
    assert row.memory_gib is None


def test_user_resource_config_partial_override(test_db):
    """Each field can be overridden independently."""
    config = UserResourceConfig(
        user_id="user-partial",
        vcpus=16,
        memory_gib=None,  # memory still uses default
    )
    test_db.add(config)
    test_db.commit()

    row = test_db.query(UserResourceConfig).filter_by(user_id="user-partial").one()
    assert row.vcpus == 16
    assert row.memory_gib is None


def test_project_resource_columns_can_be_set(test_db):
    project = Project(
        id=uuid.uuid4(),
        user_id="test-user",
        name="Big Project",
        configuration={},
        requested_cpu_cores=8.0,
        requested_memory_gib=16.0,
        is_queued=True,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)

    assert project.requested_cpu_cores == 8.0
    assert project.requested_memory_gib == 16.0
    assert project.is_queued is True


def test_project_is_queued_defaults_false(test_db):
    """is_queued defaults to False — existing projects must not be treated as queued."""
    project = Project(
        id=uuid.uuid4(),
        user_id="test-user",
        name="Old Project",
        configuration={},
        requested_cpu_cores=2.0,
        requested_memory_gib=4.0,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)

    assert project.is_queued is False
