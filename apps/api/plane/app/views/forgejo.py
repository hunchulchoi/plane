# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import hmac
import json
import re
import secrets
from urllib.parse import urlsplit

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import SimpleRateThrottle

from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.db.models import ForgejoDelivery, ForgejoRepository, Issue, IssueLink, Project
from plane.license.utils.encryption import decrypt_data, encrypt_data


def repository_url(value):
    """Canonical HTTPS owner/repo URL. No outbound requests or API tokens."""
    if not isinstance(value, str) or len(value) > 500:
        raise serializers.ValidationError("Enter an HTTPS repository URL.")
    try:
        parts = urlsplit(value.strip().rstrip("/"))
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", parts.path)
            or any(segment in (".", "..") for segment in parts.path.split("/")[1:])
        ):
            raise ValueError
        # Accessing port validates malformed/non-numeric ports, too.
        port = parts.port
    except ValueError as exc:
        raise serializers.ValidationError("Enter an HTTPS repository URL (https://host/owner/repo).") from exc
    path = parts.path.removesuffix(".git")
    if not path.rsplit("/", 1)[-1]:
        raise serializers.ValidationError("Enter a repository name.")
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    return f"https://{host}{f':{port}' if port and port != 443 else ''}{path}"


class RepositoryInput(serializers.Serializer):
    project_id = serializers.UUIDField()
    repository_url = serializers.CharField(max_length=500)

    def validate_repository_url(self, value):
        return repository_url(value)


def representation(repo, secret=None):
    result = {
        "id": str(repo.id),
        "project_id": str(repo.project_id),
        "project_name": repo.project.name,
        "repository_url": repo.repository_url,
        "webhook_url": f"{settings.WEB_URL.rstrip('/')}/api/integrations/forgejo/{repo.id}/webhook/",
        "last_received_at": repo.last_received_at,
    }
    if secret:
        result["secret"] = secret
    return result


class ForgejoRepositoryEndpoint(BaseAPIView):
    http_method_names = ["get", "post", "head", "options"]

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        repos = (
            ForgejoRepository.objects.filter(
                project__workspace__slug=slug,
                project__deleted_at__isnull=True,
                project__project_projectmember__member=request.user,
                project__project_projectmember__is_active=True,
                project__project_projectmember__deleted_at__isnull=True,
            )
            .select_related("project")
            .distinct()
        )
        return Response([representation(repo) for repo in repos])

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        serializer = RepositoryInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(
            Project.objects.filter(
                workspace__slug=slug,
                archived_at__isnull=True,
                project_projectmember__member=request.user,
                project_projectmember__is_active=True,
                project_projectmember__deleted_at__isnull=True,
            ).distinct(),
            id=serializer.validated_data["project_id"],
        )
        secret = secrets.token_hex(32)
        encrypted = encrypt_data(secret)
        if not encrypted:
            return Response({"error": "Could not secure webhook secret."}, status=503)
        try:
            with transaction.atomic():
                repo = ForgejoRepository.objects.create(
                    project=project, repository_url=serializer.validated_data["repository_url"], secret=encrypted
                )
        except IntegrityError:
            return Response({"error": "This repository is already connected to the project."}, status=409)
        return Response(representation(repo, secret), status=201, headers={"Cache-Control": "no-store"})


class ForgejoRepositoryDetailEndpoint(BaseAPIView):
    http_method_names = ["delete", "options"]

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def delete(self, request, slug, pk):
        repo = get_object_or_404(
            ForgejoRepository,
            pk=pk,
            project__workspace__slug=slug,
            project__deleted_at__isnull=True,
            project__project_projectmember__member=request.user,
            project__project_projectmember__is_active=True,
            project__project_projectmember__deleted_at__isnull=True,
        )
        repo.delete()
        return Response(status=204)


def source_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        timestamp = parse_datetime(value)
    except ValueError:
        return None
    return timestamp if timestamp is not None and timezone.is_aware(timestamp) else None


def event_links(payload, event, repo):
    """Derive trusted URLs from the configured repository, never payload URLs."""
    if event == "push":
        commits = payload.get("commits", [])
        if not isinstance(commits, list) or len(commits) > 2000:
            raise serializers.ValidationError("Invalid commits list (maximum 2000).")
        for commit in commits:
            if not isinstance(commit, dict):
                raise serializers.ValidationError("Invalid commit.")
            sha, message = commit.get("id"), commit.get("message", "")
            if not isinstance(sha, str) or not re.fullmatch(r"(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})", sha):
                raise serializers.ValidationError("Invalid commit ID.")
            if not isinstance(message, str):
                raise serializers.ValidationError("Invalid commit message.")
            title = f"Forgejo commit {sha[:8]}: {message.splitlines()[0] if message else ''}"
            yield message, f"{repo.repository_url}/commit/{sha}", title, {"kind": "commit", "sha": sha}
    elif event == "pull_request":
        pr = payload.get("pull_request")
        if not isinstance(pr, dict):
            raise serializers.ValidationError("Invalid pull request.")
        number = pr.get("number") or payload.get("number")
        title, body = pr.get("title", ""), pr.get("body") or ""
        if type(number) is not int or number < 1 or not isinstance(title, str) or not isinstance(body, str):
            raise serializers.ValidationError("Invalid pull request fields.")
        state = "merged" if pr.get("merged") is True else pr.get("state", "open")
        if state not in ("open", "closed", "merged"):
            raise serializers.ValidationError("Invalid pull request state.")
        updated_at = pr.get("updated_at")
        if updated_at is not None and source_timestamp(updated_at) is None:
            raise serializers.ValidationError("Invalid pull request update timestamp.")
        yield (
            f"{title}\n{body}",
            f"{repo.repository_url}/pulls/{number}",
            f"Forgejo PR #{number} [{state}]: {title}",
            {"kind": "pull_request", "number": number, "state": state, "source_updated_at": updated_at},
        )


class ForgejoWebhookThrottle(SimpleRateThrottle):
    scope = "forgejo_webhook"
    rate = "120/minute"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": f"{view.kwargs['pk']}:{self.get_ident(request)}"}


class ForgejoWebhookEndpoint(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ForgejoWebhookThrottle]

    def post(self, request, pk):
        # Read raw bytes before DRF parsing: signatures cover the exact body.
        if len(request.body) > 2 * 1024 * 1024:
            return Response({"error": "Payload too large."}, status=413)
        with transaction.atomic():
            # Serializes retries and link updates for this mapping.
            repo = get_object_or_404(
                ForgejoRepository.objects.select_for_update(of=("self",)),
                pk=pk,
                project__deleted_at__isnull=True,
                project__archived_at__isnull=True,
                project__workspace__deleted_at__isnull=True,
            )
            secret = decrypt_data(repo.secret)
            signature = request.headers.get("X-Forgejo-Signature") or request.headers.get("X-Gitea-Signature", "")
            expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
            if (
                not secret
                or not re.fullmatch(r"[a-fA-F0-9]{64}", signature)
                or not hmac.compare_digest(expected, signature.lower())
            ):
                return Response({"error": "Invalid webhook signature."}, status=403)
            try:
                payload = json.loads(request.body)
            except (ValueError, UnicodeDecodeError):
                return Response({"error": "Invalid JSON."}, status=400)
            if not isinstance(payload, dict):
                return Response({"error": "Expected a JSON object."}, status=400)
            repository = payload.get("repository")
            if not isinstance(repository, dict) or repository_url(repository.get("html_url")) != repo.repository_url:
                return Response({"error": "Repository does not match this connection."}, status=400)
            event = request.headers.get("X-Forgejo-Event") or request.headers.get("X-Gitea-Event")
            if event not in ("push", "pull_request", "ping"):
                return Response({"ignored": True})
            delivery = request.headers.get("X-Forgejo-Delivery") or request.headers.get("X-Gitea-Delivery")
            delivery = delivery or hashlib.sha256(request.body).hexdigest()
            if len(delivery) > 128:
                return Response({"error": "Invalid delivery ID."}, status=400)
            if ForgejoDelivery.objects.filter(repository=repo, delivery_id=delivery).exists():
                return Response({"duplicate": True})
            # Validate all items before creating any links.
            items = list(event_links(payload, event, repo))
            identifier = repo.project.identifier
            pattern = re.compile(rf"(?<![\w-]){re.escape(identifier)}-([1-9][0-9]{{0,17}})(?![\w-])", re.IGNORECASE)
            linked = 0
            for text, url, title, metadata in items:
                sequences = {int(match) for match in pattern.findall(text)}
                # Existing PR links also receive close/merge updates if its text changed.
                issues = Issue.issue_objects.filter(project_id=repo.project_id, sequence_id__in=sequences)
                issue_ids = set(issues.values_list("id", flat=True))
                issue_ids.update(
                    IssueLink.objects.filter(
                        project_id=repo.project_id, url=url, metadata__provider="forgejo"
                    ).values_list("issue_id", flat=True)
                )
                for issue in Issue.issue_objects.filter(project_id=repo.project_id, id__in=issue_ids):
                    link = IssueLink.objects.filter(issue=issue, url=url).first()
                    fields = {
                        "title": title[:255],
                        "metadata": {"provider": "forgejo", "forgejo_repository_id": str(repo.id), **metadata},
                    }
                    if link is None:
                        IssueLink.objects.create(project=repo.project, issue=issue, url=url, **fields)
                    elif isinstance(link.metadata, dict) and link.metadata.get("provider") == "forgejo":
                        previous_time = source_timestamp(link.metadata.get("source_updated_at"))
                        next_time = source_timestamp(metadata.get("source_updated_at"))
                        if previous_time and (not next_time or previous_time > next_time):
                            continue
                        for key, value in fields.items():
                            setattr(link, key, value)
                        link.save(update_fields=["title", "metadata", "updated_at"])
                    else:
                        continue
                    linked += 1
            ForgejoDelivery.objects.create(repository=repo, delivery_id=delivery)
            repo.last_received_at = timezone.now()
            repo.save(update_fields=["last_received_at"])
            return Response({"linked": linked})
