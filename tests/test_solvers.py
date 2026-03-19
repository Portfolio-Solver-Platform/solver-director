"""Tests for solvers API endpoints"""

from src.models import Solver, SolverImage

IMAGE_URL = "ghcr.io/portfolio-solver-platform/minizinc-solvers:latest"


def _register(client, image_name="minizinc-solvers", image_url=IMAGE_URL, names="chuffed,gecode"):
    return client.post(
        "/api/solverdirector/v1/solvers",
        data={"image_name": image_name, "image_url": image_url, "names": names},
    )


def test_register_solver_success(authed_client_with_db):
    response = _register(authed_client_with_db)

    assert response.status_code == 201
    data = response.json()
    assert data["names"] == ["chuffed", "gecode"]
    assert data["id"] == 1
    assert data["solver_images_id"] == 1
    assert data["image_path"] == IMAGE_URL


def test_register_solver_creates_database_records(authed_client_with_db, test_db):
    response = _register(authed_client_with_db, names="chuffed,gecode")
    assert response.status_code == 201

    solver_image = (
        test_db.query(SolverImage)
        .filter(SolverImage.image_name == "minizinc-solvers")
        .first()
    )
    assert solver_image is not None
    assert solver_image.image_path == IMAGE_URL

    for name in ["chuffed", "gecode"]:
        solver = test_db.query(Solver).filter(Solver.name == name).first()
        assert solver is not None
        assert solver.solver_image_id == solver_image.id


def test_register_solver_duplicate_image_name(authed_client_with_db):
    _register(authed_client_with_db)
    response = _register(authed_client_with_db)

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_register_solver_empty_image_name(authed_client_with_db):
    response = _register(authed_client_with_db, image_name="   ")
    assert response.status_code == 422
    assert "cannot be empty" in response.json()["detail"]


def test_register_solver_empty_image_url(authed_client_with_db):
    response = _register(authed_client_with_db, image_url="   ")
    assert response.status_code == 422
    assert "cannot be empty" in response.json()["detail"]


def test_register_solver_empty_names(authed_client_with_db):
    response = _register(authed_client_with_db, names="   ")
    assert response.status_code == 422
    assert "At least one solver name is required" in response.json()["detail"]


def test_register_solver_normalizes_names(authed_client_with_db):
    response = _register(
        authed_client_with_db,
        image_name="  MiniZinc-Solvers  ",
        names="  Chuffed , GECODE  ",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["names"] == ["chuffed", "gecode"]


def test_register_solver_invalid_image_name(authed_client_with_db):
    for invalid_name in ["gecode/nested", "../gecode", "gecode@latest", "-gecode", ".gecode", "ge code"]:
        response = _register(authed_client_with_db, image_name=invalid_name)
        assert response.status_code == 422, f"Expected 422 for: {invalid_name}"
        assert "lowercase alphanumeric" in response.json()["detail"]


def test_register_solver_invalid_solver_names(authed_client_with_db):
    for invalid_name in ["chuffed/nested", "../chuffed", "chuffed@latest", "-chuffed", ".chuffed"]:
        response = _register(authed_client_with_db, names=invalid_name)
        assert response.status_code == 422, f"Expected 422 for: {invalid_name}"
        assert "lowercase alphanumeric" in response.json()["detail"]


def test_get_all_solvers(authed_client_with_db):
    _register(authed_client_with_db, names="chuffed,gecode,ortools")

    response = authed_client_with_db.get("/api/solverdirector/v1/solvers")
    assert response.status_code == 200
    data = response.json()
    assert len(data["solvers"]) == 3

    solver_names = {s["name"] for s in data["solvers"]}
    assert solver_names == {"chuffed", "gecode", "ortools"}

    for solver in data["solvers"]:
        assert solver["image_name"] == "minizinc-solvers"
        assert solver["image_path"] == IMAGE_URL


def test_get_solver_by_id(authed_client_with_db, test_db):
    _register(authed_client_with_db, names="chuffed")

    solver = test_db.query(Solver).filter(Solver.name == "chuffed").first()
    assert solver is not None

    response = authed_client_with_db.get(f"/api/solverdirector/v1/solvers/{solver.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == solver.id
    assert data["name"] == "chuffed"
    assert data["image_name"] == "minizinc-solvers"
    assert data["image_path"] == IMAGE_URL


def test_get_solver_by_id_not_found(authed_client_with_db):
    response = authed_client_with_db.get("/api/solverdirector/v1/solvers/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
