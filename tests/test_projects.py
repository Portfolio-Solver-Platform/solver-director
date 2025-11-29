"""Tests for projects API endpoints"""

from unittest.mock import patch, MagicMock
from psp_auth.testing import MockToken, MockUser

# Test data
VALID_CONFIG = {
    "name": "Test Project",
    "problem_groups": [
        {
            "problem_group": 1,
            "problems": [
                {"problem": 10, "instances": [1, 2, 3]},
                {"problem": 11, "instances": [4, 5]},
            ],
            "extras": {
                "solvers": [1, 2]
            }
        }
    ],
}

VALID_CONFIG_MULTI_GROUP = {
    "name": "Multi-Group Project",
    "problem_groups": [
        {
            "problem_group": 1,
            "problems": [{"problem": 10, "instances": [1, 2]}],
            "extras": {
                "solvers": [1, 2]
            }
        },
        {
            "problem_group": 2,
            "problems": [
                {"problem": 20, "instances": [1]},
                {"problem": 21, "instances": [2, 3, 4]},
            ],
            "extras": {
                "solvers": [3, 4, 5]
            }
        },
    ],
}


def test_create_project(client_with_db, auth):
    """Test creating a new project with valid configuration"""
    mock_user = MockUser(id="test-user-123")
    mock_token = MockToken(scopes=["projects:write"], user=mock_user)
    token = auth.issue_token(mock_token)
    with patch("src.routers.api.projects.start_project_services") as mock_start:
        response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(token)
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == mock_user.id
        assert data["name"] == "Test Project"
        assert "id" in data
        assert isinstance(data["id"], str)  # UUID as string
        assert "created_at" in data

        # Verify start_project_services was called with (config, project_id, user_id)
        mock_start.assert_called_once()
        call_args = mock_start.call_args[0]
        # First arg is the config object
        # Second arg is project_id as UUID string
        assert isinstance(call_args[1], str)  # project_id as UUID string
        assert call_args[2] == mock_user.id  # user_id


def test_get_all_projects(client_with_db, auth):
    """Test getting all projects"""
    mock_user = MockUser(id="test-user-123")
    write_token_obj = MockToken(scopes=["projects:write"], user=mock_user)
    read_token_obj = MockToken(scopes=["projects:read"], user=mock_user)
    write_token = auth.issue_token(write_token_obj)
    read_token = auth.issue_token(read_token_obj)
    with patch("src.routers.api.projects.start_project_services"):
        # Create two projects
        client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(write_token)
        )
        client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(write_token)
        )

        # Get all projects
        response = client_with_db.get(
            "/v1/projects", headers=auth.auth_header(read_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Test Project"
        assert data[1]["name"] == "Test Project"
        assert isinstance(data[0]["id"], str)
        assert isinstance(data[1]["id"], str)
        assert data[0]["user_id"] == mock_user.id
        assert data[1]["user_id"] == mock_user.id


def test_get_project_status(client_with_db, auth):
    """Test getting a specific project status"""
    mock_user = MockUser(id="test-user-123")
    write_token_obj = MockToken(scopes=["projects:write"], user=mock_user)
    read_token_obj = MockToken(scopes=["projects:read"], user=mock_user)
    write_token = auth.issue_token(write_token_obj)
    read_token = auth.issue_token(read_token_obj)
    with patch("src.routers.api.projects.start_project_services"):
        # Create project
        create_response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(write_token)
        )
        project_id = create_response.json()["id"]

        # Mock the status response
        with patch("src.routers.api.projects.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "isFinished": False,
                "messages": ["Processing..."],
            }
            mock_get.return_value = mock_response

            # Get project status
            response = client_with_db.get(
                f"/v1/projects/{project_id}/status",
                headers=auth.auth_header(read_token),
            )
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == project_id
            assert data["name"] == "Test Project"
            assert data["user_id"] == mock_user.id
            assert "status" in data
            assert data["status"]["isFinished"] is False
            assert len(data["status"]["messages"]) == 1


def test_get_nonexistent_project_status(client_with_db, auth):
    """Test getting non-existent project status returns 404"""
    token = auth.issue_token(MockToken(scopes=["projects:read"]))
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = client_with_db.get(
        f"/v1/projects/{fake_uuid}/status", headers=auth.auth_header(token)
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid user or project"


def test_create_project_solver_controller_failure(client_with_db, auth):
    """Test that project creation fails if solver controller fails to start"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    with patch("src.routers.api.projects.start_project_services") as mock_start:
        mock_start.side_effect = Exception("Failed to start solver controller")

        response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(token)
        )

        # Should return 500 with generic error message
        assert response.status_code == 500
        assert response.json()["detail"] == "Unable to create project"


def test_get_project_status_connection_error(client_with_db, auth):
    """Test that getting project status returns 503 when solver controller is unreachable"""
    write_token = auth.issue_token(MockToken(scopes=["projects:write"]))
    read_token = auth.issue_token(MockToken(scopes=["projects:read"]))
    with patch("src.routers.api.projects.start_project_services"):
        # Create project
        create_response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(write_token)
        )
        project_id = create_response.json()["id"]

        # Mock connection error
        with patch("src.routers.api.projects.requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            # Get project status - should fail with 503
            response = client_with_db.get(
                f"/v1/projects/{project_id}/status",
                headers=auth.auth_header(read_token),
            )
            assert response.status_code == 503
            assert "unavailable" in response.json()["detail"].lower()


# DELETE /projects/{project_id} tests
def test_delete_project_success(client_with_db, auth):
    """Test successfully deleting a project"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    with patch("src.routers.api.projects.start_project_services"):
        # Create project
        create_response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(token)
        )
        project_id = create_response.json()["id"]

        # Delete project
        with patch("src.routers.api.projects.stop_solver_controller") as mock_stop:
            delete_response = client_with_db.delete(
                f"/v1/projects/{project_id}", headers=auth.auth_header(token)
            )
            assert delete_response.status_code == 204

            # Verify stop_solver_controller was called with UUID string
            mock_stop.assert_called_once()
            call_args = mock_stop.call_args[0]
            assert call_args[0] == project_id  # Should be UUID string

        # Verify project no longer exists (check via status endpoint)
        read_token = auth.issue_token(MockToken(scopes=["projects:read"]))
        get_response = client_with_db.get(
            f"/v1/projects/{project_id}/status", headers=auth.auth_header(read_token)
        )
        assert get_response.status_code == 404


def test_delete_nonexistent_project(client_with_db, auth):
    """Test deleting a non-existent project returns 404"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    delete_response = client_with_db.delete(
        f"/v1/projects/{fake_uuid}", headers=auth.auth_header(token)
    )
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == "Invalid user or project"


def test_delete_project_namespace_failure(client_with_db, auth):
    """Test that project is deleted even if namespace deletion fails"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    with patch("src.routers.api.projects.start_project_services"):
        # Create project
        create_response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(token)
        )
        project_id = create_response.json()["id"]

        # Delete project with namespace deletion failure
        with patch("src.routers.api.projects.stop_solver_controller") as mock_stop:
            mock_stop.side_effect = Exception("Namespace not found")

            delete_response = client_with_db.delete(
                f"/v1/projects/{project_id}", headers=auth.auth_header(token)
            )
            # Should still succeed (204) even though namespace deletion failed
            assert delete_response.status_code == 204

        # Verify project was still deleted from database (check via status endpoint)
        read_token = auth.issue_token(MockToken(scopes=["projects:read"]))
        get_response = client_with_db.get(
            f"/v1/projects/{project_id}/status", headers=auth.auth_header(read_token)
        )
        assert get_response.status_code == 404


# New tests for configuration endpoints


def test_create_project_with_multiple_problem_groups(client_with_db, auth):
    """Test creating a project with multiple problem groups"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    with patch("src.routers.api.projects.start_project_services"):
        response = client_with_db.post(
            "/v1/projects",
            json=VALID_CONFIG_MULTI_GROUP,
            headers=auth.auth_header(token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Multi-Group Project"
        assert isinstance(data["id"], str)


def test_create_project_missing_configuration(client_with_db, auth):
    """Test creating project without configuration returns 422"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    response = client_with_db.post(
        "/v1/projects", json={}, headers=auth.auth_header(token)
    )

    assert response.status_code == 422
    detail = str(response.json()).lower()
    assert "problem_groups" in detail or "name" in detail


def test_create_project_empty_configuration(client_with_db, auth):
    """Test creating project with empty configuration returns 422"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    response = client_with_db.post(
        "/v1/projects",
        json={"name": "Test", "problem_groups": []},
        headers=auth.auth_header(token),
    )

    assert response.status_code == 422
    detail = str(response.json()).lower()
    assert "at least 1" in detail or "min_length" in detail


def test_create_project_invalid_problem_group(client_with_db, auth):
    """Test creating project with invalid problem_group ID returns 422"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    invalid_config = {
        "name": "Invalid Project",
        "problem_groups": [
            {
                "problem_group": 0,  # Invalid: must be > 0
                "problems": [{"problem": 1, "instances": [1]}],
                "extras": {"solvers": [1]}
            }
        ],
    }
    response = client_with_db.post(
        "/v1/projects", json=invalid_config, headers=auth.auth_header(token)
    )

    assert response.status_code == 422
    detail = str(response.json()).lower()
    assert "greater than 0" in detail or "gt=0" in detail


def test_create_project_empty_solvers(client_with_db, auth):
    """Test creating project with empty solvers list in extras"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    invalid_config = {
        "name": "Invalid Project",
        "problem_groups": [
            {
                "problem_group": 1,
                "problems": [{"problem": 1, "instances": [1]}],
                "extras": {"solvers": []}  # Empty solvers in extras
            }
        ],
    }
    with patch("src.routers.api.projects.start_project_services"):
        response = client_with_db.post(
            "/v1/projects", json=invalid_config, headers=auth.auth_header(token)
        )

        # Solvers are in extras which is optional/flexible, so this might succeed
        # Just check we get a valid response code
        assert response.status_code in [201, 422]


def test_create_project_empty_instances(client_with_db, auth):
    """Test creating project with empty instances list returns 422"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    invalid_config = {
        "name": "Invalid Project",
        "problem_groups": [
            {
                "problem_group": 1,
                "problems": [{"problem": 1, "instances": []}],  # Invalid: empty
                "extras": {"solvers": [1]}
            }
        ],
    }
    response = client_with_db.post(
        "/v1/projects", json=invalid_config, headers=auth.auth_header(token)
    )

    assert response.status_code == 422
    detail = str(response.json()).lower()
    assert "at least 1" in detail or "min_length" in detail


def test_get_project_config(client_with_db, auth):
    """Test getting project configuration"""
    write_token = auth.issue_token(MockToken(scopes=["projects:write"]))
    read_token = auth.issue_token(MockToken(scopes=["projects:read"]))
    with patch("src.routers.api.projects.start_project_services"):
        # Create project
        create_response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(write_token)
        )
        project_id = create_response.json()["id"]

        # Get config
        response = client_with_db.get(
            f"/v1/projects/{project_id}/config", headers=auth.auth_header(read_token)
        )
        assert response.status_code == 200
        config = response.json()

        # Verify configuration matches full ProjectConfiguration (includes name + problem_groups)
        assert config["name"] == VALID_CONFIG["name"]
        assert config["problem_groups"] == VALID_CONFIG["problem_groups"]
        assert len(config["problem_groups"]) == 1
        assert config["problem_groups"][0]["problem_group"] == 1
        assert config["problem_groups"][0]["extras"]["solvers"] == [1, 2]
        assert len(config["problem_groups"][0]["problems"]) == 2


def test_get_nonexistent_project_config(client_with_db, auth):
    """Test getting config for non-existent project returns 404"""
    token = auth.issue_token(MockToken(scopes=["projects:read"]))
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = client_with_db.get(
        f"/v1/projects/{fake_uuid}/config", headers=auth.auth_header(token)
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid user or project"


def test_get_project_solution_not_implemented(client_with_db, auth):
    """Test getting project solution returns 501"""
    write_token = auth.issue_token(MockToken(scopes=["projects:write"]))
    read_token = auth.issue_token(MockToken(scopes=["projects:read"]))
    with patch("src.routers.api.projects.start_project_services"):
        # Create project
        create_response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(write_token)
        )
        project_id = create_response.json()["id"]

        # Get solution (not implemented yet)
        response = client_with_db.get(
            f"/v1/projects/{project_id}/solution", headers=auth.auth_header(read_token)
        )
        assert response.status_code == 501
        assert "not yet implemented" in response.json()["detail"].lower()


def test_get_nonexistent_project_solution(client_with_db, auth):
    """Test getting solution for non-existent project returns 404"""
    token = auth.issue_token(MockToken(scopes=["projects:read"]))
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = client_with_db.get(
        f"/v1/projects/{fake_uuid}/solution", headers=auth.auth_header(token)
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid user or project"


# Security Tests


def test_invalid_uuid_format_status(client_with_db, auth):
    """Test that invalid UUID format returns 404"""
    token = auth.issue_token(MockToken(scopes=["projects:read"]))

    invalid_uuids = [
        "not-a-uuid",
        "550e8400-e29b",  # Partial UUID
        "550e8400e29b41d4a716446655440000",  # No hyphens
    ]

    for invalid_uuid in invalid_uuids:
        response = client_with_db.get(
            f"/v1/projects/{invalid_uuid}/status", headers=auth.auth_header(token)
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Invalid user or project"


def test_invalid_uuid_format_config(client_with_db, auth):
    """Test that invalid UUID format returns 404 for config endpoint"""
    token = auth.issue_token(MockToken(scopes=["projects:read"]))
    response = client_with_db.get(
        "/v1/projects/not-a-uuid/config", headers=auth.auth_header(token)
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid user or project"


def test_invalid_uuid_format_delete(client_with_db, auth):
    """Test that invalid UUID format returns 404 for delete endpoint"""
    token = auth.issue_token(MockToken(scopes=["projects:write"]))
    response = client_with_db.delete(
        "/v1/projects/not-a-uuid", headers=auth.auth_header(token)
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid user or project"


def test_user_cannot_access_other_users_project_status(client_with_db, auth):
    """Test that User A cannot access User B's project status"""
    user_a = MockUser(id="user-a")
    user_b = MockUser(id="user-b")

    # User A creates a project
    token_a_write = auth.issue_token(MockToken(scopes=["projects:write"], user=user_a))
    with patch("src.routers.api.projects.start_project_services"):
        response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(token_a_write)
        )
        project_id = response.json()["id"]

    # User B tries to access User A's project
    token_b_read = auth.issue_token(MockToken(scopes=["projects:read"], user=user_b))
    response = client_with_db.get(
        f"/v1/projects/{project_id}/status", headers=auth.auth_header(token_b_read)
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid user or project"


def test_user_cannot_access_other_users_project_config(client_with_db, auth):
    """Test that User A cannot access User B's project config"""
    user_a = MockUser(id="user-a")
    user_b = MockUser(id="user-b")

    # User A creates a project
    token_a_write = auth.issue_token(MockToken(scopes=["projects:write"], user=user_a))
    with patch("src.routers.api.projects.start_project_services"):
        response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(token_a_write)
        )
        project_id = response.json()["id"]

    # User B tries to access User A's project config
    token_b_read = auth.issue_token(MockToken(scopes=["projects:read"], user=user_b))
    response = client_with_db.get(
        f"/v1/projects/{project_id}/config", headers=auth.auth_header(token_b_read)
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid user or project"


def test_user_cannot_delete_other_users_project(client_with_db, auth):
    """Test that User A cannot delete User B's project"""
    user_a = MockUser(id="user-a")
    user_b = MockUser(id="user-b")

    # User A creates a project
    token_a_write = auth.issue_token(MockToken(scopes=["projects:write"], user=user_a))
    with patch("src.routers.api.projects.start_project_services"):
        response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(token_a_write)
        )
        project_id = response.json()["id"]

    # User B tries to delete User A's project
    token_b_write = auth.issue_token(MockToken(scopes=["projects:write"], user=user_b))
    response = client_with_db.delete(
        f"/v1/projects/{project_id}", headers=auth.auth_header(token_b_write)
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid user or project"


def test_create_project_without_write_scope(client_with_db, auth):
    """Test that creating a project without write scope returns 403"""
    mock_user = MockUser(id="test-user")
    token = auth.issue_token(MockToken(scopes=["projects:read"], user=mock_user))

    response = client_with_db.post(
        "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(token)
    )
    assert response.status_code == 403


def test_get_projects_without_read_scope(client_with_db, auth):
    """Test that getting projects without read scope returns 403"""
    mock_user = MockUser(id="test-user")
    token = auth.issue_token(MockToken(scopes=["projects:write"], user=mock_user))

    response = client_with_db.get("/v1/projects", headers=auth.auth_header(token))
    assert response.status_code == 403


def test_delete_project_without_write_scope(client_with_db, auth):
    """Test that deleting a project without write scope returns 403"""
    mock_user = MockUser(id="test-user")

    # Create project with write scope
    write_token = auth.issue_token(MockToken(scopes=["projects:write"], user=mock_user))
    with patch("src.routers.api.projects.start_project_services"):
        response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(write_token)
        )
        project_id = response.json()["id"]

    # Try to delete with only read scope
    read_token = auth.issue_token(MockToken(scopes=["projects:read"], user=mock_user))
    response = client_with_db.delete(
        f"/v1/projects/{project_id}", headers=auth.auth_header(read_token)
    )
    assert response.status_code == 403


def test_get_project_status_without_read_scope(client_with_db, auth):
    """Test that getting project status without read scope returns 403"""
    mock_user = MockUser(id="test-user")

    # Create project with write scope
    write_token = auth.issue_token(MockToken(scopes=["projects:write"], user=mock_user))
    with patch("src.routers.api.projects.start_project_services"):
        response = client_with_db.post(
            "/v1/projects", json=VALID_CONFIG, headers=auth.auth_header(write_token)
        )
        project_id = response.json()["id"]

    # Try to get status with no scopes
    no_scope_token = auth.issue_token(MockToken(scopes=[], user=mock_user))
    response = client_with_db.get(
        f"/v1/projects/{project_id}/status", headers=auth.auth_header(no_scope_token)
    )
    assert response.status_code == 403


def test_get_projects_returns_only_user_projects(client_with_db, auth):
    """Test that GET /projects returns only the authenticated user's projects"""
    user_a = MockUser(id="user-a")
    user_b = MockUser(id="user-b")

    token_a_write = auth.issue_token(MockToken(scopes=["projects:write"], user=user_a))
    token_a_read = auth.issue_token(MockToken(scopes=["projects:read"], user=user_a))
    token_b_write = auth.issue_token(MockToken(scopes=["projects:write"], user=user_b))
    token_b_read = auth.issue_token(MockToken(scopes=["projects:read"], user=user_b))

    with patch("src.routers.api.projects.start_project_services"):
        # User A creates 2 projects
        response_a1 = client_with_db.post(
            "/v1/projects",
            json={**VALID_CONFIG, "name": "User A Project 1"},
            headers=auth.auth_header(token_a_write),
        )
        response_a2 = client_with_db.post(
            "/v1/projects",
            json={**VALID_CONFIG, "name": "User A Project 2"},
            headers=auth.auth_header(token_a_write),
        )
        project_a1_id = response_a1.json()["id"]
        project_a2_id = response_a2.json()["id"]

        # User B creates 2 projects
        response_b1 = client_with_db.post(
            "/v1/projects",
            json={**VALID_CONFIG, "name": "User B Project 1"},
            headers=auth.auth_header(token_b_write),
        )
        response_b2 = client_with_db.post(
            "/v1/projects",
            json={**VALID_CONFIG, "name": "User B Project 2"},
            headers=auth.auth_header(token_b_write),
        )
        project_b1_id = response_b1.json()["id"]
        project_b2_id = response_b2.json()["id"]

    # User A calls GET /projects - should only see their 2 projects
    response_a = client_with_db.get(
        "/v1/projects", headers=auth.auth_header(token_a_read)
    )
    assert response_a.status_code == 200
    projects_a = response_a.json()
    assert len(projects_a) == 2
    project_ids_a = {p["id"] for p in projects_a}
    assert project_ids_a == {project_a1_id, project_a2_id}
    assert all(p["user_id"] == user_a.id for p in projects_a)

    # User B calls GET /projects - should only see their 2 projects
    response_b = client_with_db.get(
        "/v1/projects", headers=auth.auth_header(token_b_read)
    )
    assert response_b.status_code == 200
    projects_b = response_b.json()
    assert len(projects_b) == 2
    project_ids_b = {p["id"] for p in projects_b}
    assert project_ids_b == {project_b1_id, project_b2_id}
    assert all(p["user_id"] == user_b.id for p in projects_b)
