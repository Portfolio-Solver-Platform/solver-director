"""Tests for problems API endpoints"""
from io import BytesIO


def test_upload_problem(client_with_db):
    """Test uploading a problem file"""

    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    file_content = b"This is a test problem file"
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Test Problem", "group_id": group_id},
        files={"file": ("problem.txt", BytesIO(file_content), "text/plain")}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Problem"
    assert data["filename"] == "problem.txt"
    assert data["content_type"] == "text/plain"
    assert data["file_size"] == len(file_content)
    assert data["group_id"] == group_id
    assert data["is_instances_self_contained"] is False  # File provided
    assert "id" in data
    assert "uploaded_at" in data


def test_get_problem_metadata(client_with_db):
    """Test getting problem metadata without file content"""

    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    upload_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Metadata Test", "group_id": group_id},
        files={"file": ("test.txt", BytesIO(b"content"), "text/plain")}
    )
    problem_id = upload_response.json()["id"]

    # Get metadata
    response = client_with_db.get(f"/api/solverdirector/v1/problems/{problem_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == problem_id
    assert data["name"] == "Metadata Test"
    assert data["filename"] == "test.txt"
    assert data["is_instances_self_contained"] is False
    assert "file_data" not in data  # Should not include binary data


def test_download_problem_file(client_with_db):
    """Test downloading problem file"""
    # Create group and upload problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    file_content = b"This is the actual problem content"
    upload_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Download Test", "group_id": group_id},
        files={"file": ("download.txt", BytesIO(file_content), "text/plain")}
    )
    problem_id = upload_response.json()["id"]

    # Download file
    response = client_with_db.get(f"/api/solverdirector/v1/problems/{problem_id}/download")
    assert response.status_code == 200
    assert response.content == file_content
    assert response.headers["content-type"].startswith("text/plain")
    assert 'attachment; filename="download.txt"' in response.headers["content-disposition"]


def test_upload_problem_invalid_group(client_with_db):
    """Test uploading problem with non-existent group fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Invalid Group", "group_id": 99999},
        files={"file": ("test.txt", BytesIO(b"content"), "text/plain")}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_upload_problem_no_file(client_with_db):
    """Test uploading problem without file (self-contained instances)"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    # Upload without file - should succeed (self-contained)
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Self-Contained Problem", "group_id": group_id}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Self-Contained Problem"
    assert data["filename"] is None
    assert data["file_size"] is None
    assert data["is_instances_self_contained"] is True  # No file provided


def test_upload_problem_empty_file(client_with_db):
    """Test uploading empty file fails"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    # Upload empty file
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Empty File", "group_id": group_id},
        files={"file": ("empty.txt", BytesIO(b""), "text/plain")}
    )
    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


def test_get_nonexistent_problem(client_with_db):
    """Test getting non-existent problem returns 404"""
    response = client_with_db.get("/api/solverdirector/v1/problems/99999")
    assert response.status_code == 404


def test_download_nonexistent_problem(client_with_db):
    """Test downloading non-existent problem returns 404"""
    response = client_with_db.get("/api/solverdirector/v1/problems/99999/download")
    assert response.status_code == 404


def test_download_self_contained_problem(client_with_db):
    """Test downloading self-contained problem (no file) returns 404"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    # Upload problem without file (self-contained)
    upload_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Self-Contained", "group_id": group_id}
    )
    problem_id = upload_response.json()["id"]

    # Try to download - should fail with 404
    response = client_with_db.get(f"/api/solverdirector/v1/problems/{problem_id}/download")
    assert response.status_code == 404
    assert "self-contained" in response.json()["detail"].lower()


# Validation tests
def test_upload_problem_empty_name(client_with_db):
    """Test uploading problem with empty name fails"""
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "", "group_id": group_id},
        files={"file": ("test.txt", BytesIO(b"content"), "text/plain")}
    )
    assert response.status_code == 422
    assert "name" in response.json()["detail"].lower()


def test_upload_problem_whitespace_name(client_with_db):
    """Test uploading problem with whitespace-only name fails"""
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "   ", "group_id": group_id},
        files={"file": ("test.txt", BytesIO(b"content"), "text/plain")}
    )
    assert response.status_code == 422
    assert "name" in response.json()["detail"].lower()


def test_upload_problem_missing_name(client_with_db):
    """Test uploading problem without name fails"""
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"group_id": group_id},
        files={"file": ("test.txt", BytesIO(b"content"), "text/plain")}
    )
    assert response.status_code == 422


def test_upload_problem_missing_group_id(client_with_db):
    """Test uploading problem without group_id fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Test Problem"},
        files={"file": ("test.txt", BytesIO(b"content"), "text/plain")}
    )
    assert response.status_code == 422


def test_upload_problem_invalid_group_id_type(client_with_db):
    """Test uploading problem with invalid group_id type fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Test Problem", "group_id": "not-a-number"},
        files={"file": ("test.txt", BytesIO(b"content"), "text/plain")}
    )
    assert response.status_code == 422


def test_get_problems_by_group(client_with_db):
    """Test getting all problems for a specific group"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    # Upload two problems
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Problem 1", "group_id": group_id},
        files={"file": ("p1.txt", BytesIO(b"content1"), "text/plain")}
    )
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Problem 2", "group_id": group_id}
    )

    # Get all problems for group
    response = client_with_db.get(f"/api/solverdirector/v1/problems?group_id={group_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Problem 1"
    assert data[0]["is_instances_self_contained"] is False
    assert data[1]["name"] == "Problem 2"
    assert data[1]["is_instances_self_contained"] is True


def test_get_problems_nonexistent_group(client_with_db):
    """Test getting problems for non-existent group returns 404"""
    response = client_with_db.get("/api/solverdirector/v1/problems?group_id=99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_problems_empty_group(client_with_db):
    """Test getting problems for group with no problems returns empty list"""
    # Create empty group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "empty-group", "description": "Test"}
    )
    group_id = group_response.json()["id"]

    # Get problems - should be empty
    response = client_with_db.get(f"/api/solverdirector/v1/problems?group_id={group_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


def test_get_problems_multiple_groups(client_with_db):
    """Test that problems are correctly filtered by group"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"}
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"}
    )
    group2_id = group2_response.json()["id"]

    # Add problems to both groups
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Group1 Problem", "group_id": group1_id}
    )
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        data={"name": "Group2 Problem", "group_id": group2_id}
    )

    # Get problems for group1 - should only have 1
    response = client_with_db.get(f"/api/solverdirector/v1/problems?group_id={group1_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Group1 Problem"
    assert data[0]["group_id"] == group1_id
