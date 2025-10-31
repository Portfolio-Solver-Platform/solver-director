"""Tests for projects API endpoints"""

from unittest.mock import patch, MagicMock


def test_create_project(client_with_db):
    """Test creating a new project"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        mock_start.return_value = "solver-controller-test-123"

        response = client_with_db.post("/api/solverdirector/v1/projects")

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == "sofus"
        assert data["solver_controller_id"] == "solver-controller-test-123"
        assert "id" in data
        assert "created_at" in data

        # Verify start_solver_controller was called with correct user_id
        mock_start.assert_called_once_with("sofus")


def test_get_all_projects(client_with_db):
    """Test getting all projects"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        mock_start.side_effect = ["controller-1", "controller-2"]

        # Create two projects
        client_with_db.post("/api/solverdirector/v1/projects")
        client_with_db.post("/api/solverdirector/v1/projects")

        # Get all projects
        response = client_with_db.get("/api/solverdirector/v1/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["solver_controller_id"] == "controller-1"
        assert data[1]["solver_controller_id"] == "controller-2"

# def test_get_all_projects(client_with_db, auth):
#     """Test getting all projects"""
#     token = auth.issue_token(MockToken(scopes=["projects:read"]))
#     with patch("src.routers.api.projects.start_solver_controller") as mock_start:
#         mock_start.side_effect = ["controller-1", "controller-2"]

#         # Create two projects
#         client_with_db.post("/api/solverdirector/v1/projects")
#         client_with_db.post("/api/solverdirector/v1/projects")

#         # Get all projects
#         response = client_with_db.get("/api/solverdirector/v1/projects", headers=auth.auth_header(token))
#         assert response.status_code == 200
#         data = response.json()
#         assert len(data) == 2
#         assert data[0]["solver_controller_id"] == "controller-1"
#         assert data[1]["solver_controller_id"] == "controller-2"


def test_get_projects_by_user_id(client_with_db):
    """Test filtering projects by user_id"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        mock_start.side_effect = ["controller-1", "controller-2"]

        # Create two projects (both will have user_id="sofus")
        client_with_db.post("/api/solverdirector/v1/projects")
        client_with_db.post("/api/solverdirector/v1/projects")

        # Get projects for specific user
        response = client_with_db.get("/api/solverdirector/v1/projects?user_id=sofus")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(p["user_id"] == "sofus" for p in data)


def test_get_projects_by_nonexistent_user(client_with_db):
    """Test getting projects for non-existent user returns empty list"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        mock_start.return_value = "controller-1"

        # Create a project
        client_with_db.post("/api/solverdirector/v1/projects")

        # Query for different user
        response = client_with_db.get(
            "/api/solverdirector/v1/projects?user_id=nonexistent"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


def test_get_project_by_id(client_with_db):
    """Test getting a specific project by id with status"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        mock_start.return_value = "controller-test-123"

        # Create project
        create_response = client_with_db.post("/api/solverdirector/v1/projects")
        project_id = create_response.json()["id"]

        # Mock the status response
        with patch("src.routers.api.projects.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "running": True,
                "jobs": 5,
                "completed": 3,
            }
            mock_get.return_value = mock_response

            # Get project by id
            response = client_with_db.get(
                f"/api/solverdirector/v1/projects/{project_id}"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == project_id
            assert data["solver_controller_id"] == "controller-test-123"
            assert data["user_id"] == "sofus"
            assert "status" in data
            assert data["status"]["running"] is True
            assert data["status"]["jobs"] == 5
            assert data["status"]["completed"] == 3


def test_get_nonexistent_project(client_with_db):
    """Test getting non-existent project returns 404"""
    response = client_with_db.get("/api/solverdirector/v1/projects/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_project_solver_controller_failure(client_with_db):
    """Test that project creation fails if solver controller fails to start"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        mock_start.side_effect = Exception("Failed to start solver controller")

        response = client_with_db.post("/api/solverdirector/v1/projects")

        # Should return 500 with error message
        assert response.status_code == 500
        assert "failed to start solver controller" in response.json()["detail"].lower()


def test_unique_solver_controller_id(client_with_db):
    """Test that solver_controller_id must be unique"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        # First project succeeds
        mock_start.return_value = "duplicate-controller-id"
        response1 = client_with_db.post("/api/solverdirector/v1/projects")
        assert response1.status_code == 201

        # Second project with same solver_controller_id should fail with 409 Conflict
        response2 = client_with_db.post("/api/solverdirector/v1/projects")
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()


def test_get_project_status_connection_error(client_with_db):
    """Test that getting project returns 503 when solver controller is unreachable"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        mock_start.return_value = "controller-unreachable"

        # Create project
        create_response = client_with_db.post("/api/solverdirector/v1/projects")
        project_id = create_response.json()["id"]

        # Mock connection error
        with patch("src.routers.api.projects.requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            # Get project by id - should fail with 503
            response = client_with_db.get(
                f"/api/solverdirector/v1/projects/{project_id}"
            )
            assert response.status_code == 503
            assert "cannot connect" in response.json()["detail"].lower()


# DELETE /projects/{project_id} tests
def test_delete_project_success(client_with_db):
    """Test successfully deleting a project"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        mock_start.return_value = "controller-to-delete"

        # Create project
        create_response = client_with_db.post("/api/solverdirector/v1/projects")
        project_id = create_response.json()["id"]

        # Delete project
        with patch("src.routers.api.projects.stop_solver_controller") as mock_stop:
            delete_response = client_with_db.delete(
                f"/api/solverdirector/v1/projects/{project_id}"
            )
            assert delete_response.status_code == 204

            # Verify stop_solver_controller was called with correct namespace
            mock_stop.assert_called_once_with("controller-to-delete")

        # Verify project no longer exists
        get_response = client_with_db.get(
            f"/api/solverdirector/v1/projects/{project_id}"
        )
        assert get_response.status_code == 404


def test_delete_nonexistent_project(client_with_db):
    """Test deleting a non-existent project returns 404"""
    delete_response = client_with_db.delete("/api/solverdirector/v1/projects/99999")
    assert delete_response.status_code == 404
    assert "not found" in delete_response.json()["detail"].lower()


def test_delete_project_namespace_failure(client_with_db):
    """Test that project is deleted even if namespace deletion fails"""
    with patch("src.routers.api.projects.start_solver_controller") as mock_start:
        mock_start.return_value = "controller-test"

        # Create project
        create_response = client_with_db.post("/api/solverdirector/v1/projects")
        project_id = create_response.json()["id"]

        # Delete project with namespace deletion failure
        with patch("src.routers.api.projects.stop_solver_controller") as mock_stop:
            mock_stop.side_effect = Exception("Namespace not found")

            delete_response = client_with_db.delete(
                f"/api/solverdirector/v1/projects/{project_id}"
            )
            # Should still succeed (204) even though namespace deletion failed
            assert delete_response.status_code == 204

        # Verify project was still deleted from database
        get_response = client_with_db.get(
            f"/api/solverdirector/v1/projects/{project_id}"
        )
        assert get_response.status_code == 404
