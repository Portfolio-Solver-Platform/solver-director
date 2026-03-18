"""Tests for solvers API endpoints"""

import asyncio
import io
import pytest
from unittest.mock import Mock, patch
from src.models import Solver, SolverImage


def create_mock_process(returncode=0, stdout=b"Success", stderr=b""):
    """Helper to create a mock async subprocess"""
    mock_process = Mock()
    mock_process.returncode = returncode

    async def _communicate():
        return (stdout, stderr)

    async def _wait():
        return None

    mock_process.communicate = _communicate
    mock_process.wait = _wait
    mock_process.kill = Mock()
    return mock_process


def test_upload_solver_success(authed_client_with_db):
    """Test uploading a solver successfully"""
    fake_tarball = io.BytesIO(b"fake docker image tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(returncode=0)

        response = authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": "chuffed,gecode"},
            files={"file": ("minizinc.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["names"] == ["chuffed", "gecode"]
        assert data["id"] == 1
        assert data["solver_images_id"] == 1
        assert data["image_path"] == "harbor.local/psp-solvers/minizinc-solver:latest"

        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "skopeo"
        assert call_args[1] == "copy"
        assert call_args[2].startswith("docker-archive:")
        assert (
            call_args[3]
            == "docker://harbor-core.harbor.svc.cluster.local/psp-solvers/minizinc-solver:latest"
        )
        assert "--dest-creds" in call_args
        assert "test-user:test-pass" in call_args


def test_upload_solver_duplicate_image_name(authed_client_with_db):
    """Test uploading a solver with duplicate image_name fails"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(returncode=0)

        authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": "chuffed"},
            files={
                "file": (
                    "minizinc.tar",
                    io.BytesIO(b"fake tar data"),
                    "application/x-tar",
                )
            },
        )

        response = authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": "gecode"},
            files={"file": ("minizinc2.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


def test_upload_solver_empty_image_name(authed_client_with_db):
    """Test uploading a solver with empty image_name fails"""
    fake_tarball = io.BytesIO(b"fake tar data")

    response = authed_client_with_db.post(
        "/api/solverdirector/v1/solvers",
        data={"image_name": "   ", "names": "gecode"},  # Whitespace only
        files={"file": ("solver.tar", fake_tarball, "application/x-tar")},
    )

    assert response.status_code == 422
    assert "cannot be empty" in response.json()["detail"]


def test_upload_solver_empty_names(authed_client_with_db):
    """Test uploading a solver with empty names fails"""
    fake_tarball = io.BytesIO(b"fake tar data")

    response = authed_client_with_db.post(
        "/api/solverdirector/v1/solvers",
        data={"image_name": "minizinc-solver", "names": "   "},  # Whitespace only
        files={"file": ("solver.tar", fake_tarball, "application/x-tar")},
    )

    assert response.status_code == 422
    assert "At least one solver name is required" in response.json()["detail"]


def test_upload_solver_empty_file(authed_client_with_db):
    """Test uploading a solver with empty file fails"""
    empty_file = io.BytesIO(b"")

    response = authed_client_with_db.post(
        "/api/solverdirector/v1/solvers",
        data={"image_name": "minizinc-solver", "names": "gecode"},
        files={"file": ("gecode.tar", empty_file, "application/x-tar")},
    )

    assert response.status_code == 422
    assert "cannot be empty" in response.json()["detail"]


def test_upload_solver_missing_file(authed_client_with_db):
    """Test uploading a solver without file fails"""
    response = authed_client_with_db.post(
        "/api/solverdirector/v1/solvers",
        data={"image_name": "minizinc-solver", "names": "gecode"},
    )

    assert response.status_code == 422


def test_upload_solver_harbor_push_failure(authed_client_with_db):
    """Test handling Harbor push failure"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(
            returncode=1, stderr=b"Error: failed to push to Harbor", stdout=b""
        )

        response = authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": "gecode"},
            files={"file": ("gecode.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 500
        assert "Failed to push image to Harbor" in response.json()["detail"]


def test_upload_solver_harbor_credentials_failure(authed_client_with_db):
    """Test handling Harbor credentials failure"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds:
        mock_creds.side_effect = Exception("Failed to get credentials")

        response = authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": "gecode"},
            files={"file": ("gecode.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 500
        assert "Failed to upload solver" in response.json()["detail"]


def test_upload_solver_timeout(authed_client_with_db):
    """Test handling skopeo timeout"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.asyncio.wait_for") as mock_wait_for,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        # communicate is never awaited (wait_for raises before it runs), so use a plain
        # Mock to avoid creating an unawaited coroutine that leaks into the next test's GC.
        mock_process = create_mock_process(returncode=0)
        mock_process.communicate = Mock(return_value=None)
        mock_exec.return_value = mock_process
        mock_wait_for.side_effect = asyncio.TimeoutError()

        response = authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": "gecode"},
            files={"file": ("gecode.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 500
        assert "timed out" in response.json()["detail"]


def test_upload_solver_creates_database_records(authed_client_with_db, test_db):
    """Test that solver upload creates correct database records"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(returncode=0)

        response = authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": "chuffed,gecode"},
            files={"file": ("minizinc.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 201

        # Check SolverImage record
        solver_image = (
            test_db.query(SolverImage)
            .filter(SolverImage.image_name == "minizinc-solver")
            .first()
        )
        assert solver_image is not None
        assert solver_image.image_name == "minizinc-solver"
        assert (
            solver_image.image_path == "harbor.local/psp-solvers/minizinc-solver:latest"
        )

        # Check that both Solver records were created
        chuffed_solver = test_db.query(Solver).filter(Solver.name == "chuffed").first()
        assert chuffed_solver is not None
        assert chuffed_solver.name == "chuffed"
        assert chuffed_solver.solver_image_id == solver_image.id

        gecode_solver = test_db.query(Solver).filter(Solver.name == "gecode").first()
        assert gecode_solver is not None
        assert gecode_solver.name == "gecode"
        assert gecode_solver.solver_image_id == solver_image.id


def test_upload_solver_normalizes_names(authed_client_with_db):
    """Test that image_name and solver names are normalized (whitespace stripped and lowercased)"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(returncode=0)

        response = authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "  MiniZinc-Solver  ", "names": "  Chuffed , GECODE  "},
            files={"file": ("minizinc.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["names"] == ["chuffed", "gecode"]
        assert data["image_path"] == "harbor.local/psp-solvers/minizinc-solver:latest"


def test_upload_solver_invalid_image_name(authed_client_with_db):
    """Test that invalid image names are rejected"""
    fake_tarball = io.BytesIO(b"fake tar data")

    invalid_names = [
        "gecode/nested",
        "../gecode",
        "gecode@latest",
        "-gecode",
        ".gecode",
        "ge code",
    ]

    for invalid_name in invalid_names:
        response = authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": invalid_name, "names": "chuffed"},
            files={"file": ("solver.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 422, (
            f"Expected 422 for image_name: {invalid_name}, got {response.status_code}: {response.json()}"
        )
        assert "lowercase alphanumeric" in response.json()["detail"]


def test_upload_solver_invalid_solver_names(authed_client_with_db):
    """Test that invalid solver names in the names parameter are rejected"""
    fake_tarball = io.BytesIO(b"fake tar data")

    invalid_names = [
        "chuffed/nested",
        "../chuffed",
        "chuffed@latest",
        "-chuffed",
        ".chuffed",
    ]

    for invalid_name in invalid_names:
        response = authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": invalid_name},
            files={"file": ("solver.tar", fake_tarball, "application/x-tar")},
        )

        assert response.status_code == 422, (
            f"Expected 422 for solver name: {invalid_name}, got {response.status_code}: {response.json()}"
        )
        assert "lowercase alphanumeric" in response.json()["detail"]


def test_get_all_solvers(authed_client_with_db, test_db):
    """Test retrieving all solvers"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(returncode=0)

        authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": "chuffed,gecode,ortools"},
            files={"file": ("minizinc.tar", fake_tarball, "application/x-tar")},
        )

        response = authed_client_with_db.get("/api/solverdirector/v1/solvers")

        assert response.status_code == 200
        data = response.json()
        assert "solvers" in data
        assert len(data["solvers"]) == 3

        solver_names = {solver["name"] for solver in data["solvers"]}
        assert solver_names == {"chuffed", "gecode", "ortools"}

        for solver in data["solvers"]:
            assert "id" in solver
            assert "name" in solver
            assert "image_name" in solver
            assert "image_path" in solver
            assert solver["image_name"] == "minizinc-solver"
            assert (
                solver["image_path"]
                == "harbor.local/psp-solvers/minizinc-solver:latest"
            )


def test_get_solver_by_id(authed_client_with_db, test_db):
    """Test retrieving a specific solver by ID"""
    fake_tarball = io.BytesIO(b"fake tar data")

    with (
        patch("src.routers.api.solvers.asyncio.create_subprocess_exec") as mock_exec,
        patch("src.routers.api.solvers.get_harbor_credentials") as mock_creds,
    ):
        mock_creds.return_value = ("test-user", "test-pass")
        mock_exec.return_value = create_mock_process(returncode=0)

        authed_client_with_db.post(
            "/api/solverdirector/v1/solvers",
            data={"image_name": "minizinc-solver", "names": "chuffed"},
            files={"file": ("minizinc.tar", fake_tarball, "application/x-tar")},
        )

        solver = test_db.query(Solver).filter(Solver.name == "chuffed").first()
        assert solver is not None

        response = authed_client_with_db.get(f"/api/solverdirector/v1/solvers/{solver.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == solver.id
        assert data["name"] == "chuffed"
        assert data["image_name"] == "minizinc-solver"
        assert data["image_path"] == "harbor.local/psp-solvers/minizinc-solver:latest"


def test_get_solver_by_id_not_found(authed_client_with_db):
    """Test retrieving a solver by ID that doesn't exist"""
    response = authed_client_with_db.get("/api/solverdirector/v1/solvers/99999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
