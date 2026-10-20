# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from plane.api.views.base import BaseViewSet
from plane.app.serializers.view import IssueViewSerializer
from plane.db.models import IssueView, Project, ProjectMember, UserFavorite, UserRecentVisit


class ProjectViewAPIEndpoint(BaseViewSet):
    """Project custom views for API-key clients."""

    model = IssueView
    serializer_class = IssueViewSerializer
    writable_fields = {"name", "description", "filters"}

    def project_and_membership(self):
        project = Project.objects.filter(
            id=self.kwargs["project_id"],
            workspace__slug=self.kwargs["slug"],
            archived_at__isnull=True,
        ).first()
        if project is None:
            raise NotFound("Project not found")
        membership = ProjectMember.objects.filter(project=project, member=self.request.user, is_active=True).first()
        if membership is None:
            raise NotFound("Project not found")
        return project, membership

    def visible_views(self, project, membership):
        views = IssueView.objects.filter(project=project, workspace=project.workspace).filter(
            Q(owned_by=self.request.user) | Q(access=1)
        )
        if membership.role == 5 and not project.guest_view_all_features:
            views = views.filter(owned_by=self.request.user)
        return views

    def list(self, request, *args, **kwargs):
        project, membership = self.project_and_membership()
        views = self.visible_views(project, membership).order_by("name")
        return Response(self.get_serializer(views, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        project, membership = self.project_and_membership()
        view = self.visible_views(project, membership).filter(pk=kwargs["pk"]).first()
        if view is None:
            raise NotFound("View not found")
        return Response(self.get_serializer(view).data)

    def create(self, request, *args, **kwargs):
        project, membership = self.project_and_membership()
        if membership.role not in (15, 20):
            raise PermissionDenied("Project members cannot create views")
        extra_fields = set(request.data) - self.writable_fields
        if extra_fields:
            raise ValidationError({"fields": sorted(extra_fields)})
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        view = serializer.save(project=project, workspace=project.workspace, owned_by=request.user)
        return Response(self.get_serializer(view).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        project, membership = self.project_and_membership()
        view = self.visible_views(project, membership).filter(pk=kwargs["pk"]).first()
        if view is None:
            raise NotFound("View not found")
        if membership.role != 20 and view.owned_by_id != request.user.id:
            raise PermissionDenied("Only an admin or the view owner can delete this view")
        view.delete()
        UserFavorite.objects.filter(project=project, entity_identifier=view.id, entity_type="view").delete()
        UserRecentVisit.objects.filter(project=project, entity_identifier=view.id, entity_name="view").delete(
            soft=False
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
