"""Tests for problems API endpoints"""

from io import BytesIO


def test_upload_problem(client_with_db):
    """Test uploading a problem file"""

    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Step 1: Create problem with JSON
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Test Problem", "group_ids": [group_id]},
    )
    assert response.status_code == 201
    problem_id = response.json()["id"]

    # Step 2: Upload file
    file_content = b"This is a test problem file"
    file_response = client_with_db.put(
        f"/api/solverdirector/v1/problems/{problem_id}/file",
        files={"file": ("problem.txt", BytesIO(file_content), "text/plain")},
    )

    assert file_response.status_code == 200
    data = file_response.json()
    assert data["name"] == "Test Problem"
    assert data["filename"] == "problem.txt"
    assert data["content_type"] == "text/plain"
    assert data["file_size"] == len(file_content)
    assert data["group_ids"] == [group_id]
    assert data["is_instances_self_contained"] is False  # File provided
    assert "id" in data
    assert "uploaded_at" in data


def test_get_problem_metadata(client_with_db):
    """Test getting problem metadata without file content"""

    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create problem
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Metadata Test", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Upload file
    client_with_db.put(
        f"/api/solverdirector/v1/problems/{problem_id}/file",
        files={"file": ("test.txt", BytesIO(b"content"), "text/plain")},
    )

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
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create problem
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Download Test", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Upload file
    file_content = b"This is the actual problem content"
    client_with_db.put(
        f"/api/solverdirector/v1/problems/{problem_id}/file",
        files={"file": ("download.txt", BytesIO(file_content), "text/plain")},
    )

    # Download file
    response = client_with_db.get(f"/api/solverdirector/v1/problems/{problem_id}/file")
    assert response.status_code == 200
    assert response.content == file_content
    assert response.headers["content-type"].startswith("text/plain")
    assert (
        'attachment; filename="download.txt"' in response.headers["content-disposition"]
    )


def test_upload_problem_invalid_group(client_with_db):
    """Test uploading problem with non-existent group fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Invalid Group", "group_ids": [99999]},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_upload_problem_no_file(client_with_db):
    """Test uploading problem without file (self-contained instances)"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create without file - should succeed (self-contained)
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Self-Contained Problem", "group_ids": [group_id]},
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
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create problem
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Empty File", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Upload empty file
    response = client_with_db.put(
        f"/api/solverdirector/v1/problems/{problem_id}/file",
        files={"file": ("empty.txt", BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


def test_get_nonexistent_problem(client_with_db):
    """Test getting non-existent problem returns 404"""
    response = client_with_db.get("/api/solverdirector/v1/problems/99999")
    assert response.status_code == 404


def test_download_nonexistent_problem(client_with_db):
    """Test downloading non-existent problem returns 404"""
    response = client_with_db.get("/api/solverdirector/v1/problems/99999/file")
    assert response.status_code == 404


def test_download_self_contained_problem(client_with_db):
    """Test downloading self-contained problem (no file) returns 404"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create problem without file (self-contained)
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Self-Contained", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Try to download - should fail with 404
    response = client_with_db.get(f"/api/solverdirector/v1/problems/{problem_id}/file")
    assert response.status_code == 404
    assert "self-contained" in response.json()["detail"].lower()


# Validation tests
def test_upload_problem_empty_name(client_with_db):
    """Test uploading problem with empty name fails"""
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "", "group_ids": [group_id]},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    # Detail can be either a string or a list of validation errors
    if isinstance(detail, list):
        assert any("name" in str(error).lower() for error in detail)
    else:
        assert "name" in detail.lower()


def test_upload_problem_whitespace_name(client_with_db):
    """Test uploading problem with whitespace-only name fails"""
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "   ", "group_ids": [group_id]},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    # Detail can be either a string or a list of validation errors
    if isinstance(detail, list):
        assert any("name" in str(error).lower() for error in detail)
    else:
        assert "name" in detail.lower()


def test_upload_problem_missing_name(client_with_db):
    """Test uploading problem without name fails"""
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"group_ids": [group_id]},
    )
    assert response.status_code == 422


def test_upload_problem_missing_group_id(client_with_db):
    """Test uploading problem without group_id fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Test Problem"},
    )
    assert response.status_code == 422


def test_upload_problem_invalid_group_id_type(client_with_db):
    """Test uploading problem with invalid group_id type fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Test Problem", "group_ids": ["not-a-number"]},
    )
    assert response.status_code == 422


def test_get_problems_by_group(client_with_db):
    """Test getting all problems for a specific group"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create two problems
    problem1_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Problem 1", "group_ids": [group_id]},
    )
    problem1_id = problem1_response.json()["id"]

    # Upload file for problem 1
    client_with_db.put(
        f"/api/solverdirector/v1/problems/{problem1_id}/file",
        files={"file": ("p1.txt", BytesIO(b"content1"), "text/plain")},
    )

    # Create problem 2 without file
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Problem 2", "group_ids": [group_id]},
    )

    # Get all problems for group
    response = client_with_db.get(
        f"/api/solverdirector/v1/problems?group_id={group_id}"
    )
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
        json={"name": "empty-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Get problems - should be empty
    response = client_with_db.get(
        f"/api/solverdirector/v1/problems?group_id={group_id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


def test_get_problems_filters_by_group(client_with_db):
    """Test that problems are correctly filtered by group"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    # Add problems to both groups
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Group1 Problem", "group_ids": [group1_id]},
    )
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Group2 Problem", "group_ids": [group2_id]},
    )

    # Get problems for group1 - should only have 1
    response = client_with_db.get(
        f"/api/solverdirector/v1/problems?group_id={group1_id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Group1 Problem"
    assert data[0]["group_ids"] == [group1_id]


def test_get_all_problems(client_with_db):
    """Test getting all problems without filtering by group"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    # Add problems to both groups
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Group1 Problem", "group_ids": [group1_id]},
    )
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Group2 Problem 1", "group_ids": [group2_id]},
    )
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Group2 Problem 2", "group_ids": [group2_id]},
    )

    # Get all problems without filtering - should have all 3
    response = client_with_db.get("/api/solverdirector/v1/problems")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    problem_names = {p["name"] for p in data}
    assert problem_names == {"Group1 Problem", "Group2 Problem 1", "Group2 Problem 2"}


def test_upload_duplicate_problem(client_with_db):
    """Test uploading problem with duplicate name fails"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create first problem
    response1 = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Duplicate Problem", "group_ids": [group_id]},
    )
    assert response1.status_code == 201

    # Try to create problem with same name - should fail
    response2 = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Duplicate Problem", "group_ids": [group_id]},
    )
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"].lower()


# Many-to-many relationship tests
def test_upload_problem_with_multiple_groups(client_with_db):
    """Test uploading a problem with multiple groups"""
    # Create three groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    group3_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group3", "description": "Group 3"},
    )
    group3_id = group3_response.json()["id"]

    # Create problem with all three groups
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={
            "name": "Multi-Group Problem",
            "group_ids": [group1_id, group2_id, group3_id],
        },
    )
    assert response.status_code == 201
    problem_id = response.json()["id"]

    # Upload file
    file_response = client_with_db.put(
        f"/api/solverdirector/v1/problems/{problem_id}/file",
        files={"file": ("test.txt", BytesIO(b"content"), "text/plain")},
    )

    assert file_response.status_code == 200
    data = file_response.json()
    assert data["name"] == "Multi-Group Problem"
    assert set(data["group_ids"]) == {group1_id, group2_id, group3_id}

    # Verify problem appears when querying by each group
    for gid in [group1_id, group2_id, group3_id]:
        response = client_with_db.get(f"/api/solverdirector/v1/problems?group_id={gid}")
        assert response.status_code == 200
        problems = response.json()
        problem_ids = [p["id"] for p in problems]
        assert problem_id in problem_ids


def test_upload_problem_with_duplicate_group_ids(client_with_db):
    """Test uploading problem with duplicate group_ids deduplicates them"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    # Create problem with duplicate group IDs
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={
            "name": "Duplicate Groups",
            "group_ids": [group1_id, group1_id, group2_id],
        },
    )

    assert response.status_code == 201
    data = response.json()
    # Should deduplicate to only 2 groups
    assert set(data["group_ids"]) == {group1_id, group2_id}
    assert len(data["group_ids"]) == 2


def test_upload_problem_with_partially_invalid_groups(client_with_db):
    """Test uploading problem with some invalid group IDs fails"""
    # Create one valid group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "valid-group", "description": "Valid"},
    )
    group_id = group_response.json()["id"]

    # Try to create problem with mix of valid and invalid groups
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Partial Invalid", "group_ids": [group_id, 99999, 88888]},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_upload_problem_with_empty_string_group_ids(client_with_db):
    """Test uploading problem with empty list group_ids fails"""
    # Try with empty list
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Empty Groups", "group_ids": []},
    )
    assert response.status_code == 422


def test_problem_in_multiple_groups_query_filtering(client_with_db):
    """Test that problem in multiple groups appears in queries for each group"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    # Create problem in both groups
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Shared Problem", "group_ids": [group1_id, group2_id]},
    )
    assert response.status_code == 201
    problem_id = response.json()["id"]

    # Query by group1 - should include the problem
    response1 = client_with_db.get(
        f"/api/solverdirector/v1/problems?group_id={group1_id}"
    )
    assert response1.status_code == 200
    problems1 = response1.json()
    assert len(problems1) == 1
    assert problems1[0]["id"] == problem_id
    assert problems1[0]["name"] == "Shared Problem"

    # Query by group2 - should also include the problem
    response2 = client_with_db.get(
        f"/api/solverdirector/v1/problems?group_id={group2_id}"
    )
    assert response2.status_code == 200
    problems2 = response2.json()
    assert len(problems2) == 1
    assert problems2[0]["id"] == problem_id
    assert problems2[0]["name"] == "Shared Problem"


def test_delete_group_keeps_problem(client_with_db):
    """Test that deleting a group doesn't delete problems in other groups"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    # Create problem in both groups
    response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Persistent Problem", "group_ids": [group1_id, group2_id]},
    )
    assert response.status_code == 201
    problem_id = response.json()["id"]

    # Delete group1
    delete_response = client_with_db.delete(
        f"/api/solverdirector/v1/groups/{group1_id}"
    )
    assert delete_response.status_code == 204

    # Problem should still exist
    problem_response = client_with_db.get(
        f"/api/solverdirector/v1/problems/{problem_id}"
    )
    assert problem_response.status_code == 200
    problem_data = problem_response.json()
    assert problem_data["name"] == "Persistent Problem"
    # Should only have group2 now
    assert problem_data["group_ids"] == [group2_id]


def test_get_problem_by_id_with_multiple_groups(client_with_db):
    """Test getting problem by ID returns all associated group IDs"""
    # Create three groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    group3_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group3", "description": "Group 3"},
    )
    group3_id = group3_response.json()["id"]

    # Create problem with all three groups
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={
            "name": "Multi-Group Query Test",
            "group_ids": [group1_id, group2_id, group3_id],
        },
    )
    problem_id = create_response.json()["id"]

    # Get problem by ID
    response = client_with_db.get(f"/api/solverdirector/v1/problems/{problem_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Multi-Group Query Test"
    assert set(data["group_ids"]) == {group1_id, group2_id, group3_id}


# PATCH /problems/{id} tests
def test_update_problem_name_only(client_with_db):
    """Test updating only problem name"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Original Name", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Update name only
    update_response = client_with_db.patch(
        f"/api/solverdirector/v1/problems/{problem_id}",
        json={"name": "Updated Name"},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Updated Name"
    assert data["group_ids"] == [group_id]  # Groups unchanged


def test_update_problem_groups_only(client_with_db):
    """Test updating only problem groups"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    # Create problem with group1
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Test Problem", "group_ids": [group1_id]},
    )
    problem_id = create_response.json()["id"]

    # Update to use both groups
    update_response = client_with_db.patch(
        f"/api/solverdirector/v1/problems/{problem_id}",
        json={"group_ids": [group1_id, group2_id]},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Test Problem"  # Name unchanged
    assert set(data["group_ids"]) == {group1_id, group2_id}


def test_update_problem_both_name_and_groups(client_with_db):
    """Test updating both name and groups"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    # Create problem
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Original", "group_ids": [group1_id]},
    )
    problem_id = create_response.json()["id"]

    # Update both fields
    update_response = client_with_db.patch(
        f"/api/solverdirector/v1/problems/{problem_id}",
        json={"name": "Updated", "group_ids": [group2_id]},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Updated"
    assert data["group_ids"] == [group2_id]


def test_update_problem_empty_name(client_with_db):
    """Test updating with empty name fails"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Original", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Try to update with empty name
    update_response = client_with_db.patch(
        f"/api/solverdirector/v1/problems/{problem_id}",
        json={"name": "   "},
    )
    assert update_response.status_code == 422


def test_update_problem_duplicate_name(client_with_db):
    """Test updating to duplicate name fails"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create two problems
    client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Problem 1", "group_ids": [group_id]},
    )

    create_response2 = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Problem 2", "group_ids": [group_id]},
    )
    problem2_id = create_response2.json()["id"]

    # Try to update problem 2 to have same name as problem 1
    update_response = client_with_db.patch(
        f"/api/solverdirector/v1/problems/{problem2_id}",
        json={"name": "Problem 1"},
    )
    assert update_response.status_code == 400
    assert "already exists" in update_response.json()["detail"]


def test_update_problem_nonexistent_groups(client_with_db):
    """Test updating with non-existent groups fails"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Test Problem", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Try to update with non-existent group
    update_response = client_with_db.patch(
        f"/api/solverdirector/v1/problems/{problem_id}",
        json={"group_ids": [group_id, 99999]},
    )
    assert update_response.status_code == 404
    assert "99999" in update_response.json()["detail"]


def test_update_problem_empty_group_ids(client_with_db):
    """Test updating with empty group_ids list fails"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Test Problem", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Try to update with empty group_ids
    update_response = client_with_db.patch(
        f"/api/solverdirector/v1/problems/{problem_id}",
        json={"group_ids": []},
    )
    assert update_response.status_code == 422


def test_update_problem_duplicate_group_ids(client_with_db):
    """Test updating with duplicate group_ids deduplicates them"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    # Create problem
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Test Problem", "group_ids": [group1_id]},
    )
    problem_id = create_response.json()["id"]

    # Update with duplicate group_ids
    update_response = client_with_db.patch(
        f"/api/solverdirector/v1/problems/{problem_id}",
        json={"group_ids": [group1_id, group2_id, group1_id, group2_id]},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    # Should be deduplicated
    assert set(data["group_ids"]) == {group1_id, group2_id}
    assert len(data["group_ids"]) == 2


def test_update_nonexistent_problem(client_with_db):
    """Test updating non-existent problem fails"""
    update_response = client_with_db.patch(
        "/api/solverdirector/v1/problems/99999",
        json={"name": "New Name"},
    )
    assert update_response.status_code == 404
    assert "not found" in update_response.json()["detail"].lower()


def test_update_problem_no_fields(client_with_db):
    """Test updating with no fields fails"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Test Problem", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Try to update with no fields
    update_response = client_with_db.patch(
        f"/api/solverdirector/v1/problems/{problem_id}",
        json={},
    )
    assert update_response.status_code == 422
    assert "at least one field" in update_response.json()["detail"].lower()


# DELETE /problems/{id} tests
def test_delete_problem_success(client_with_db):
    """Test successfully deleting a problem"""
    # Create group and problem
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Problem to Delete", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Delete problem
    delete_response = client_with_db.delete(
        f"/api/solverdirector/v1/problems/{problem_id}"
    )
    assert delete_response.status_code == 204

    # Verify problem no longer exists
    get_response = client_with_db.get(
        f"/api/solverdirector/v1/problems/{problem_id}"
    )
    assert get_response.status_code == 404


def test_delete_problem_with_instances(client_with_db):
    """Test deleting a problem with instances (cascade delete)"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create problem with file
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Problem with Instances", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Upload file
    file_content = b"problem content"
    client_with_db.put(
        f"/api/solverdirector/v1/problems/{problem_id}/file",
        files={"file": ("problem.mzn", BytesIO(file_content), "text/plain")},
    )

    # Upload instances
    instance1_content = b"instance 1"
    instance1_response = client_with_db.post(
        f"/api/solverdirector/v1/problems/{problem_id}/instances",
        files={"file": ("instance1.dzn", BytesIO(instance1_content), "text/plain")},
    )
    _ = instance1_response.json()["id"]

    instance2_content = b"instance 2"
    instance2_response = client_with_db.post(
        f"/api/solverdirector/v1/problems/{problem_id}/instances",
        files={"file": ("instance2.dzn", BytesIO(instance2_content), "text/plain")},
    )
    _ = instance2_response.json()["id"]

    # Delete problem
    delete_response = client_with_db.delete(
        f"/api/solverdirector/v1/problems/{problem_id}"
    )
    assert delete_response.status_code == 204

    # Verify problem no longer exists
    get_problem_response = client_with_db.get(
        f"/api/solverdirector/v1/problems/{problem_id}"
    )
    assert get_problem_response.status_code == 404

    # Verify instances are also deleted
    get_instances_response = client_with_db.get(
        f"/api/solverdirector/v1/problems/{problem_id}/instances"
    )
    assert get_instances_response.status_code == 404


def test_delete_problem_with_multiple_groups(client_with_db):
    """Test deleting a problem in multiple groups (groups should remain)"""
    # Create two groups
    group1_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group1", "description": "Group 1"},
    )
    group1_id = group1_response.json()["id"]

    group2_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "group2", "description": "Group 2"},
    )
    group2_id = group2_response.json()["id"]

    # Create problem in both groups
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Multi-Group Problem", "group_ids": [group1_id, group2_id]},
    )
    problem_id = create_response.json()["id"]

    # Delete problem
    delete_response = client_with_db.delete(
        f"/api/solverdirector/v1/problems/{problem_id}"
    )
    assert delete_response.status_code == 204

    # Verify groups still exist
    group1_get = client_with_db.get(f"/api/solverdirector/v1/groups/{group1_id}")
    assert group1_get.status_code == 200

    group2_get = client_with_db.get(f"/api/solverdirector/v1/groups/{group2_id}")
    assert group2_get.status_code == 200


def test_delete_nonexistent_problem(client_with_db):
    """Test deleting a non-existent problem returns 404"""
    delete_response = client_with_db.delete("/api/solverdirector/v1/problems/99999")
    assert delete_response.status_code == 404
    assert "not found" in delete_response.json()["detail"].lower()


def test_delete_problem_with_file(client_with_db):
    """Test deleting a problem with uploaded file"""
    # Create group
    group_response = client_with_db.post(
        "/api/solverdirector/v1/groups",
        json={"name": "test-group", "description": "Test"},
    )
    group_id = group_response.json()["id"]

    # Create problem
    create_response = client_with_db.post(
        "/api/solverdirector/v1/problems",
        json={"name": "Problem with File", "group_ids": [group_id]},
    )
    problem_id = create_response.json()["id"]

    # Upload file
    file_content = b"This is the problem file content"
    client_with_db.put(
        f"/api/solverdirector/v1/problems/{problem_id}/file",
        files={"file": ("problem.mzn", BytesIO(file_content), "text/plain")},
    )

    # Verify file was uploaded
    get_response = client_with_db.get(f"/api/solverdirector/v1/problems/{problem_id}")
    assert get_response.status_code == 200
    assert get_response.json()["filename"] == "problem.mzn"

    # Delete problem
    delete_response = client_with_db.delete(
        f"/api/solverdirector/v1/problems/{problem_id}"
    )
    assert delete_response.status_code == 204

    # Verify problem and file are gone
    get_after_delete = client_with_db.get(
        f"/api/solverdirector/v1/problems/{problem_id}"
    )
    assert get_after_delete.status_code == 404
