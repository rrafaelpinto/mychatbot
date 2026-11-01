#!/usr/bin/env python3
"""Verify a deployed frontend/API pair without creating sessions or invoking AI."""

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class DeploymentCheckError(Exception):
    """A deployed service failed a read-only release invariant."""


def validate_origin(value, *, allow_local_http=False):
    parsed = urlsplit(value)
    local = parsed.hostname in {"localhost", "127.0.0.1"}
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or (
            parsed.scheme != "https"
            and not (allow_local_http and local and parsed.scheme == "http")
        )
    ):
        raise DeploymentCheckError(
            "Origins must be absolute HTTPS origins (HTTP loopback allowed only with --allow-local-http)."
        )
    return value.rstrip("/")


def fetch(url, *, method="GET", headers=None):
    request = Request(url, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=15) as response:
            result = response.read(1_048_576)
            final = urlsplit(response.geturl())
            requested = urlsplit(url)
            if (final.scheme, final.netloc) != (
                requested.scheme,
                requested.netloc,
            ):
                raise DeploymentCheckError("Request redirected to a different origin.")
            if response.status != 200 and not (
                method == "OPTIONS" and response.status in (200, 204)
            ):
                raise DeploymentCheckError(
                    f"{method} {requested.path}: unexpected status {response.status}."
                )
            return result, response.headers
    except (HTTPError, URLError, TimeoutError) as exc:
        raise DeploymentCheckError(
            f"{method} {urlsplit(url).path}: connection or HTTP failure."
        ) from exc


def read_json(url, *, headers=None):
    body, response_headers = fetch(url, headers=headers)
    try:
        return json.loads(body), response_headers
    except (ValueError, UnicodeError) as exc:
        raise DeploymentCheckError(f"{urlsplit(url).path}: invalid JSON.") from exc


def check_deployment(
    *, api_origin, frontend_origin, candidate=None, allow_local_http=False
):
    api = validate_origin(api_origin, allow_local_http=allow_local_http)
    frontend = validate_origin(frontend_origin, allow_local_http=allow_local_http)
    if api == frontend:
        raise DeploymentCheckError("Frontend and API must use distinct origins.")

    page, _ = fetch(frontend + "/")
    if b"ResumeBot" not in page or b"<html" not in page:
        raise DeploymentCheckError("Frontend did not serve the ResumeBot application.")
    health, _ = fetch(api + "/healthz/")
    if health != b"ok":
        raise DeploymentCheckError("Backend database health check did not return ok.")

    origin_headers = {"Origin": frontend}
    csrf, csrf_headers = read_json(api + "/api/v1/auth/csrf/", headers=origin_headers)
    if not isinstance(csrf, dict) or not csrf.get("csrf_token"):
        raise DeploymentCheckError("CSRF bootstrap did not return a token.")
    if csrf_headers.get("Cache-Control") != "no-store":
        raise DeploymentCheckError("CSRF response must not be cached.")
    if not allow_local_http:
        cookies = csrf_headers.get_all("Set-Cookie", [])
        if not any(
            "csrftoken=" in value
            and "secure" in value.lower()
            and "samesite=lax" in value.lower()
            for value in cookies
        ):
            raise DeploymentCheckError("CSRF cookie requires Secure and SameSite=Lax.")

    preflight_url = api + "/api/v1/candidates/example/guest-chat/"
    _, cors = fetch(
        preflight_url,
        method="OPTIONS",
        headers={
            "Origin": frontend,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "content-type,x-csrftoken,idempotency-key"
            ),
        },
    )
    if cors.get("Access-Control-Allow-Origin") != frontend:
        raise DeploymentCheckError("Frontend origin is not CORS-allowlisted.")
    if cors.get("Access-Control-Allow-Credentials", "").lower() != "true":
        raise DeploymentCheckError("Credentialed CORS is not enabled.")
    allowed = {
        header.strip().lower()
        for header in cors.get("Access-Control-Allow-Headers", "").split(",")
    }
    if not {"content-type", "x-csrftoken", "idempotency-key"} <= allowed:
        raise DeploymentCheckError(
            "Guest POST preflight does not allow required headers."
        )

    candidates, _ = read_json(api + "/api/v1/candidates/", headers=origin_headers)
    if not isinstance(candidates, dict) or not isinstance(
        candidates.get("results"), list
    ):
        raise DeploymentCheckError(
            "Public candidates endpoint returned an invalid page."
        )

    if candidate:
        if not candidate.isascii() or not all(
            char.islower() or char.isdigit() or char == "-" for char in candidate
        ):
            raise DeploymentCheckError("Candidate must be a lowercase slug.")
        status, headers = read_json(
            api + "/api/v1/candidates/" + quote(candidate) + "/guest-chat/",
            headers=origin_headers,
        )
        if not isinstance(status, dict) or not isinstance(status.get("enabled"), bool):
            raise DeploymentCheckError("Guest status contract is invalid.")
        if status.get("guest_verified") or status.get("history") != []:
            raise DeploymentCheckError(
                "Fresh smoke-test client must not see guest history or verification."
            )
        if headers.get("Cache-Control") != "no-store":
            raise DeploymentCheckError("Guest status must not be cached.")

    return (
        "Frontend HTML, backend database, CSRF cookie, credentialed CORS, "
        "idempotent guest preflight, and public API: OK."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-origin", required=True)
    parser.add_argument("--frontend-origin", required=True)
    parser.add_argument("--candidate", help="Optional public candidate slug")
    parser.add_argument(
        "--allow-local-http",
        action="store_true",
        help="Permit HTTP only when both origins use loopback addresses",
    )
    args = parser.parse_args(argv)
    try:
        message = check_deployment(
            api_origin=args.api_origin,
            frontend_origin=args.frontend_origin,
            candidate=args.candidate,
            allow_local_http=args.allow_local_http,
        )
    except DeploymentCheckError as exc:
        print(f"Deployment check failed: {exc}", file=sys.stderr)
        return 1
    print(message)
    print(
        "Real browser cookie persistence, Turnstile completion, "
        "and paid AI availability require separate controlled verification."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
