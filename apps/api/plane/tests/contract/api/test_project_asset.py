# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from unittest import mock

import pytest
from rest_framework import status

from plane.db.models import FileAsset, Page, Project, ProjectMember, ProjectPage


@pytest.fixture
def attachment_project(workspace, create_user):
    project = Project.objects.create(name="Attachment Project", identifier="ATT", workspace=workspace)
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20)
    return project


@pytest.fixture
def project_page(workspace, attachment_project, create_user):
    page = Page.objects.create(name="Runbook", workspace=workspace, owned_by=create_user)
    ProjectPage.objects.create(project=attachment_project, page=page, workspace=workspace)
    return page


def asset_url(workspace, project):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/assets/"


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectAttachmentAssetAPI:
    def test_page_document_upload_and_confirmation(self, api_key_client, workspace, attachment_project, project_page):
        with mock.patch("plane.api.views.project_asset.S3Storage") as storage:
            storage.return_value.generate_presigned_post.return_value = {
                "url": "https://storage.example/upload",
                "fields": {},
            }
            response = api_key_client.post(
                asset_url(workspace, attachment_project),
                {
                    "name": "runbook.pdf",
                    "type": "application/pdf",
                    "size": 1024,
                    "entity_type": "PAGE_DESCRIPTION",
                    "entity_identifier": str(project_page.id),
                },
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK, response.data
        asset = FileAsset.objects.get(pk=response.data["asset_id"])
        assert asset.page_id == project_page.id
        assert asset.project_id == attachment_project.id
        assert asset.entity_type == "PAGE_DESCRIPTION"
        assert asset.is_uploaded is False
        assert response.data["upload_data"]["url"] == "https://storage.example/upload"

        with mock.patch("plane.api.views.project_asset.get_asset_object_metadata.delay"):
            confirmed = api_key_client.patch(
                f"{asset_url(workspace, attachment_project)}{asset.id}/",
                {"is_uploaded": True},
                format="json",
            )
        assert confirmed.status_code == status.HTTP_204_NO_CONTENT
        asset.refresh_from_db()
        assert asset.is_uploaded is True

    def test_page_from_other_project_cannot_be_attached(
        self, api_key_client, workspace, attachment_project, project_page, create_user
    ):
        other = Project.objects.create(name="Other Project", identifier="OTH", workspace=workspace)
        ProjectMember.objects.create(project=other, workspace=workspace, member=create_user, role=20)
        response = api_key_client.post(
            asset_url(workspace, other),
            {
                "name": "runbook.pdf",
                "type": "application/pdf",
                "size": 1024,
                "entity_type": "PAGE_DESCRIPTION",
                "entity_identifier": str(project_page.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert FileAsset.objects.count() == 0

    def test_non_member_cannot_upload(self, api_key_client, workspace, project_page):
        other = Project.objects.create(name="Other Project", identifier="OTH", workspace=workspace)
        response = api_key_client.post(
            asset_url(workspace, other),
            {
                "name": "runbook.pdf",
                "type": "application/pdf",
                "size": 1024,
                "entity_type": "PAGE_DESCRIPTION",
                "entity_identifier": str(project_page.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert FileAsset.objects.count() == 0

    def test_invalid_metadata_does_not_create_asset(self, api_key_client, workspace, attachment_project, project_page):
        response = api_key_client.post(
            asset_url(workspace, attachment_project),
            {
                "name": "runbook.exe",
                "type": "application/x-msdownload",
                "size": 1024,
                "entity_type": "PAGE_DESCRIPTION",
                "entity_identifier": str(project_page.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert FileAsset.objects.count() == 0
