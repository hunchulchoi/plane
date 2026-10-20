# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import json
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

    def test_public_api_rejects_editor_relations_and_audit_fields(
        self, api_key_client, workspace, page_project, create_user
    ):
        response = api_key_client.post(
            pages_url(workspace, page_project),
            {"name": "Invalid", "parent": str(create_user.id), "created_by": str(create_user.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["fields"] == ["created_by", "parent"]
        assert not Page.objects.filter(name="Invalid").exists()

    def test_description_html_update_invalidates_binary(self, api_key_client, workspace, page_project):
        url = pages_url(workspace, page_project)
        with patch("plane.app.views.page.base.page_transaction.delay"):
            created = api_key_client.post(
                url, {"name": "Doc", "description_html": "<p>v1</p>"}, format="json"
            )
        page_id = created.data["id"]
        page = Page.objects.get(pk=page_id)
        page.description_binary = b"\x00\x01stale"
        page.description_json = {"content": [{"type": "paragraph"}]}
        page.save()

        with (
            patch("plane.app.views.page.base.page_transaction.delay"),
            patch("plane.app.views.page.base.redis_instance") as mock_redis,
        ):
            updated = api_key_client.patch(
                f"{url}{page_id}/", {"description_html": "<p>v2</p>"}, format="json"
            )
        assert updated.status_code == status.HTTP_200_OK, updated.data
        page.refresh_from_db()
        assert page.description_binary is None
        assert page.description_json == {}

        # Open editor sessions are notified so they can reload the document
        mock_redis.return_value.publish.assert_called_once()
        channel, payload = mock_redis.return_value.publish.call_args[0]
        assert channel == "hocuspocus:admin"
        assert json.loads(payload)["command"] == "restart_document"
        assert json.loads(payload)["docId"] == str(page_id)

        # Re-sending identical content must not invalidate the binary again
        page.description_binary = b"\x00\x01fresh"
        page.save()
        with (
            patch("plane.app.views.page.base.page_transaction.delay"),
            patch("plane.app.views.page.base.redis_instance") as mock_redis,
        ):
            api_key_client.patch(f"{url}{page_id}/", {"description_html": "<p>v2</p>"}, format="json")
        page.refresh_from_db()
        assert page.description_binary is not None
        mock_redis.return_value.publish.assert_not_called()

    def test_metadata_update_preserves_binary(self, api_key_client, workspace, page_project):
        url = pages_url(workspace, page_project)
        with patch("plane.app.views.page.base.page_transaction.delay"):
            created = api_key_client.post(url, {"name": "Doc", "description_html": "<p>v1</p>"}, format="json")
        page = Page.objects.get(pk=created.data["id"])
        page.description_binary = b"\x00\x01binary"
        page.save()

        updated = api_key_client.patch(f"{url}{page.id}/", {"name": "Renamed"}, format="json")
        assert updated.status_code == status.HTTP_200_OK, updated.data
        page.refresh_from_db()
        assert page.description_binary is not None
        assert page.name == "Renamed"

    def test_page_from_other_project_is_not_accessible(self, api_key_client, workspace, page_project, create_user):
        other_project = Project.objects.create(name="Other Project", identifier="OTH", workspace=workspace)
        ProjectMember.objects.create(project=other_project, workspace=workspace, member=create_user, role=20)
        page = Page.objects.create(name="Other Project Page", workspace=workspace, owned_by=create_user)
        ProjectPage.objects.create(project=other_project, page=page, workspace=workspace)

        response = api_key_client.get(f"{pages_url(workspace, page_project)}{page.id}/", {"track_visit": "false"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
