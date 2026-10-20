# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ProjectPagePermission
from plane.app.serializers.page import PageFolderSerializer
from plane.db.models import Page, PageFolder, Project
from ..base import BaseAPIView


class PageFolderEndpoint(BaseAPIView):
    permission_classes = [ProjectPagePermission]

    def get_queryset(self):
        return PageFolder.objects.filter(workspace__slug=self.kwargs["slug"], project_id=self.kwargs["project_id"])

    def get(self, request, slug, project_id, folder_id=None):
        if folder_id:
            folder = get_object_or_404(self.get_queryset(), pk=folder_id)
            return Response(PageFolderSerializer(folder).data)
        return Response(PageFolderSerializer(self.get_queryset(), many=True).data)

    def post(self, request, slug, project_id, folder_id=None):
        if folder_id:
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
        project = get_object_or_404(Project, pk=project_id, workspace__slug=slug)
        serializer = PageFolderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project, workspace_id=project.workspace_id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def patch(self, request, slug, project_id, folder_id=None):
        folder = get_object_or_404(self.get_queryset(), pk=folder_id)
        serializer = PageFolderSerializer(folder, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, slug, project_id, folder_id=None):
        folder = get_object_or_404(self.get_queryset(), pk=folder_id)
        with transaction.atomic():
            # Clear soft-deleted pages too, so restoring a page cannot restore a deleted folder link.
            Page.all_objects.filter(folder=folder).update(folder=None)
            folder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
