"""Tests for groups API endpoints"""

from src.models import Solver, SolverImage


def test_create_group(authed_client_with_db):
    """Test creating a new group"""
    response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test description"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-group"
    assert data["description"] == "Test description"
    assert "id" in data


def test_create_duplicate_group(authed_client_with_db):
    """Test creating a duplicate group fails"""
    authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "duplicate", "description": "First"},
    )

    response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "duplicate", "description": "Second"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_all_groups(authed_client_with_db):
    """Test getting all groups"""
    response = authed_client_with_db.get("/api/solverdirector/v1/groups")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test", "description": "test description"},
    )
    response = authed_client_with_db.get("api/solverdirector/v1/groups")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_group_by_id(authed_client_with_db):
    """Test getting a specific group"""
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "get-test", "description": "Get test"},
    )
    group_id = create_response.json()["id"]

    response = authed_client_with_db.get(f"/api/solverdirector/v1/groups/{group_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == group_id
    assert data["name"] == "get-test"


def test_get_nonexistent_group(authed_client_with_db):
    """Test getting a group that doesn't exist"""
    response = authed_client_with_db.get("/api/solverdirector/v1/groups/99999")
    assert response.status_code == 404


def test_create_group_missing_name(authed_client_with_db):
    """Test creating group without name fails"""
    response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups", json={"description": "No name provided"}
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_group_empty_name(authed_client_with_db):
    """Test creating group with empty name fails"""
    response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups", json={"name": "", "description": "Empty name"}
    )
    assert response.status_code == 422


def test_create_group_whitespace_name(authed_client_with_db):
    """Test creating group with whitespace-only name fails"""
    response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "   ", "description": "Whitespace name"},
    )
    assert response.status_code == 422


def test_create_group_invalid_name_type(authed_client_with_db):
    """Test creating group with wrong name data type"""
    response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": 123, "description": "Name is number"},
    )
    assert response.status_code == 422


def test_create_group_null_name(authed_client_with_db):
    """Test creating group with null name fails"""
    response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups", json={"name": None, "description": "Null name"}
    )
    assert response.status_code == 422


def test_create_group_invalid_description_type(authed_client_with_db):
    """Test creating group with wrong description data type"""
    response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups", json={"name": "test", "description": 123}
    )
    assert response.status_code == 422


def test_delete_group(authed_client_with_db):
    """Test deleting an existing group"""
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "delete-test", "description": "To be deleted"},
    )
    group_id = create_response.json()["id"]

    response = authed_client_with_db.delete(f"/api/solverdirector/v1/groups/{group_id}")
    assert response.status_code == 204

    # verify it is gone
    get_response = authed_client_with_db.get(f"/api/solverdirector/v1/groups/{group_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_group(authed_client_with_db):
    """Test deleting a non-existent group returns 404"""
    response = authed_client_with_db.delete("/api/solverdirector/v1/groups/99999")
    assert response.status_code == 404


def test_delete_group_twice(authed_client_with_db):
    """Test deleting the same group twice fails on second attempt"""
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "double-delete", "description": "Delete twice"},
    )
    group_id = create_response.json()["id"]

    response = authed_client_with_db.delete(f"/api/solverdirector/v1/groups/{group_id}")
    assert response.status_code == 204

    response = authed_client_with_db.delete(f"/api/solverdirector/v1/groups/{group_id}")
    assert response.status_code == 404


# PATCH /groups/{group_id} tests
def test_update_group_name_only(authed_client_with_db, test_db):
    """Test updating only group name"""
    # Create group
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Original Name", "description": "Test"},
    )
    group_id = create_response.json()["id"]

    # Update name only
    update_response = authed_client_with_db.patch(
        f"/api/solverdirector/v1/groups/{group_id}",
        json={"name": "Updated Name"},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Test"  # Unchanged


def test_update_group_description_only(authed_client_with_db, test_db):
    """Test updating only group description"""
    # Create group
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Test Group", "description": "Original Description"},
    )
    group_id = create_response.json()["id"]

    # Update description only
    update_response = authed_client_with_db.patch(
        f"/api/solverdirector/v1/groups/{group_id}",
        json={"description": "Updated Description"},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Test Group"  # Unchanged
    assert data["description"] == "Updated Description"


def test_update_group_solvers_only(authed_client_with_db, test_db):
    """Test updating only group solvers"""
    # Create group
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Test Group", "description": "Test"},
    )
    group_id = create_response.json()["id"]

    # Create solvers
    solver_image1 = SolverImage(
        image_name="solver1", image_path="ghcr.io/portfolio-solver-platform/solver1:latest"
    )
    test_db.add(solver_image1)
    test_db.flush()

    solver1 = Solver(name="solver1", solver_image_id=solver_image1.id)
    test_db.add(solver1)

    solver_image2 = SolverImage(
        image_name="solver2", image_path="ghcr.io/portfolio-solver-platform/solver2:latest"
    )
    test_db.add(solver_image2)
    test_db.flush()

    solver2 = Solver(name="solver2", solver_image_id=solver_image2.id)
    test_db.add(solver2)
    test_db.commit()

    # Update solvers only
    update_response = authed_client_with_db.patch(
        f"/api/solverdirector/v1/groups/{group_id}",
        json={"solver_ids": [solver1.id, solver2.id]},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Test Group"  # Unchanged
    assert set(data["solver_ids"]) == {solver1.id, solver2.id}


def test_update_group_all_fields(authed_client_with_db, test_db):
    """Test updating name, description, and solvers"""
    # Create group
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Original", "description": "Original Desc"},
    )
    group_id = create_response.json()["id"]

    # Create solver
    solver_image = SolverImage(
        image_name="solver", image_path="ghcr.io/portfolio-solver-platform/solver:latest"
    )
    test_db.add(solver_image)
    test_db.flush()

    solver = Solver(name="solver", solver_image_id=solver_image.id)
    test_db.add(solver)
    test_db.commit()

    # Update all fields
    update_response = authed_client_with_db.patch(
        f"/api/solverdirector/v1/groups/{group_id}",
        json={
            "name": "Updated",
            "description": "Updated Desc",
            "solver_ids": [solver.id],
        },
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Updated"
    assert data["description"] == "Updated Desc"
    assert data["solver_ids"] == [solver.id]


def test_update_group_empty_name(authed_client_with_db, test_db):
    """Test updating with empty name fails"""
    # Create group
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Original", "description": "Test"},
    )
    group_id = create_response.json()["id"]

    # Try to update with empty name
    update_response = authed_client_with_db.patch(
        f"/api/solverdirector/v1/groups/{group_id}",
        json={"name": "   "},
    )
    assert update_response.status_code == 422


def test_update_group_duplicate_name(authed_client_with_db, test_db):
    """Test updating to duplicate name fails"""
    # Create two groups
    authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Group 1", "description": "Test"},
    )

    create_response2 = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Group 2", "description": "Test"},
    )
    group2_id = create_response2.json()["id"]

    # Try to update group 2 to have same name as group 1
    update_response = authed_client_with_db.patch(
        f"/api/solverdirector/v1/groups/{group2_id}",
        json={"name": "Group 1"},
    )
    assert update_response.status_code == 400
    assert "already exists" in update_response.json()["detail"]


def test_update_group_nonexistent_solvers(authed_client_with_db, test_db):
    """Test updating with non-existent solvers fails"""
    # Create group
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Test Group", "description": "Test"},
    )
    group_id = create_response.json()["id"]

    # Try to update with non-existent solver
    update_response = authed_client_with_db.patch(
        f"/api/solverdirector/v1/groups/{group_id}",
        json={"solver_ids": [99999]},
    )
    assert update_response.status_code == 404
    assert "99999" in update_response.json()["detail"]


def test_update_group_duplicate_solver_ids(authed_client_with_db, test_db):
    """Test updating with duplicate solver_ids deduplicates them"""
    # Create group
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Test Group", "description": "Test"},
    )
    group_id = create_response.json()["id"]

    # Create solver
    solver_image = SolverImage(
        image_name="solver", image_path="ghcr.io/portfolio-solver-platform/solver:latest"
    )
    test_db.add(solver_image)
    test_db.flush()

    solver = Solver(name="solver", solver_image_id=solver_image.id)
    test_db.add(solver)
    test_db.commit()

    # Update with duplicate solver_ids
    update_response = authed_client_with_db.patch(
        f"/api/solverdirector/v1/groups/{group_id}",
        json={"solver_ids": [solver.id, solver.id, solver.id]},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    # Should be deduplicated
    assert data["solver_ids"] == [solver.id]


def test_update_nonexistent_group(authed_client_with_db, test_db):
    """Test updating non-existent group fails"""
    update_response = authed_client_with_db.patch(
        "/api/solverdirector/v1/groups/99999",
        json={"name": "New Name"},
    )
    assert update_response.status_code == 404
    assert "not found" in update_response.json()["detail"].lower()


def test_update_group_no_fields(authed_client_with_db, test_db):
    """Test updating with no fields fails"""
    # Create group
    create_response = authed_client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "Test Group", "description": "Test"},
    )
    group_id = create_response.json()["id"]

    # Try to update with no fields
    update_response = authed_client_with_db.patch(
        f"/api/solverdirector/v1/groups/{group_id}",
        json={},
    )
    assert update_response.status_code == 422
    assert "at least one field" in update_response.json()["detail"].lower()
