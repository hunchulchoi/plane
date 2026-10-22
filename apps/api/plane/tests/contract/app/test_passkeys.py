# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import copy
import hashlib
import json
import os
import uuid
from unittest.mock import patch

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from webauthn.helpers import bytes_to_base64url

from plane.authentication.views.app.passkey import consume_challenge
from plane.db.models import Passkey, User
from plane.license.models import Instance

pytestmark = [pytest.mark.contract, pytest.mark.django_db]
ORIGIN = "https://testserver"


class Authenticator:
    """Small ES256 authenticator producing genuine WebAuthn signatures."""

    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)

    def registration(self, challenge, *, origin=ORIGIN, rp_id="testserver", verified=True):
        public = self.key.public_key().public_numbers()
        cose = {1: 2, 3: -7, -1: 1, -2: public.x.to_bytes(32, "big"), -3: public.y.to_bytes(32, "big")}
        client = json.dumps({"type": "webauthn.create", "challenge": challenge, "origin": origin}).encode()
        auth = (
            hashlib.sha256(rp_id.encode()).digest()
            + bytes([0x45 if verified else 0x41])
            + bytes(4)
            + bytes(16)
            + len(self.credential_id).to_bytes(2, "big")
            + self.credential_id
            + cbor2.dumps(cose)
        )
        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client),
                "attestationObject": bytes_to_base64url(cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth})),
                "transports": ["internal"],
            },
        }

    def assertion(self, challenge, user, *, count=1, origin=ORIGIN, rp_id="testserver", verified=True):
        client = json.dumps({"type": "webauthn.get", "challenge": challenge, "origin": origin}).encode()
        auth = hashlib.sha256(rp_id.encode()).digest() + bytes([5 if verified else 1]) + count.to_bytes(4, "big")
        signature = self.key.sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client),
                "authenticatorData": bytes_to_base64url(auth),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(user.id.bytes),
            },
        }


@pytest.fixture(autouse=True)
def passkey_environment(settings):
    settings.WEB_URL = ORIGIN
    settings.CSRF_TRUSTED_ORIGINS = [ORIGIN]
    Instance.objects.create(
        instance_name="Passkey test",
        instance_id=str(uuid.uuid4()),
        is_setup_done=True,
        last_checked_at=timezone.now(),
    )
    cache.delete_pattern("passkey:used:*")
    with patch("plane.authentication.rate_limit.AuthenticationThrottle.allow_request", return_value=True):
        yield
    cache.delete_pattern("passkey:used:*")


def client_for(user=None):
    client = APIClient(enforce_csrf_checks=True)
    if user:
        client.force_login(user)
    token = client.get("/auth/get-csrf-token/", secure=True).json()["csrf_token"]
    client.credentials(HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN=ORIGIN)
    return client


def post(client, path, data=None):
    return client.post(f"/auth/passkeys/{path}/", data or {}, format="json", secure=True)


def register(client, authenticator, **kwargs):
    options = post(client, "register/options")
    assert options.status_code == 200, options.data
    credential = authenticator.registration(options.data["challenge"], **kwargs)
    return post(client, "register/verify", {"name": "Laptop", "credential": credential})


def test_registration_login_and_delete(create_user):
    client = client_for(create_user)
    authenticator = Authenticator()
    created = register(client, authenticator)
    assert created.status_code == 201, created.data
    key = Passkey.objects.get(pk=created.data["id"])
    assert key.user == create_user
    assert key.name == "Laptop"
    listed = client.get("/auth/passkeys/", secure=True)
    assert listed.status_code == 200
    assert set(listed.data[0]) == {"id", "name", "created_at", "last_used_at"}

    anonymous = client_for()
    options = post(anonymous, "login/options")
    assert options.status_code == 200
    assert options.data["userVerification"] == "required"
    assertion = authenticator.assertion(options.data["challenge"], create_user)
    with patch("plane.authentication.views.app.passkey.post_user_auth_workflow"):
        response = post(anonymous, "login/verify", {"credential": assertion})
    assert response.status_code == 200, response.data
    assert anonymous.session["_auth_user_id"] == str(create_user.id)
    key.refresh_from_db()
    assert key.sign_count == 1
    assert key.last_used_at is not None
    assert response.data["redirect_url"]

    # CSRF tokens rotate on login; retrieve a new one before deleting.
    token = anonymous.get("/auth/get-csrf-token/", secure=True).json()["csrf_token"]
    anonymous.credentials(HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN=ORIGIN)
    assert anonymous.delete(f"/auth/passkeys/{key.id}/", secure=True).status_code == 204
    assert not Passkey.objects.filter(id=key.id).exists()


@pytest.mark.parametrize("bad", [{"origin": "https://evil.invalid"}, {"rp_id": "evil.invalid"}, {"verified": False}])
def test_registration_rejects_wrong_origin_rp_and_unverified_user(create_user, bad):
    response = register(client_for(create_user), Authenticator(), **bad)
    assert response.status_code == 400
    assert not Passkey.objects.exists()


@pytest.mark.parametrize("case", ["origin", "rp", "verification", "signature", "user_handle", "inactive", "counter"])
def test_login_rejects_invalid_assertions(create_user, case):
    client = client_for(create_user)
    authenticator = Authenticator()
    assert register(client, authenticator).status_code == 201
    if case == "inactive":
        create_user.is_active = False
        create_user.save(update_fields=["is_active"])
    if case == "counter":
        Passkey.objects.update(sign_count=3)
    anonymous = client_for()
    options = post(anonymous, "login/options").data
    kwargs = {"origin": "https://evil.invalid"} if case == "origin" else {}
    if case == "rp":
        kwargs["rp_id"] = "evil.invalid"
    if case == "verification":
        kwargs["verified"] = False
    credential = authenticator.assertion(options["challenge"], create_user, **kwargs)
    if case == "signature":
        credential["response"]["signature"] = bytes_to_base64url(os.urandom(64))
    if case == "user_handle":
        credential["response"]["userHandle"] = bytes_to_base64url(uuid.uuid4().bytes)
    response = post(anonymous, "login/verify", {"credential": credential})
    assert response.status_code == 400, response.data
    assert "_auth_user_id" not in anonymous.session


def test_challenge_expiry_and_replay(create_user):
    client = client_for(create_user)
    authenticator = Authenticator()
    options = post(client, "register/options").data
    session = client.session
    session["passkey_registration"]["created_at"] -= 301
    session.save()
    credential = authenticator.registration(options["challenge"])
    assert post(client, "register/verify", {"credential": credential}).status_code == 400
    options = post(client, "register/options").data
    credential = authenticator.registration(options["challenge"])
    assert post(client, "register/verify", {"credential": credential}).status_code == 201
    assert post(client, "register/verify", {"credential": credential}).status_code == 400


def test_concurrent_session_snapshots_cannot_reuse_challenge(create_user):
    from types import SimpleNamespace
    from rest_framework.exceptions import ValidationError

    state = {"challenge": bytes_to_base64url(os.urandom(32)), "created_at": __import__("time").time()}
    first = SimpleNamespace(session={"passkey_authentication": copy.deepcopy(state)})
    second = SimpleNamespace(session={"passkey_authentication": copy.deepcopy(state)})
    consume_challenge(first, "authentication")
    with pytest.raises(ValidationError):
        consume_challenge(second, "authentication")


def test_authentication_and_csrf_are_required(create_user):
    anonymous = client_for()
    assert post(anonymous, "register/options").status_code in (401, 403)
    no_csrf = APIClient(enforce_csrf_checks=True)
    assert post(no_csrf, "login/options").status_code == 403
    client = client_for(create_user)
    client.credentials(HTTP_ORIGIN="https://evil.invalid")
    assert post(client, "register/options").status_code == 403
    assert not Passkey.objects.exists()


def test_delete_is_scoped_to_owner(create_user):
    client = client_for(create_user)
    created = register(client, Authenticator())
    other = User.objects.create(email="other-passkey@example.com", username="other-passkey")
    other_client = client_for(other)
    assert other_client.get("/auth/passkeys/", secure=True).data == []
    assert other_client.delete(f"/auth/passkeys/{created.data['id']}/", secure=True).status_code == 404
    assert Passkey.objects.count() == 1


def test_registration_excludes_existing_credential_and_requires_discoverable_key(create_user):
    client = client_for(create_user)
    authenticator = Authenticator()
    assert register(client, authenticator).status_code == 201
    options = post(client, "register/options").data
    assert options["user"]["id"] == bytes_to_base64url(create_user.id.bytes)
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["authenticatorSelection"]["userVerification"] == "required"
    assert options["excludeCredentials"][0]["id"] == bytes_to_base64url(authenticator.credential_id)
    response = post(client, "register/verify", {"credential": authenticator.registration(options["challenge"])})
    assert response.status_code == 400
    assert Passkey.objects.count() == 1


def test_passkey_auth_is_throttled():
    client = client_for()
    with (
        patch("plane.authentication.rate_limit.AuthenticationThrottle.allow_request", return_value=False),
        patch("plane.authentication.rate_limit.AuthenticationThrottle.wait", return_value=1),
    ):
        assert post(client, "login/options").status_code == 429


def test_management_does_not_consume_signin_budget(create_user):
    client = client_for(create_user)
    with patch("plane.authentication.rate_limit.AuthenticationThrottle.allow_request") as throttle:
        assert client.get("/auth/passkeys/", secure=True).status_code == 200
        throttle.assert_not_called()


@pytest.mark.parametrize("purpose", ["register", "login"])
@pytest.mark.parametrize("credential", [{}, {"id": []}, {"id": "invalid", "response": []}])
def test_malformed_credentials_return_400(create_user, purpose, credential):
    client = client_for(create_user) if purpose == "register" else client_for()
    assert post(client, f"{purpose}/options").status_code == 200
    assert post(client, f"{purpose}/verify", {"credential": credential}).status_code == 400


def test_registration_challenge_is_bound_to_user(create_user):
    client = client_for(create_user)
    options = post(client, "register/options").data
    session = client.session
    session["passkey_registration"]["user_id"] = str(uuid.uuid4())
    session.save()
    credential = Authenticator().registration(options["challenge"])
    assert post(client, "register/verify", {"credential": credential}).status_code == 400
    assert not Passkey.objects.exists()


def test_synced_authenticator_with_zero_counter_can_sign_in(create_user):
    authenticator = Authenticator()
    assert register(client_for(create_user), authenticator).status_code == 201
    for _ in range(2):
        client = client_for()
        options = post(client, "login/options").data
        credential = authenticator.assertion(options["challenge"], create_user, count=0)
        with patch("plane.authentication.views.app.passkey.post_user_auth_workflow"):
            response = post(client, "login/verify", {"credential": credential})
        assert response.status_code == 200, response.data
        assert client.session["_auth_user_id"] == str(create_user.id)
