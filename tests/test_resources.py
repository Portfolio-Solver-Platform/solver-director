"""Tests for resource defaults and user resource config endpoints."""

import uuid
from psp_auth.testing import MockToken, MockUser
from src.models import ResourceDefaults, UserResourceConfig, Project

VALID_DEFAULTS = {
    "per_user_cpu_cores": 3.0,
    "per_user_memory_gib": 8.0,
    "global_max_cpu_cores": 4.0,
    "global_max_memory_gib": 12.0,
}


# ── Auth ──────────────────────────────────────────────────────────────────────


def test_get_defaults_requires_auth(client_with_db):
    response = client_with_db.get("/v1/resources/defaults")
    assert response.status_code == 401


def test_put_defaults_requires_auth(client_with_db):
    response = client_with_db.put("/v1/resources/defaults", json=VALID_DEFAULTS)
    assert response.status_code == 401


def test_get_defaults_requires_write_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["projects:read"]))
    response = client_with_db.get(
        "/v1/resources/defaults", headers=auth.auth_header(token)
    )
    assert response.status_code == 403


def test_put_defaults_requires_write_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["projects:read"]))
    response = client_with_db.put(
        "/v1/resources/defaults", json=VALID_DEFAULTS, headers=auth.auth_header(token)
    )
    assert response.status_code == 403


# ── GET /resources/defaults ───────────────────────────────────────────────────


def test_get_defaults_returns_config_fallback_when_no_db_row(client_with_db, auth):
    """When no admin has configured limits yet, Config fallbacks are returned."""
    from src.config import Config

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.get(
        "/v1/resources/defaults", headers=auth.auth_header(token)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["per_user_cpu_cores"] == Config.ResourceLimitDefaults.PER_USER_CPU_CORES
    assert data["per_user_memory_gib"] == Config.ResourceLimitDefaults.PER_USER_MEMORY_GIB
    assert data["global_max_cpu_cores"] == Config.ResourceLimitDefaults.GLOBAL_MAX_CPU_CORES
    assert data["global_max_memory_gib"] == Config.ResourceLimitDefaults.GLOBAL_MAX_MEMORY_GIB


def test_get_defaults_returns_db_row_when_configured(client_with_db, auth, test_db):
    """When a row exists, the DB values are returned."""
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.get(
        "/v1/resources/defaults", headers=auth.auth_header(token)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["per_user_cpu_cores"] == 3.0
    assert data["per_user_memory_gib"] == 8.0
    assert data["global_max_cpu_cores"] == 4.0
    assert data["global_max_memory_gib"] == 12.0


# ── PUT /resources/defaults ───────────────────────────────────────────────────


def test_put_defaults_creates_row_on_first_call(client_with_db, auth, test_db):
    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.put(
        "/v1/resources/defaults", json=VALID_DEFAULTS, headers=auth.auth_header(token)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["per_user_cpu_cores"] == 3.0
    assert data["per_user_memory_gib"] == 8.0
    assert data["global_max_cpu_cores"] == 4.0
    assert data["global_max_memory_gib"] == 12.0

    assert test_db.query(ResourceDefaults).count() == 1


def test_put_defaults_updates_existing_row(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    updated = {**VALID_DEFAULTS, "per_user_cpu_cores": 2.0, "global_max_cpu_cores": 8.0}
    response = client_with_db.put(
        "/v1/resources/defaults", json=updated, headers=auth.auth_header(token)
    )
    assert response.status_code == 200
    assert response.json()["per_user_cpu_cores"] == 2.0
    assert response.json()["global_max_cpu_cores"] == 8.0

    assert test_db.query(ResourceDefaults).count() == 1


def test_put_defaults_rejects_global_cpu_less_than_per_user(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    invalid = {**VALID_DEFAULTS, "global_max_cpu_cores": 2.0, "per_user_cpu_cores": 3.0}
    response = client_with_db.put(
        "/v1/resources/defaults", json=invalid, headers=auth.auth_header(token)
    )
    assert response.status_code == 422
    assert "global_max_cpu_cores" in response.json()["detail"]


def test_put_defaults_rejects_global_memory_less_than_per_user(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    invalid = {**VALID_DEFAULTS, "global_max_memory_gib": 4.0, "per_user_memory_gib": 8.0}
    response = client_with_db.put(
        "/v1/resources/defaults", json=invalid, headers=auth.auth_header(token)
    )
    assert response.status_code == 422
    assert "global_max_memory_gib" in response.json()["detail"]


def test_put_defaults_equal_global_and_per_user_is_valid(client_with_db, auth):
    """global == per_user is allowed (single-user scenario)."""
    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    equal = {
        "per_user_cpu_cores": 4.0,
        "per_user_memory_gib": 12.0,
        "global_max_cpu_cores": 4.0,
        "global_max_memory_gib": 12.0,
    }
    response = client_with_db.put(
        "/v1/resources/defaults", json=equal, headers=auth.auth_header(token)
    )
    assert response.status_code == 200


def test_put_defaults_rejects_zero_values(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    invalid = {**VALID_DEFAULTS, "per_user_cpu_cores": 0.0}
    response = client_with_db.put(
        "/v1/resources/defaults", json=invalid, headers=auth.auth_header(token)
    )
    assert response.status_code == 422


def test_get_after_put_returns_updated_values(client_with_db, auth):
    """Round-trip: PUT then GET returns the same values."""
    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    client_with_db.put(
        "/v1/resources/defaults", json=VALID_DEFAULTS, headers=auth.auth_header(token)
    )
    response = client_with_db.get(
        "/v1/resources/defaults", headers=auth.auth_header(token)
    )
    assert response.status_code == 200
    assert response.json() == VALID_DEFAULTS


# ── Auth: user resource config ────────────────────────────────────────────────


def test_get_user_config_requires_auth(client_with_db):
    response = client_with_db.get("/v1/resources/users/user-a")
    assert response.status_code == 401


def test_put_user_config_requires_auth(client_with_db):
    response = client_with_db.put(
        "/v1/resources/users/user-a", json={"vcpus": 2, "memory_gib": 4.0}
    )
    assert response.status_code == 401


def test_delete_user_config_requires_auth(client_with_db):
    response = client_with_db.delete("/v1/resources/users/user-a")
    assert response.status_code == 401


def test_get_user_config_requires_read_scope(client_with_db, auth):
    """No scope at all → 403."""
    token = auth.issue_token(MockToken(scopes=["projects:read"]))
    assert client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    ).status_code == 403


def test_get_user_config_other_user_requires_write_scope(client_with_db, auth):
    """resources:read is not enough to read another user's data."""
    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    assert client_with_db.get(
        "/v1/resources/users/user-b", headers=auth.auth_header(token)
    ).status_code == 403


def test_put_user_config_requires_write_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["resources:read"]))
    assert client_with_db.put(
        "/v1/resources/users/user-a",
        json={"vcpus": 2, "memory_gib": 4.0},
        headers=auth.auth_header(token),
    ).status_code == 403


def test_delete_user_config_requires_write_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["resources:read"]))
    assert client_with_db.delete(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    ).status_code == 403


# ── GET /resources/users/{user_id} ────────────────────────────────────────────


def test_get_user_config_self_allowed_with_read_scope(client_with_db, auth):
    """A user can read their own resource data with just resources:read."""
    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    response = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    )
    assert response.status_code == 200


def test_get_user_config_admin_can_read_any_user(client_with_db, auth):
    """An admin with resources:read + resources:write can read any user."""
    token = auth.issue_token(MockToken(scopes=["resources:read", "resources:write"]))
    response = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    )
    assert response.status_code == 200


def test_get_user_config_returns_null_overrides_when_no_config(client_with_db, auth):
    """When no override exists the overrides are null and defaults are used."""
    from src.config import Config

    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    response = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["vcpus_override"] is None
    assert data["memory_gib_override"] is None
    assert data["effective_cpu_cores"] == Config.ResourceLimitDefaults.PER_USER_CPU_CORES
    assert data["effective_memory_gib"] == Config.ResourceLimitDefaults.PER_USER_MEMORY_GIB


def test_get_user_config_returns_override_when_set(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.add(UserResourceConfig(user_id="user-a", vcpus=2, memory_gib=6.0))
    test_db.commit()

    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    response = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user-a"
    assert data["vcpus_override"] == 2.0
    assert data["memory_gib_override"] == 6.0
    assert data["effective_cpu_cores"] == 2.0
    assert data["effective_memory_gib"] == 6.0


def test_get_user_config_returns_db_defaults_when_no_override(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.commit()

    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    data = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    ).json()

    assert data["effective_cpu_cores"] == VALID_DEFAULTS["per_user_cpu_cores"]
    assert data["effective_memory_gib"] == VALID_DEFAULTS["per_user_memory_gib"]


def test_get_user_config_in_use_is_zero_with_no_projects(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.commit()

    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    data = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    ).json()

    assert data["in_use_cpu_cores"] == 0.0
    assert data["in_use_memory_gib"] == 0.0


def test_get_user_config_in_use_reflects_active_projects(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.add(_make_project("user-a", cpu=1.0, mem=2.0))
    test_db.add(_make_project("user-a", cpu=1.5, mem=3.0))
    test_db.commit()

    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    data = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    ).json()

    assert data["in_use_cpu_cores"] == 2.5
    assert data["in_use_memory_gib"] == 5.0
    assert data["available_cpu_cores"] == VALID_DEFAULTS["per_user_cpu_cores"] - 2.5
    assert data["available_memory_gib"] == VALID_DEFAULTS["per_user_memory_gib"] - 5.0


def test_get_user_config_queued_projects_do_not_count_as_in_use(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.add(_make_project("user-a", cpu=1.0, mem=2.0))
    test_db.add(_make_project("user-a", cpu=2.0, mem=4.0, is_queued=True))
    test_db.commit()

    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    data = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    ).json()

    assert data["in_use_cpu_cores"] == 1.0
    assert data["in_use_memory_gib"] == 2.0


def test_get_user_config_completed_projects_do_not_count_as_in_use(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.add(_make_project("user-a", cpu=1.0, mem=2.0))
    test_db.add(_make_project("user-a", cpu=2.0, mem=4.0, is_complete=True))
    test_db.commit()

    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    data = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    ).json()

    assert data["in_use_cpu_cores"] == 1.0
    assert data["in_use_memory_gib"] == 2.0


def test_get_user_config_only_counts_own_projects(client_with_db, auth, test_db):
    """Projects from other users must not appear in in_use."""
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.add(_make_project("user-a", cpu=1.0, mem=2.0))
    test_db.add(_make_project("user-b", cpu=3.0, mem=6.0))
    test_db.commit()

    user = MockUser(id="user-a")
    token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    data = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    ).json()

    assert data["in_use_cpu_cores"] == 1.0
    assert data["in_use_memory_gib"] == 2.0


def test_get_user_config_admin_sees_correct_in_use(client_with_db, auth, test_db):
    """An admin requesting another user's data sees that user's in_use."""
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.add(_make_project("user-a", cpu=1.5, mem=3.0))
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:read", "resources:write"]))
    data = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    ).json()

    assert data["in_use_cpu_cores"] == 1.5
    assert data["in_use_memory_gib"] == 3.0


# ── PUT /resources/users/{user_id} ────────────────────────────────────────────


def test_put_user_config_creates_override(client_with_db, auth, test_db):
    # Seed global defaults so validation has a ceiling to check against
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.put(
        "/v1/resources/users/user-a",
        json={"vcpus": 2, "memory_gib": 4.0},
        headers=auth.auth_header(token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user-a"
    assert data["vcpus"] == 2.0
    assert data["memory_gib"] == 4.0

    assert test_db.query(UserResourceConfig).filter_by(user_id="user-a").count() == 1


def test_put_user_config_updates_existing_override(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.add(UserResourceConfig(user_id="user-a", vcpus=2, memory_gib=4.0))
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.put(
        "/v1/resources/users/user-a",
        json={"vcpus": 3, "memory_gib": 6.0},
        headers=auth.auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["vcpus"] == 3.0
    assert response.json()["memory_gib"] == 6.0

    assert test_db.query(UserResourceConfig).filter_by(user_id="user-a").count() == 1


def test_put_user_config_rejects_cpu_exceeding_global_max(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))  # global_max_cpu_cores=4.0
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.put(
        "/v1/resources/users/user-a",
        json={"vcpus": 5, "memory_gib": 4.0},  # 5.0 > 4.0 global max
        headers=auth.auth_header(token),
    )
    assert response.status_code == 422
    assert "vcpus" in response.json()["detail"]


def test_put_user_config_rejects_memory_exceeding_global_max(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))  # global_max_memory_gib=12.0
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.put(
        "/v1/resources/users/user-a",
        json={"vcpus": 2, "memory_gib": 20.0},  # 20.0 > 12.0 global max
        headers=auth.auth_header(token),
    )
    assert response.status_code == 422
    assert "memory_gib" in response.json()["detail"]


def test_put_user_config_equal_to_global_max_is_valid(client_with_db, auth, test_db):
    """A user can be given the full global budget."""
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.put(
        "/v1/resources/users/user-a",
        json={"vcpus": 4, "memory_gib": 12.0},  # exactly at global max
        headers=auth.auth_header(token),
    )
    assert response.status_code == 200


def test_put_user_config_uses_config_fallback_when_no_defaults_row(client_with_db, auth):
    """Validation works even before an admin has set explicit defaults."""
    from src.config import Config

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    # Request values within the Config fallback global max
    response = client_with_db.put(
        "/v1/resources/users/user-a",
        json={
            "vcpus": Config.ResourceLimitDefaults.GLOBAL_MAX_CPU_CORES,
            "memory_gib": Config.ResourceLimitDefaults.GLOBAL_MAX_MEMORY_GIB,
        },
        headers=auth.auth_header(token),
    )
    assert response.status_code == 200


def test_put_user_config_rejects_zero_values(client_with_db, auth, test_db):
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.put(
        "/v1/resources/users/user-a",
        json={"vcpus": 0, "memory_gib": 4.0},
        headers=auth.auth_header(token),
    )
    assert response.status_code == 422


# ── DELETE /resources/users/{user_id} ─────────────────────────────────────────


def test_delete_user_config_removes_override(client_with_db, auth, test_db):
    test_db.add(UserResourceConfig(user_id="user-a", vcpus=2, memory_gib=4.0))
    test_db.commit()

    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.delete(
        "/v1/resources/users/user-a", headers=auth.auth_header(token)
    )
    assert response.status_code == 204
    assert test_db.query(UserResourceConfig).filter_by(user_id="user-a").count() == 0


def test_delete_user_config_returns_404_when_no_override(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["resources:write"]))
    response = client_with_db.delete(
        "/v1/resources/users/nonexistent-user", headers=auth.auth_header(token)
    )
    assert response.status_code == 404


def test_get_returns_null_overrides_after_delete(client_with_db, auth, test_db):
    """After deleting an override, GET returns null overrides and falls back to defaults."""
    test_db.add(ResourceDefaults(id=1, **VALID_DEFAULTS))
    test_db.add(UserResourceConfig(user_id="user-a", vcpus=2, memory_gib=4.0))
    test_db.commit()

    admin_token = auth.issue_token(MockToken(scopes=["resources:write"]))
    client_with_db.delete("/v1/resources/users/user-a", headers=auth.auth_header(admin_token))

    user = MockUser(id="user-a")
    read_token = auth.issue_token(MockToken(scopes=["resources:read"], user=user))
    data = client_with_db.get(
        "/v1/resources/users/user-a", headers=auth.auth_header(read_token)
    ).json()

    assert data["vcpus_override"] is None
    assert data["memory_gib_override"] is None
    assert data["effective_cpu_cores"] == VALID_DEFAULTS["per_user_cpu_cores"]
    assert data["effective_memory_gib"] == VALID_DEFAULTS["per_user_memory_gib"]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_project(user_id, cpu, mem, is_complete=False, is_queued=False):
    return Project(
        id=uuid.uuid4(),
        user_id=user_id,
        name=f"project-{uuid.uuid4()}",
        configuration={},
        requested_cpu_cores=cpu,
        requested_memory_gib=mem,
        is_complete=is_complete,
        is_queued=is_queued,
    )
