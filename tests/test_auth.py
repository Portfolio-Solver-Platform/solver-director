"""Tests that all newly-protected endpoints enforce authentication and scope checks."""

import pytest
from psp_auth.testing import MockToken


# ── Solvers ───────────────────────────────────────────────────────────────────


def test_get_solvers_requires_auth(client_with_db):
    response = client_with_db.get("/api/solverdirector/v1/solvers")
    assert response.status_code == 401


def test_get_solver_by_id_requires_auth(client_with_db):
    response = client_with_db.get("/api/solverdirector/v1/solvers/1")
    assert response.status_code == 401


def test_upload_solver_requires_auth(client_with_db):
    response = client_with_db.post("/api/solverdirector/v1/solvers", data={})
    assert response.status_code == 401


def test_upload_solver_requires_write_scope(client_with_db, auth):
    """solvers:read is not enough to upload a solver."""
    token = auth.issue_token(MockToken(scopes=["solvers:read"]))
    response = client_with_db.post(
        "/api/solverdirector/v1/solvers",
        data={},
        headers=auth.auth_header(token),
    )
    assert response.status_code == 403


def test_get_solvers_with_read_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["solvers:read"]))
    response = client_with_db.get(
        "/api/solverdirector/v1/solvers",
        headers=auth.auth_header(token),
    )
    assert response.status_code == 200


# ── Groups ────────────────────────────────────────────────────────────────────


def test_get_groups_requires_auth(client_with_db):
    response = client_with_db.get("/api/solverdirector/v1/groups")
    assert response.status_code == 401


def test_create_group_requires_auth(client_with_db):
    response = client_with_db.post(
        "/api/solverdirector/v1/groups", json={"name": "test"}
    )
    assert response.status_code == 401


def test_create_group_requires_write_scope(client_with_db, auth):
    """groups:read is not enough to create a group."""
    token = auth.issue_token(MockToken(scopes=["groups:read"]))
    response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test"},
        headers=auth.auth_header(token),
    )
    assert response.status_code == 403


def test_patch_group_requires_write_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["groups:read"]))
    response = client_with_db.patch(
        "/api/solverdirector/v1/groups/1",
        json={"name": "new-name"},
        headers=auth.auth_header(token),
    )
    assert response.status_code == 403


def test_delete_group_requires_write_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["groups:read"]))
    response = client_with_db.delete(
        "/api/solverdirector/v1/groups/1",
        headers=auth.auth_header(token),
    )
    assert response.status_code == 403


def test_get_groups_with_read_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["groups:read"]))
    response = client_with_db.get(
        "/api/solverdirector/v1/groups",
        headers=auth.auth_header(token),
    )
    assert response.status_code == 200


# ── Problems ──────────────────────────────────────────────────────────────────


def test_get_problems_requires_auth(client_with_db):
    response = client_with_db.get("/api/solverdirector/v1/problems")
    assert response.status_code == 401


def test_create_problem_requires_auth(client_with_db):
    response = client_with_db.post(
        "/api/solverdirector/v1/problems", json={"name": "p", "group_ids": [1]}
    )
    assert response.status_code == 401


def test_create_problem_requires_write_scope(client_with_db, auth):
    """problems:read is not enough to create a problem."""
    token = auth.issue_token(MockToken(scopes=["problems:read"]))
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "p", "group_ids": [1]},
        headers=auth.auth_header(token),
    )
    assert response.status_code == 403


def test_upload_problem_file_requires_write_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["problems:read"]))
    response = client_with_db.put(
        "/api/solverdirector/v1/problems/1/file",
        headers=auth.auth_header(token),
    )
    assert response.status_code == 403


def test_delete_problem_requires_write_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["problems:read"]))
    response = client_with_db.delete(
        "/api/solverdirector/v1/problems/1",
        headers=auth.auth_header(token),
    )
    assert response.status_code == 403


def test_get_problems_with_read_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["problems:read"]))
    response = client_with_db.get(
        "/api/solverdirector/v1/problems",
        headers=auth.auth_header(token),
    )
    assert response.status_code == 200


# ── Instances ─────────────────────────────────────────────────────────────────


def test_get_instances_requires_auth(client_with_db):
    response = client_with_db.get("/api/solverdirector/v1/problems/1/instances")
    assert response.status_code == 401


def test_upload_instance_requires_auth(client_with_db):
    response = client_with_db.post("/api/solverdirector/v1/problems/1/instances")
    assert response.status_code == 401


def test_upload_instance_requires_write_scope(client_with_db, auth):
    """problems:read is not enough to upload an instance."""
    token = auth.issue_token(MockToken(scopes=["problems:read"]))
    response = client_with_db.post(
        "/api/solverdirector/v1/problems/1/instances",
        headers=auth.auth_header(token),
    )
    assert response.status_code == 403


def test_delete_instance_requires_write_scope(client_with_db, auth):
    token = auth.issue_token(MockToken(scopes=["problems:read"]))
    response = client_with_db.delete(
        "/api/solverdirector/v1/problems/1/instances/1",
        headers=auth.auth_header(token),
    )
    assert response.status_code == 403


def test_get_instances_with_read_scope(client_with_db, auth):
    """problems:read is enough to list instances — problem 1 doesn't exist so 404, not 401/403."""
    token = auth.issue_token(MockToken(scopes=["problems:read"]))
    response = client_with_db.get(
        "/api/solverdirector/v1/problems/1/instances",
        headers=auth.auth_header(token),
    )
    # Auth passes — 404 because problem doesn't exist in test DB
    assert response.status_code == 404
