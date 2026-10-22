# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import time
from hmac import compare_digest
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from plane.authentication.rate_limit import AuthenticationThrottle
from plane.authentication.session import BaseSessionAuthentication
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.authentication.utils.redirection_path import get_redirection_path
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.db.models import Passkey
from plane.license.models import Instance
from plane.utils.path_validator import get_safe_redirect_url

CHALLENGE_TTL = 300


class PasskeyManagementThrottle(UserRateThrottle):
    scope = "passkey_management"
    rate = "30/minute"


def relying_party():
    # Never derive credential scope from an incoming Host or Origin header.
    url = urlsplit(settings.WEB_URL or "")
    if not url.hostname or (url.scheme != "https" and not (url.scheme == "http" and url.hostname == "localhost")):
        raise ValidationError("Passkeys require a configured HTTPS WEB_URL.")
    return url.hostname, f"{url.scheme}://{url.netloc}"


def remember_challenge(request, purpose, options):
    request.session[f"passkey_{purpose}"] = {
        "challenge": bytes_to_base64url(options.challenge),
        "created_at": time.time(),
        "user_id": str(request.user.id) if request.user.is_authenticated else None,
    }


def consume_challenge(request, purpose):
    state = request.session.pop(f"passkey_{purpose}", None)
    if not state or not 0 <= time.time() - state["created_at"] <= CHALLENGE_TTL:
        raise ValidationError("Passkey request expired. Please try again.")
    if purpose == "registration" and state["user_id"] != str(request.user.id):
        raise ValidationError("Passkey request belongs to another account.")
    # Session pop alone is not atomic across requests. Redis ADD claims a challenge
    # once, even when concurrent requests loaded the same session state.
    if not cache.add(f"passkey:used:{state['challenge']}", True, timeout=CHALLENGE_TTL):
        raise ValidationError("Passkey request was already used.")
    return base64url_to_bytes(state["challenge"])


class CredentialInput(serializers.Serializer):
    credential = serializers.DictField()


class RegistrationInput(CredentialInput):
    name = serializers.CharField(max_length=100, default="Passkey")


class PasskeyView(APIView):
    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [AuthenticationThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            # Explicitly check tokens for anonymous login too (login CSRF).
            SessionAuthentication().enforce_csrf(request)
        if not Instance.objects.filter(is_setup_done=True).exists():
            raise PermissionDenied("Instance is not configured.")
        if request.user.is_authenticated and request.user.is_bot:
            raise PermissionDenied("Passkeys require a human account.")


class PasskeyRegistrationOptions(PasskeyView):
    def post(self, request):
        rp_id, _ = relying_party()
        options = generate_registration_options(
            rp_id=rp_id,
            rp_name="Plane",
            user_id=request.user.id.bytes,
            user_name=request.user.email,
            user_display_name=request.user.display_name or request.user.email,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=base64url_to_bytes(key.credential_id))
                for key in Passkey.objects.filter(user=request.user)
            ],
        )
        remember_challenge(request, "registration", options)
        return Response(json.loads(options_to_json(options)))


class PasskeyRegistrationVerify(PasskeyView):
    def post(self, request):
        serializer = RegistrationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.validated_data["credential"]
        challenge = consume_challenge(request, "registration")
        rp_id, origin = relying_party()
        try:
            verified = verify_registration_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=rp_id,
                expected_origin=origin,
                require_user_verification=True,
            )
        except (WebAuthnException, ValueError, TypeError, KeyError, AttributeError):
            raise ValidationError("Passkey registration could not be verified.") from None
        if len(verified.credential_id) > 1023:
            raise ValidationError("Invalid credential ID.")
        transports = credential.get("response", {}).get("transports", [])
        if (
            not isinstance(transports, list)
            or len(transports) > 10
            or any(not isinstance(item, str) or len(item) > 32 for item in transports)
        ):
            raise ValidationError("Invalid authenticator transports.")
        try:
            with transaction.atomic():
                key = Passkey.objects.create(
                    user=request.user,
                    name=serializer.validated_data["name"],
                    credential_id=bytes_to_base64url(verified.credential_id),
                    public_key=verified.credential_public_key,
                    sign_count=verified.sign_count,
                    transports=transports,
                    device_type=verified.credential_device_type.value,
                    backed_up=verified.credential_backed_up,
                )
        except IntegrityError:
            raise ValidationError("This passkey is already registered.") from None
        return Response({"id": str(key.id), "name": key.name}, status=201)


class PasskeyAuthenticationOptions(PasskeyView):
    permission_classes = [AllowAny]

    def post(self, request):
        rp_id, _ = relying_party()
        options = generate_authentication_options(rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED)
        remember_challenge(request, "authentication", options)
        return Response(json.loads(options_to_json(options)))


class PasskeyAuthenticationVerify(PasskeyView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CredentialInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.validated_data["credential"]
        challenge = consume_challenge(request, "authentication")
        rp_id, origin = relying_party()
        credential_id = credential.get("id")
        if not isinstance(credential_id, str) or len(credential_id) > 1400:
            raise ValidationError("Passkey sign-in could not be verified.")
        try:
            with transaction.atomic():
                key = Passkey.objects.select_for_update().get(
                    credential_id=credential_id, user__is_active=True, user__is_bot=False
                )
                user = key.user
                handle = credential.get("response", {}).get("userHandle")
                if not isinstance(handle, str) or not compare_digest(base64url_to_bytes(handle), user.id.bytes):
                    raise ValueError("Account mismatch")
                verified = verify_authentication_response(
                    credential=credential,
                    expected_challenge=challenge,
                    expected_rp_id=rp_id,
                    expected_origin=origin,
                    credential_public_key=bytes(key.public_key),
                    credential_current_sign_count=key.sign_count,
                    require_user_verification=True,
                )
                key.sign_count = verified.new_sign_count
                key.device_type = verified.credential_device_type.value
                key.backed_up = verified.credential_backed_up
                key.last_used_at = timezone.now()
                key.save(update_fields=["sign_count", "device_type", "backed_up", "last_used_at"])
        except (Passkey.DoesNotExist, WebAuthnException, ValueError, TypeError, KeyError, AttributeError):
            raise ValidationError("Passkey sign-in could not be verified.") from None
        post_user_auth_workflow(user=user, is_signup=False, request=request)
        user_login(request=request, user=user, is_app=True)
        return Response(
            {
                "redirect_url": get_safe_redirect_url(
                    base_url=base_host(request=request, is_app=True),
                    next_path=get_redirection_path(user=user),
                    params={},
                )
            }
        )


class PasskeyList(PasskeyView):
    throttle_classes = [PasskeyManagementThrottle]

    def get(self, request):
        return Response(
            list(Passkey.objects.filter(user=request.user).values("id", "name", "created_at", "last_used_at"))
        )


class PasskeyDetail(PasskeyView):
    throttle_classes = [PasskeyManagementThrottle]

    def delete(self, request, key_id):
        key = get_object_or_404(Passkey, id=key_id, user=request.user)
        key.delete()
        return Response(status=204)
