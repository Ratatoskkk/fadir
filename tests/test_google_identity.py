from __future__ import annotations

from pathlib import Path
import time

import pytest


def test_google_identity_module_is_available():
    from app.services.google_identity import verify_google_identity

    assert callable(verify_google_identity)


def test_valid_claims_use_issuer_subject_and_nonce_without_email():
    from app.services.google_identity import verify_google_identity

    token = "synthetic-token"
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "web-client-id",
        "sub": "opaque-subject-123",
        "nonce": "nonce-value",
        "email": "private@example.invalid",
    }
    identity = verify_google_identity(
        token,
        client_id="web-client-id",
        expected_nonce="nonce-value",
        timeout_seconds=2.5,
        verifier=lambda value, client_id, timeout: claims,
    )
    assert identity.issuer == "https://accounts.google.com"
    assert identity.subject == "opaque-subject-123"
    assert "email" not in repr(identity)
    assert "private@example.invalid" not in repr(identity)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("iss", "accounts.google.com"),
        ("aud", "another-client"),
        ("nonce", "wrong-nonce"),
        ("sub", ""),
    ],
)
def test_claim_mismatch_fails_generically(field, value):
    from app.services.google_identity import GoogleIdentityError, verify_google_identity

    claims = {
        "iss": "https://accounts.google.com",
        "aud": "web-client-id",
        "sub": "opaque-subject-123",
        "nonce": "nonce-value",
    }
    claims[field] = value
    with pytest.raises(GoogleIdentityError) as error:
        verify_google_identity(
            "token-with-email@example.invalid",
            client_id="web-client-id",
            expected_nonce="nonce-value",
            verifier=lambda *_: claims,
        )
    assert str(error.value) == "Google identity verification failed"
    assert error.value.__context__ is None
    assert "email@example.invalid" not in repr(error.value)


def test_verifier_receives_exact_timeout():
    from app.services.google_identity import verify_google_identity

    seen = {}

    def verifier(token, client_id, timeout_seconds):
        seen.update(token=token, client_id=client_id, timeout=timeout_seconds)
        return {
            "iss": "https://accounts.google.com",
            "aud": client_id,
            "sub": "opaque-subject-123",
            "nonce": "nonce-value",
        }

    verify_google_identity(
        "synthetic-token",
        client_id="web-client-id",
        expected_nonce="nonce-value",
        timeout_seconds=3.25,
        verifier=verifier,
    )
    assert seen == {
        "token": "synthetic-token",
        "client_id": "web-client-id",
        "timeout": 3.25,
    }


def test_verifier_failure_and_timeout_are_generic():
    from app.services.google_identity import GoogleIdentityError, verify_google_identity

    def broken(*_args):
        raise RuntimeError("token=secret email=private@example.invalid")

    with pytest.raises(GoogleIdentityError) as error:
        verify_google_identity(
            "secret-token",
            client_id="web-client-id",
            expected_nonce="nonce-value",
            verifier=broken,
        )
    assert str(error.value) == "Google identity verification failed"
    assert error.value.__context__ is None
    assert "secret" not in repr(error.value)
    assert "private@example.invalid" not in repr(error.value)

    def slow(*_args):
        time.sleep(0.2)
        return {}

    started = time.monotonic()
    with pytest.raises(GoogleIdentityError):
        verify_google_identity(
            "secret-token",
            client_id="web-client-id",
            expected_nonce="nonce-value",
            timeout_seconds=0.1,
            verifier=slow,
        )
    assert time.monotonic() - started < 0.18


def test_unavailable_google_auth_fails_closed(monkeypatch):
    from app.services import google_identity

    monkeypatch.setattr(google_identity, "_load_google_verifier", lambda: None)
    with pytest.raises(google_identity.GoogleIdentityUnavailable) as error:
        google_identity.verify_google_identity(
            "synthetic-token",
            client_id="web-client-id",
            expected_nonce="nonce-value",
        )
    assert str(error.value) == "Google identity verification unavailable"
    assert error.value.__context__ is None


def test_settings_load_explicit_google_config(tmp_path, monkeypatch):
    from app.config import load_settings

    config_path = Path(tmp_path) / "settings.yaml"
    config_path.write_text(
        "google:\n  web_client_id: yaml-client\n  verification_timeout_seconds: 4.5\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("FADIR_GOOGLE_WEB_CLIENT_ID", raising=False)
    monkeypatch.delenv("FADIR_GOOGLE_VERIFICATION_TIMEOUT_SECONDS", raising=False)
    settings = load_settings(config_path)
    assert settings.google.web_client_id == "yaml-client"
    assert settings.google.verification_timeout_seconds == 4.5

    monkeypatch.setenv("FADIR_GOOGLE_WEB_CLIENT_ID", "env-client")
    monkeypatch.setenv("FADIR_GOOGLE_VERIFICATION_TIMEOUT_SECONDS", "6")
    env_settings = load_settings(config_path)
    assert env_settings.google.web_client_id == "env-client"
    assert env_settings.google.verification_timeout_seconds == 6.0
