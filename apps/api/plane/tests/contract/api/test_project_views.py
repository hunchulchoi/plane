# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from rest_framework import status

from plane.db.models import IssueView, Project, ProjectMember


@pytest.fixture
def view_project(workspace, create_user):
    project = Project.objects.create(name="Views Project", identifier="VWS", workspace=workspace)
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20)
    return project


def views_url(workspace, project):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/views/"


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectViewAPI:
    def test_create_list_get_delete(self, api_key_client, workspace, view_project, create_user):
        url = views_url(workspace, view_project)
        created = api_key_client.post(url, {"name": "Urgent", "filters": {"priority": ["urgent"]}}, format="json")
        assert created.status_code == status.HTTP_201_CREATED, created.data
        view = IssueView.objects.get(pk=created.data["id"])
        assert view.workspace_id == workspace.id
        assert view.project_id == view_project.id
        assert view.owned_by_id == create_user.id

        listed = api_key_client.get(url)
        assert listed.status_code == status.HTTP_200_OK
        assert [item["id"] for item in listed.data] == [view.id]
        detail_url = f"{url}{view.id}/"
        assert api_key_client.get(detail_url).status_code == status.HTTP_200_OK
        assert api_key_client.delete(detail_url).status_code == status.HTTP_204_NO_CONTENT
        assert api_key_client.get(detail_url).status_code == status.HTTP_404_NOT_FOUND

    def test_rejects_cross_project_and_audit_fields(self, api_key_client, workspace, view_project):
        url = views_url(workspace, view_project)
        response = api_key_client.post(url, {"name": "Bad", "owned_by": None}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert IssueView.objects.count() == 0

        other = Project.objects.create(name="Other Project", identifier="OTH", workspace=workspace)
        assert api_key_client.get(views_url(workspace, other)).status_code == status.HTTP_404_NOT_FOUND

    def test_guest_cannot_create(self, api_key_client, workspace, view_project, create_user):
        membership = ProjectMember.objects.get(project=view_project, member=create_user)
        membership.role = 5
        membership.save()
        response = api_key_client.post(views_url(workspace, view_project), {"name": "Guest"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
