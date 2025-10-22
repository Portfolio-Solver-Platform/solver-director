"""Tests for groups API endpoints"""


def test_create_group(client_with_db):
    """Test creating a new group"""
    response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test description"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-group"
    assert data["description"] == "Test description"
    assert "id" in data


def test_create_duplicate_group(client_with_db):
    """Test creating a duplicate group fails"""
    client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "duplicate", "description": "First"},
    )

    response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "duplicate", "description": "Second"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_all_groups(client_with_db):
    """Test getting all groups"""
    response = client_with_db.get("/api/solverdirector/v1/groups")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test", "description": "test description"},
    )
    response = client_with_db.get("api/solverdirector/v1/groups")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_group_by_id(client_with_db):
    """Test getting a specific group"""
    create_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "get-test", "description": "Get test"},
    )
    group_id = create_response.json()["id"]

    response = client_with_db.get(f"/api/solverdirector/v1/groups/{group_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == group_id
    assert data["name"] == "get-test"


def test_get_nonexistent_group(client_with_db):
    """Test getting a group that doesn't exist"""
    response = client_with_db.get("/api/solverdirector/v1/groups/99999")
    assert response.status_code == 404


def test_create_group_missing_name(client_with_db):
    """Test creating group without name fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/groups", json={"description": "No name provided"}
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_group_empty_name(client_with_db):
    """Test creating group with empty name fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/groups", json={"name": "", "description": "Empty name"}
    )
    assert response.status_code == 422


def test_create_group_whitespace_name(client_with_db):
    """Test creating group with whitespace-only name fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "   ", "description": "Whitespace name"},
    )
    assert response.status_code == 422


def test_create_group_invalid_name_type(client_with_db):
    """Test creating group with wrong name data type"""
    response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": 123, "description": "Name is number"},
    )
    assert response.status_code == 422


def test_create_group_null_name(client_with_db):
    """Test creating group with null name fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/groups", json={"name": None, "description": "Null name"}
    )
    assert response.status_code == 422


def test_create_group_invalid_description_type(client_with_db):
    """Test creating group with wrong description data type"""
    response = client_with_db.post(
        "/api/solverdirector/v1/groups", json={"name": "test", "description": 123}
    )
    assert response.status_code == 422


def test_delete_group(client_with_db):
    """Test deleting an existing group"""
    create_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "delete-test", "description": "To be deleted"},
    )
    group_id = create_response.json()["id"]

    response = client_with_db.delete(f"/api/solverdirector/v1/groups/{group_id}")
    assert response.status_code == 204

    # verify it is gone
    get_response = client_with_db.get(f"/api/solverdirector/v1/groups/{group_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_group(client_with_db):
    """Test deleting a non-existent group returns 404"""
    response = client_with_db.delete("/api/solverdirector/v1/groups/99999")
    assert response.status_code == 404


def test_delete_group_twice(client_with_db):
    """Test deleting the same group twice fails on second attempt"""
    create_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "double-delete", "description": "Delete twice"},
    )
    group_id = create_response.json()["id"]

    response = client_with_db.delete(f"/api/solverdirector/v1/groups/{group_id}")
    assert response.status_code == 204

    response = client_with_db.delete(f"/api/solverdirector/v1/groups/{group_id}")
    assert response.status_code == 404
