"""Tests for instances API endpoints"""

from io import BytesIO


def test_upload_instance(client_with_db):
    """Test uploading an instance file"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    problem_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Test Problem", "group_id": group_id},
    )
    problem_id = problem_response.json()["id"]

    # Upload instance
    file_content = b"This is a test instance file"
    response = client_with_db.post(
        f"/api/solverdirector/v1/problems/{problem_id}/instances",
        files={"file": ("instance.dzn", BytesIO(file_content), "text/plain")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["problem_id"] == problem_id
    assert data["filename"] == "instance.dzn"
    assert data["content_type"] == "text/plain"
    assert data["file_size"] == len(file_content)
    assert "id" in data
    assert "uploaded_at" in data


def test_upload_instance_to_nonexistent_problem(client_with_db):
    """Test uploading instance to non-existent problem returns 404"""
    response = client_with_db.post(
        "/api/solverdirector/v1/problems/99999/instances",
        files={"file": ("instance.dzn", BytesIO(b"content"), "text/plain")},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_upload_instance_empty_file(client_with_db):
    """Test uploading empty instance file fails"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    problem_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Test Problem", "group_id": group_id},
    )
    problem_id = problem_response.json()["id"]

    # Try to upload empty file
    response = client_with_db.post(
        f"/api/solverdirector/v1/problems/{problem_id}/instances",
        files={"file": ("empty.dzn", BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


def test_upload_instance_missing_file(client_with_db):
    """Test uploading instance without file fails"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    problem_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Test Problem", "group_id": group_id},
    )
    problem_id = problem_response.json()["id"]

    # Try to upload without file
    response = client_with_db.post(
        f"/api/solverdirector/v1/problems/{problem_id}/instances"
    )
    assert response.status_code == 422


def test_get_instances_for_problem(client_with_db):
    """Test getting all instances for a specific problem"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    problem_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Test Problem", "group_id": group_id},
    )
    problem_id = problem_response.json()["id"]

    # Upload two instances
    client_with_db.post(
        f"/api/solverdirector/v1/problems/{problem_id}/instances",
        files={"file": ("instance1.dzn", BytesIO(b"content1"), "text/plain")},
    )
    client_with_db.post(
        f"/api/solverdirector/v1/problems/{problem_id}/instances",
        files={"file": ("instance2.dzn", BytesIO(b"content2"), "text/plain")},
    )

    # Get all instances for problem
    response = client_with_db.get(
        f"/api/solverdirector/v1/problems/{problem_id}/instances"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["filename"] == "instance1.dzn"
    assert data[0]["problem_id"] == problem_id
    assert data[1]["filename"] == "instance2.dzn"
    assert data[1]["problem_id"] == problem_id


def test_get_instances_empty_problem(client_with_db):
    """Test getting instances for problem with no instances returns empty list"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    problem_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Test Problem", "group_id": group_id},
    )
    problem_id = problem_response.json()["id"]

    # Get instances - should be empty
    response = client_with_db.get(
        f"/api/solverdirector/v1/problems/{problem_id}/instances"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


def test_get_instances_nonexistent_problem(client_with_db):
    """Test getting instances for non-existent problem returns 404"""
    response = client_with_db.get("/api/solverdirector/v1/problems/99999/instances")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_instances_multiple_problems(client_with_db):
    """Test that instances are correctly filtered by problem"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create two problems
    problem1_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Problem 1", "group_id": group_id},
    )
    problem1_id = problem1_response.json()["id"]

    problem2_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Problem 2", "group_id": group_id},
    )
    problem2_id = problem2_response.json()["id"]

    # Add instances to both problems
    client_with_db.post(
        f"/api/solverdirector/v1/problems/{problem1_id}/instances",
        files={"file": ("p1_instance.dzn", BytesIO(b"content1"), "text/plain")},
    )
    client_with_db.post(
        f"/api/solverdirector/v1/problems/{problem2_id}/instances",
        files={"file": ("p2_instance.dzn", BytesIO(b"content2"), "text/plain")},
    )

    # Get instances for problem1 - should only have 1
    response = client_with_db.get(
        f"/api/solverdirector/v1/problems/{problem1_id}/instances"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "p1_instance.dzn"
    assert data[0]["problem_id"] == problem1_id
