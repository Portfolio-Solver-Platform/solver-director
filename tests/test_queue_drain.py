"""Unit tests for the queue drain function."""

import uuid
from unittest.mock import patch
from src.models import Project, ResourceDefaults
from src.spawner.queue_drain import drain_queue

# Defaults used across tests: per_user_cpu=3.0, global_max_cpu=6.0,
# per_user_mem=8.0, global_max_mem=16.0.
DEFAULTS = {
    "per_user_cpu_cores": 3.0,
    "per_user_memory_gib": 8.0,
    "global_max_cpu_cores": 6.0,
    "global_max_memory_gib": 16.0,
}

SAMPLE_CONFIGURATION = {
    "name": "queued-project",
    "timeout": 3600,
    "vcpus": 1,
    "memory_gib": 2.0,
    "problem_groups": [
        {
            "problem_group": 1,
            "problems": [{"problem": 1, "instances": [1]}],
            "extras": {"solvers": [1]},
        }
    ],
}


def _make_project(user_id, cpu, mem, is_queued=False, is_complete=False, name=None):
    return Project(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name or f"project-{uuid.uuid4()}",
        configuration=SAMPLE_CONFIGURATION,
        requested_cpu_cores=cpu,
        requested_memory_gib=mem,
        is_queued=is_queued,
        is_complete=is_complete,
    )


# ── Basic behaviour ───────────────────────────────────────────────────────────


def test_drain_does_nothing_when_queue_empty(test_db):
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))
    test_db.commit()

    with patch("src.spawner.queue_drain.start_project_services") as mock_start:
        drain_queue(test_db)

    mock_start.assert_not_called()


def test_drain_starts_single_queued_project(test_db):
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))
    project = _make_project("user-a", cpu=2.0, mem=4.0, is_queued=True)
    test_db.add(project)
    test_db.commit()
    project_id = project.id

    with patch("src.spawner.queue_drain.start_project_services") as mock_start:
        drain_queue(test_db)

    mock_start.assert_called_once()
    started = test_db.query(Project).filter_by(id=project_id).first()
    assert started.is_queued is False


def test_drain_starts_multiple_projects_when_all_fit(test_db):
    """All queued projects fit — all should be started."""
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))  # global_max_cpu=6.0
    p1 = _make_project("user-a", cpu=2.0, mem=2.0, is_queued=True)
    p2 = _make_project("user-b", cpu=2.0, mem=2.0, is_queued=True)
    test_db.add(p1)
    test_db.add(p2)
    test_db.commit()

    with patch("src.spawner.queue_drain.start_project_services") as mock_start:
        drain_queue(test_db)

    assert mock_start.call_count == 2
    assert test_db.query(Project).filter_by(is_queued=True).count() == 0


# ── BREAK on global cap ───────────────────────────────────────────────────────


def test_drain_breaks_when_head_exceeds_global_cpu(test_db):
    """Head project would exceed global CPU — nothing starts."""
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))  # global_max_cpu=6.0
    # 5.0 cores already active
    test_db.add(_make_project("user-b", cpu=5.0, mem=1.0))
    # queued project needs 2.0 more → 7.0 > 6.0 global
    queued = _make_project("user-a", cpu=2.0, mem=2.0, is_queued=True)
    test_db.add(queued)
    test_db.commit()

    with patch("src.spawner.queue_drain.start_project_services") as mock_start:
        drain_queue(test_db)

    mock_start.assert_not_called()
    assert test_db.query(Project).filter_by(is_queued=True).count() == 1


def test_drain_breaks_when_head_exceeds_global_memory(test_db):
    """Head project would exceed global memory — nothing starts."""
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))  # global_max_mem=16.0
    test_db.add(_make_project("user-b", cpu=1.0, mem=13.0))
    queued = _make_project("user-a", cpu=1.0, mem=4.0, is_queued=True)
    test_db.add(queued)
    test_db.commit()

    with patch("src.spawner.queue_drain.start_project_services") as mock_start:
        drain_queue(test_db)

    mock_start.assert_not_called()


def test_drain_breaks_on_global_cap_and_leaves_later_items_queued(test_db):
    """When the head is blocked globally, later queue items are also left queued."""
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))  # global_max_cpu=6.0
    test_db.add(_make_project("user-x", cpu=5.0, mem=1.0))  # 5.0 active
    # head needs 2.0 → blocked
    p1 = _make_project("user-a", cpu=2.0, mem=1.0, is_queued=True)
    # tail needs 0.5 → would fit, but we must not start it
    p2 = _make_project("user-b", cpu=0.5, mem=1.0, is_queued=True)
    test_db.add(p1)
    test_db.add(p2)
    test_db.commit()

    with patch("src.spawner.queue_drain.start_project_services") as mock_start:
        drain_queue(test_db)

    mock_start.assert_not_called()
    assert test_db.query(Project).filter_by(is_queued=True).count() == 2


# ── CONTINUE on per-user cap ──────────────────────────────────────────────────


def test_drain_skips_per_user_capped_project_and_starts_next(test_db):
    """User A is at their limit; user B's project behind them in the queue should still start."""
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))  # per_user_cpu=3.0, global_max_cpu=6.0
    # User A already has 2.0 active cores — one more at 2.0 would exceed their 3.0 limit
    test_db.add(_make_project("user-a", cpu=2.0, mem=2.0))
    queued_a = _make_project("user-a", cpu=2.0, mem=2.0, is_queued=True)
    queued_b = _make_project("user-b", cpu=1.0, mem=2.0, is_queued=True)
    test_db.add(queued_a)
    test_db.add(queued_b)
    test_db.commit()
    a_id = queued_a.id
    b_id = queued_b.id

    with patch("src.spawner.queue_drain.start_project_services") as mock_start:
        drain_queue(test_db)

    mock_start.assert_called_once()
    assert test_db.query(Project).filter_by(id=a_id).first().is_queued is True
    assert test_db.query(Project).filter_by(id=b_id).first().is_queued is False


def test_drain_continues_past_per_user_cap_even_when_global_has_little_room(test_db):
    """CONTINUE still applies even when global is nearly full."""
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))  # global_max_cpu=6.0, per_user_cpu=3.0
    # 4.0 cores active globally; user-a has 3.0 of them (at their limit)
    test_db.add(_make_project("user-a", cpu=3.0, mem=1.0))
    test_db.add(_make_project("user-x", cpu=1.0, mem=1.0))
    # user-a blocked (per-user), user-b gets to start (1.0 fits globally: 4+1=5 ≤ 6)
    queued_a = _make_project("user-a", cpu=1.0, mem=1.0, is_queued=True)
    queued_b = _make_project("user-b", cpu=1.0, mem=1.0, is_queued=True)
    test_db.add(queued_a)
    test_db.add(queued_b)
    test_db.commit()
    b_id = queued_b.id

    with patch("src.spawner.queue_drain.start_project_services") as mock_start:
        drain_queue(test_db)

    mock_start.assert_called_once()
    assert test_db.query(Project).filter_by(id=b_id).first().is_queued is False


# ── Service failure ───────────────────────────────────────────────────────────


def test_drain_keeps_project_queued_on_service_failure(test_db):
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))
    project = _make_project("user-a", cpu=1.0, mem=2.0, is_queued=True)
    test_db.add(project)
    test_db.commit()
    project_id = project.id

    with patch(
        "src.spawner.queue_drain.start_project_services",
        side_effect=Exception("K8s unavailable"),
    ):
        drain_queue(test_db)

    assert test_db.query(Project).filter_by(id=project_id).first().is_queued is True


def test_drain_stops_after_service_failure_but_keeps_earlier_starts(test_db):
    """If the 2nd project fails to start, the 1st (already started) stays started."""
    test_db.add(ResourceDefaults(id=1, **DEFAULTS))
    p1 = _make_project("user-a", cpu=1.0, mem=2.0, is_queued=True)
    p2 = _make_project("user-b", cpu=1.0, mem=2.0, is_queued=True)
    test_db.add(p1)
    test_db.add(p2)
    test_db.commit()
    p1_id, p2_id = p1.id, p2.id

    call_count = 0

    def fail_on_second(config, project_id, user_id):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("K8s blip")

    with patch("src.spawner.queue_drain.start_project_services", side_effect=fail_on_second):
        drain_queue(test_db)

    assert test_db.query(Project).filter_by(id=p1_id).first().is_queued is False
    assert test_db.query(Project).filter_by(id=p2_id).first().is_queued is True


# ── Config fallback ───────────────────────────────────────────────────────────


def test_drain_uses_config_fallback_when_no_defaults_row(test_db):
    """Drain works even before an admin has set explicit defaults."""
    from src.config import Config

    # No ResourceDefaults row — uses Config fallbacks (per_user_cpu=3.0, global_max_cpu=4.0)
    project = _make_project(
        "user-a",
        cpu=Config.ResourceLimitDefaults.PER_USER_CPU_CORES - 0.5,
        mem=1.0,
        is_queued=True,
    )
    test_db.add(project)
    test_db.commit()

    with patch("src.spawner.queue_drain.start_project_services") as mock_start:
        drain_queue(test_db)

    mock_start.assert_called_once()
    assert test_db.query(Project).filter_by(id=project.id).first().is_queued is False
