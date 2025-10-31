"""Tests for solvers API endpoints"""

import asyncio
import io
import pytest
from unittest.mock import Mock, patch
from src.models import Solver, SolverImage


def create_mock_process(mocker, returncode=0, stdout=b"Success", stderr=b""):
    """Helper to create a mock async subprocess using pytest-mock"""
    mock_process = Mock()
    mock_process.returncode = returncode
    mock_process.communicate = mocker.AsyncMock(return_value=(stdout, stderr))
    mock_process.wait = mocker.AsyncMock(return_value=None)
    mock_process.kill = Mock()
    return mock_process


def test_upload_solver_success(client_with_db, mocker):
    """Test uploading a solver successfully"""
    # Create fake tarball data
    fake_tarball = io.BytesIO(b"fake docker image tar data")

    # Mock asyncio.create_subprocess_exec (skopeo)
    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(mocker, returncode=0)

        response = client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"name": "gecode"},
            files={"file": ("gecode.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "gecode"
        assert data["id"] == 1
        assert data["solver_images_id"] == 1
        assert data["image_path"] == "harbor.local/psp-solvers/gecode:latest"

        # Verify skopeo was called correctly
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]  # Positional args as tuple
        assert call_args[0] == "skopeo"
        assert call_args[1] == "copy"
        assert call_args[2].startswith("docker-archive:")
        assert (
            call_args[3]
            == "docker://harbor-core.harbor.svc.cluster.local/psp-solvers/gecode:latest"
        )
        assert "--dest-creds" in call_args
        assert "test-user:test-pass" in call_args


def test_upload_solver_duplicate_name(client_with_db, mocker):
    """Test uploading a solver with duplicate name fails"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(mocker, returncode=0)

        # First upload
        client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"name": "gecode"},
            files={
                "file": (
                    "gecode.tar",
                    io.BytesIO(b"fake tar data"),
                    "application/x-tar",
                )
            },
        )

        # Second upload with same name
        response = client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"name": "gecode"},
            files={"file": ("gecode2.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


def test_upload_solver_empty_name(client_with_db):
    """Test uploading a solver with empty name fails"""
    fake_tarball = io.BytesIO(b"fake tar data")

    response = client_with_db.post(
        "/api/solverdirector/v1/solvers",
        data={"name": "   "},  # Whitespace only
        files={"file": ("solver.tar", fake_tarball, "application/x-tar")},
    )

    assert response.status_code == 422
    assert "cannot be empty" in response.json()["detail"]


def test_upload_solver_empty_file(client_with_db):
    """Test uploading a solver with empty file fails"""
    empty_file = io.BytesIO(b"")

    response = client_with_db.post(
        "/api/solverdirector/v1/solvers",
        data={"name": "gecode"},
        files={"file": ("gecode.tar", empty_file, "application/x-tar")},
    )

    assert response.status_code == 422
    assert "cannot be empty" in response.json()["detail"]


def test_upload_solver_missing_file(client_with_db):
    """Test uploading a solver without file fails"""
    response = client_with_db.post(
        "/api/solverdirector/v1/solvers", data={"name": "gecode"}
    )

    assert response.status_code == 422


def test_upload_solver_harbor_push_failure(client_with_db, mocker):
    """Test handling Harbor push failure"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(
            mocker, returncode=1, stderr=b"Error: failed to push to Harbor", stdout=b""
        )

        response = client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"name": "gecode"},
            files={"file": ("gecode.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 500
        assert "Failed to push image to Harbor" in response.json()["detail"]


def test_upload_solver_harbor_credentials_failure(client_with_db):
    """Test handling Harbor credentials failure"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds:
        mock_creds.side_effect = Exception("Failed to get credentials")

        response = client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"name": "gecode"},
            files={"file": ("gecode.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 500
        assert "Failed to upload solver" in response.json()["detail"]


def test_upload_solver_timeout(client_with_db, mocker):
    """Test handling skopeo timeout"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.asyncio.wait_for") as mock_wait_for,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(mocker, returncode=0)
        mock_wait_for.side_effect = asyncio.TimeoutError()

        response = client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"name": "gecode"},
            files={"file": ("gecode.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 500
        assert "timed out" in response.json()["detail"]


# Suppress pytest-mock AsyncMock garbage collection warning
# This warning occurs because SQLAlchemy queries after the mocked async request
# trigger garbage collection while AsyncMock cleanup is happening.
# All async operations are properly awaited in the endpoint - this is just
# a test infrastructure artifact, not a code issue.
@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_upload_solver_creates_database_records(client_with_db, test_db, mocker):
    """Test that solver upload creates correct database records"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(mocker, returncode=0)

        response = client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"name": "gecode"},
            files={"file": ("gecode.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 201

        # Check database records
        solver = test_db.query(Solver).filter(Solver.name == "gecode").first()
        assert solver is not None
        assert solver.name == "gecode"
        assert solver.solver_images_id is not None

        solver_image = (
            test_db.query(SolverImage)
            .filter(SolverImage.id == solver.solver_images_id)
            .first()
        )
        assert solver_image is not None
        assert solver_image.image_path == "harbor.local/psp-solvers/gecode:latest"


def test_upload_solver_normalizes_name(client_with_db, mocker):
    """Test that solver name is normalized (whitespace stripped and lowercased)"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(mocker, returncode=0)

        response = client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"name": "  gecode  "},  # With whitespace
            files={"file": ("gecode.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "gecode"  # Whitespace stripped


def test_upload_solver_invalid_name(client_with_db):
    """Test that invalid solver names are rejected"""
    fake_tarball = io.BytesIO(b"fake tar data")

    # Test various invalid names (note: uppercase is normalized to lowercase, so not invalid)
    invalid_names = [
        "gecode/nested",  # Slashes not allowed
        "../gecode",  # Path traversal attempt
        "gecode@latest",  # @ not allowed in names
        "-gecode",  # Cannot start with hyphen
        ".gecode",  # Cannot start with dot
        "ge code",  # Spaces not allowed (before normalization strips them)
    ]

    for invalid_name in invalid_names:
        response = client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"name": invalid_name},
            files={"file": ("solver.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 422, (
            f"Expected 422 for name: {invalid_name}, got {response.status_code}: {response.json()}"
        )
        assert "lowercase alphanumeric" in response.json()["detail"]
