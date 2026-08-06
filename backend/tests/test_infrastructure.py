"""FastAPI infrastructure contract tests."""

from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.error_handlers import register_exception_handlers
from app import database
from app.exceptions import NotFoundError
from app.main import app


def test_health_endpoint_returns_service_status() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "FuelMind AI Backend"}


def test_openapi_schema_is_available() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "FuelMind AI Backend"


def test_request_validation_uses_central_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["message"] == "Request validation failed."
    assert response.json()["error"]["details"]


def test_database_dependency_closes_session(
    monkeypatch: object,
) -> None:
    class FakeSession:
        closed = False

        def close(self) -> None:
            self.closed = True

    session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    dependency: Generator[object, None, None] = database.get_db()
    assert next(dependency) is session
    dependency.close()
    assert session.closed


def test_domain_errors_use_central_error_envelope() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/missing")
    def missing_resource() -> None:
        raise NotFoundError("Requested resource was not found.")

    with TestClient(test_app) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "Requested resource was not found.",
            "details": None,
        }
    }


def test_unexpected_errors_do_not_expose_tracebacks() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/unexpected")
    def unexpected_error() -> None:
        raise RuntimeError("internal diagnostic detail")

    with TestClient(test_app, raise_server_exceptions=False) as client:
        response = client.get("/unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Internal server error.",
            "details": None,
        }
    }


def test_integrity_errors_use_conflict_error_envelope() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.post("/duplicate")
    def duplicate_record() -> None:
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    with TestClient(test_app, raise_server_exceptions=False) as client:
        response = client.post("/duplicate")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RESOURCE_CONFLICT"
