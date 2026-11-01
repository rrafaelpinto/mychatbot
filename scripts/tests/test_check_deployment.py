"""Offline checks for Render deployment settings and read-only smoke probes."""

import json
from email.message import Message
from pathlib import Path
from urllib.request import Request

import pytest
import yaml

from scripts.check_deployment import DeploymentCheckError, check_deployment


ROOT = Path(__file__).resolve().parents[2]


def test_render_blueprint_requires_manual_release_and_persistent_database():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    assert "databases" not in blueprint
    services = {service["name"]: service for service in blueprint["services"]}
    assert set(services) == {"resumebot-api", "resumebot-frontend"}

    backend = services["resumebot-api"]
    frontend = services["resumebot-frontend"]
    assert backend["autoDeployTrigger"] == "off"
    assert frontend["autoDeployTrigger"] == "off"
    assert backend["plan"] != "free"
    assert backend["healthCheckPath"] == "/healthz/"
    assert "migrate --noinput" in backend["preDeployCommand"]
    assert frontend["runtime"] == "static"
    assert frontend["rootDir"] == "frontend"
    assert frontend["staticPublishPath"] == "dist"
    assert "npm run build" in frontend["buildCommand"]
    assert not frontend.get("preDeployCommand")

    backend_env = {var["key"]: var for var in backend["envVars"]}
    frontend_env = {var["key"]: var for var in frontend["envVars"]}
    for name in (
        "DATABASE_URL",
        "DJANGO_ALLOWED_HOSTS",
        "API_CORS_ALLOWED_ORIGINS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
    ):
        assert backend_env[name] == {"key": name, "sync": False}
    assert backend_env["DJANGO_SECRET_KEY"]["generateValue"] is True
    assert backend_env["JWT_SIGNING_KEY"]["generateValue"] is True
    for name in ("AI_ENABLED", "GUEST_CHAT_ENABLED", "CANDIDATE_UPLOADS_ENABLED"):
        assert backend_env[name]["value"] == "false"
    assert frontend_env["VITE_API_BASE_URL"] == {
        "key": "VITE_API_BASE_URL",
        "sync": False,
    }
    assert frontend_env["RESUMEBOT_BUILD_TARGET"]["value"] == "production"


class Reply:
    def __init__(self, request, *, content=b"", status=200, headers=None):
        self.request = request
        self.status = status
        self.content = content
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.content

    def geturl(self):
        return self.request.full_url


def fake_responses(allowed_headers="content-type,x-csrftoken,idempotency-key"):
    calls = []

    def respond(request: Request, *, timeout):
        assert timeout > 0
        assert request.get_method() in {"GET", "OPTIONS"}
        calls.append(request)
        url = request.full_url
        if url == "https://app.example.test/":
            return Reply(request, content=b"<html><title>ResumeBot</title></html>")
        if url == "https://api.example.test/healthz/":
            return Reply(request, content=b"ok")
        if url.endswith("/auth/csrf/"):
            return Reply(
                request,
                content=json.dumps({"csrf_token": "synthetic"}).encode(),
                headers={
                    "Cache-Control": "no-store",
                    "Set-Cookie": "csrftoken=synthetic; Secure; SameSite=Lax",
                },
            )
        if request.get_method() == "OPTIONS":
            return Reply(request, status=204, headers={
                "Access-Control-Allow-Origin": "https://app.example.test",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Headers": allowed_headers,
            })
        if url.endswith("/api/v1/candidates/"):
            return Reply(
                request, content=b'{"count":0,"results":[],"next":null,"previous":null}'
            )
        if url.endswith("/alex/guest-chat/"):
            return Reply(request, content=json.dumps({
                "enabled": False,
                "guest_verified": False,
                "history": [],
            }).encode(), headers={"Cache-Control": "no-store"})
        raise AssertionError(f"Unexpected request: {request.get_method()} {url}")

    return respond, calls


def test_read_only_deployment_smoke_checks_cors_csrf_and_public_contract(monkeypatch):
    respond, calls = fake_responses()
    monkeypatch.setattr("scripts.check_deployment.urlopen", respond)
    result = check_deployment(
        api_origin="https://api.example.test",
        frontend_origin="https://app.example.test",
        candidate="alex",
    )
    assert "OK" in result
    assert len(calls) == 6
    assert all(request.get_method() != "POST" for request in calls)
    preflight = next(request for request in calls if request.get_method() == "OPTIONS")
    assert preflight.headers["Origin"] == "https://app.example.test"
    assert "idempotency-key" in preflight.headers["Access-control-request-headers"]


def test_deployment_smoke_rejects_missing_idempotency_preflight(monkeypatch):
    respond, _ = fake_responses("content-type,x-csrftoken")
    monkeypatch.setattr("scripts.check_deployment.urlopen", respond)
    with pytest.raises(DeploymentCheckError, match="preflight"):
        check_deployment(
            api_origin="https://api.example.test",
            frontend_origin="https://app.example.test",
        )


@pytest.mark.parametrize(
    "origin",
    [
        "http://api.example.test",
        "https://api.example.test/path",
        "https://name:password@api.example.test",
        "https://api.example.test/?token=abc",
        "javascript:alert(1)",
        "http://localhost:8000",
    ],
)
def test_deployment_smoke_rejects_insecure_or_non_origin_endpoints(origin):
    with pytest.raises(DeploymentCheckError, match="Origins"):
        check_deployment(
            api_origin=origin,
            frontend_origin="https://app.example.test",
        )


def test_deployment_smoke_rejects_same_origin():
    with pytest.raises(DeploymentCheckError, match="distinct"):
        check_deployment(
            api_origin="https://api.example.test",
            frontend_origin="https://api.example.test",
        )
