# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.bgtasks.storage_metadata_task import get_asset_object_metadata
from plane.db.models import DraftIssue, FileAsset, Issue, IssueComment, Page, Project
from plane.settings.storage import S3Storage
from plane.utils.path_validator import sanitize_filename


class ProjectAttachmentAssetEndpoint(BaseAPIView):
    """Upload and confirm project attachments using an API key."""

    entity_fields = {
        FileAsset.EntityTypeContext.ISSUE_ATTACHMENT: "issue",
        FileAsset.EntityTypeContext.ISSUE_DESCRIPTION: "issue",
        FileAsset.EntityTypeContext.COMMENT_DESCRIPTION: "comment",
        FileAsset.EntityTypeContext.PAGE_DESCRIPTION: "page",
        FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION: "draft_issue",
    }

    def _project(self, request, slug, project_id):
        return Project.objects.filter(
            id=project_id,
            workspace__slug=slug,
            archived_at__isnull=True,
            project_projectmember__member=request.user,
            project_projectmember__is_active=True,
        ).first()

    def _entity_exists(self, entity_type, entity_id, slug, project_id, user):
        if entity_type in (
            FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
            FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
        ):
            return Issue.objects.filter(id=entity_id, workspace__slug=slug, project_id=project_id).exists()
        if entity_type == FileAsset.EntityTypeContext.COMMENT_DESCRIPTION:
            return IssueComment.objects.filter(id=entity_id, workspace__slug=slug, project_id=project_id).exists()
        if entity_type == FileAsset.EntityTypeContext.PAGE_DESCRIPTION:
            return Page.objects.filter(
                Q(owned_by=user) | Q(access=Page.PUBLIC_ACCESS),
                id=entity_id,
                workspace__slug=slug,
                project_pages__project_id=project_id,
                project_pages__deleted_at__isnull=True,
            ).exists()
        if entity_type == FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION:
            return DraftIssue.objects.filter(id=entity_id, workspace__slug=slug, created_by=user).exists()
        return False

    def post(self, request, slug, project_id):
        project = self._project(request, slug, project_id)
        if project is None:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        name = sanitize_filename(request.data.get("name"))
        mime_type = request.data.get("type")
        entity_type = request.data.get("entity_type")
        try:
            size = int(request.data.get("size"))
            entity_id = uuid.UUID(str(request.data.get("entity_identifier")))
        except (TypeError, ValueError, AttributeError):
            return Response({"error": "Invalid size or entity identifier"}, status=status.HTTP_400_BAD_REQUEST)

        if not name or mime_type not in settings.ATTACHMENT_MIME_TYPES or not (0 < size <= settings.FILE_SIZE_LIMIT):
            return Response({"error": "Invalid file metadata"}, status=status.HTTP_400_BAD_REQUEST)
        if entity_type not in self.entity_fields or not self._entity_exists(
            entity_type, entity_id, slug, project_id, request.user
        ):
            return Response({"error": "Entity not found"}, status=status.HTTP_404_NOT_FOUND)

        asset_key = f"{project.workspace_id}/{uuid.uuid4().hex}-{name}"
        asset = FileAsset(
            attributes={"name": name, "type": mime_type, "size": size},
            asset=asset_key,
            size=size,
            workspace_id=project.workspace_id,
            project_id=project_id,
            entity_type=entity_type,
            **{f"{self.entity_fields[entity_type]}_id": entity_id},
        )
        asset.save(created_by_id=request.user.id)
        storage = S3Storage(request=request)
        upload_data = storage.generate_presigned_post(object_name=asset_key, file_type=mime_type, file_size=size)
        return Response(
            {"upload_data": upload_data, "asset_id": str(asset.id), "asset_url": asset.asset_url},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, asset_id):
        if self._project(request, slug, project_id) is None:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
        asset = FileAsset.objects.filter(
            id=asset_id,
            workspace__slug=slug,
            project_id=project_id,
            created_by=request.user,
            is_deleted=False,
        ).first()
        if asset is None:
            return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)
        asset.is_uploaded = True
        asset.save(update_fields=["is_uploaded"])
        if not asset.storage_metadata:
            get_asset_object_metadata.delay(asset_id=str(asset_id))
        return Response(status=status.HTTP_204_NO_CONTENT)
