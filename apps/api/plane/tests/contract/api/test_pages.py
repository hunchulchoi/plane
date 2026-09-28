# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from unittest.mock import patch

import pytest
from rest_framework import status

from plane.db.models import Page, Project, ProjectMember, ProjectPage


@pytest.fixture
def page_project(workspace, create_user):
    project = Project.objects.create(
        name="Pages Project",
        identifier="PAGE",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20)
    return project


def pages_url(workspace, project):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/pages/"


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectPageAPI:
    def test_create_list_retrieve_and_update_with_api_key(self, api_key_client, workspace, page_project):
        url = pages_url(workspace, page_project)
        with patch("plane.app.views.page.base.page_transaction.delay"):
            created = api_key_client.post(
                url, {"name": "Runbook", "description_html": "<p>First draft</p>"}, format="json"
            )

        assert created.status_code == status.HTTP_201_CREATED, created.data
        page_id = created.data["id"]
        assert ProjectPage.objects.filter(project=page_project, page_id=page_id).exists()

        listed = api_key_client.get(url)
        assert listed.status_code == status.HTTP_200_OK, listed.data
        assert any(page["id"] == page_id for page in listed.data)

        detail_url = f"{url}{page_id}/"
        detail = api_key_client.get(detail_url, {"track_visit": "false"})
        assert detail.status_code == status.HTTP_200_OK, detail.data
        assert detail.data["description_html"] == "<p>First draft</p>"

        with patch("plane.app.views.page.base.page_transaction.delay"):
            updated = api_key_client.patch(detail_url, {"description_html": "<p>Updated</p>"}, format="json")
        assert updated.status_code == status.HTTP_200_OK, updated.data
        assert Page.objects.get(pk=page_id).description_html == "<p>Updated</p>"

    def test_unauthenticated_request_is_rejected(self, api_client, workspace, page_project):
        response = api_client.get(pages_url(workspace, page_project))
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_member_cannot_list_or_create(self, api_key_client, workspace, create_user):
        project = Project.objects.create(name="Foreign Project", identifier="FOR", workspace=workspace)
        url = pages_url(workspace, project)
        assert api_key_client.get(url).status_code == status.HTTP_403_FORBIDDEN
        assert api_key_client.post(url, {"name": "Denied"}, format="json").status_code == status.HTTP_403_FORBIDDEN
        assert not Page.objects.filter(name="Denied").exists()

    def test_guest_cannot_create(self, api_key_client, workspace, page_project, create_user):
        ProjectMember.objects.filter(project=page_project, member=create_user).update(role=5)
        response = api_key_client.post(pages_url(workspace, page_project), {"name": "Denied"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_page_from_other_project_is_not_accessible(self, api_key_client, workspace, page_project, create_user):
        other_project = Project.objects.create(name="Other Project", identifier="OTH", workspace=workspace)
        ProjectMember.objects.create(project=other_project, workspace=workspace, member=create_user, role=20)
        page = Page.objects.create(name="Other Project Page", workspace=workspace, owned_by=create_user)
        ProjectPage.objects.create(project=other_project, page=page, workspace=workspace)

        response = api_key_client.get(f"{pages_url(workspace, page_project)}{page.id}/", {"track_visit": "false"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
