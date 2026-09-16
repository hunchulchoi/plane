# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract coverage for project-scoped asset uploads."""

import base64
from unittest import mock
from uuid import uuid4

import pytest
from requests import Timeout
from rest_framework import status

from plane.db.models import FileAsset, Page, Project, ProjectMember, ProjectPage

S3_STORAGE_PATH = "plane.app.views.asset.v2.S3Storage"


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Asset Project",
        identifier="ASSET",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        project=project,
        member=create_user,
        workspace=workspace,
        role=20,
    )
    return project


@pytest.fixture
def page(db, workspace, project, create_user):
    page = Page.objects.create(
        workspace=workspace,
        owned_by=create_user,
        name="Attachment page",
    )
    ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return page


def collection_url(workspace, project):
    return f"/api/assets/v2/workspaces/{workspace.slug}/projects/{project.id}/"


def upload_payload(page, mime_type="application/pdf", size=1024):
    return {
        "name": "attachment.pdf",
        "type": mime_type,
        "size": size,
        "entity_type": FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
        "entity_identifier": str(page.id),
    }


def detail_url(workspace, project, asset):
    return f"{collection_url(workspace, project)}{asset.id}/"


def page_description_url(workspace, project, page):
    return (
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/"
        f"pages/{page.id}/description/"
    )


@pytest.mark.contract
class TestProjectAssetUpload:
    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "mime_type",
        [
            "image/png",
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/markdown",
            "application/zip",
        ],
    )
    def test_page_asset_accepts_plane_attachment_types(
        self, session_client, workspace, project, page, mime_type
    ):
        payload = upload_payload(page, mime_type=mime_type)

        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            mock_storage.return_value.generate_presigned_post.return_value = {
                "url": "https://storage.example/upload",
                "fields": {"key": "asset-key"},
            }
            response = session_client.post(
                collection_url(workspace, project), payload, format="json"
            )

        assert response.status_code == status.HTTP_200_OK
        asset = FileAsset.objects.get(id=response.data["asset_id"])
        assert asset.page_id == page.id
        assert asset.attributes["type"] == mime_type
        mock_storage.return_value.generate_presigned_post.assert_called_once()

    @pytest.mark.django_db
    def test_project_cover_remains_image_only(
        self, session_client, workspace, project
    ):
        payload = {
            "name": "cover.pdf",
            "type": "application/pdf",
            "size": 1024,
            "entity_type": FileAsset.EntityTypeContext.PROJECT_COVER,
            "entity_identifier": str(project.id),
        }

        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            response = session_client.post(
                collection_url(workspace, project), payload, format="json"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert FileAsset.objects.filter(project=project).count() == 0
        mock_storage.return_value.generate_presigned_post.assert_not_called()

    @pytest.mark.django_db
    @pytest.mark.parametrize("size", [0, "not-a-number"])
    def test_invalid_size_is_rejected(
        self, session_client, workspace, project, page, size
    ):
        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            response = session_client.post(
                collection_url(workspace, project),
                upload_payload(page, size=size),
                format="json",
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert FileAsset.objects.filter(project=project).count() == 0
        mock_storage.return_value.generate_presigned_post.assert_not_called()

    @pytest.mark.django_db
    def test_file_larger_than_instance_limit_is_rejected(
        self, settings, session_client, workspace, project, page
    ):
        settings.FILE_SIZE_LIMIT = 100

        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            response = session_client.post(
                collection_url(workspace, project),
                upload_payload(page, size=101),
                format="json",
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert FileAsset.objects.filter(project=project).count() == 0
        mock_storage.return_value.generate_presigned_post.assert_not_called()

    @pytest.mark.django_db
    def test_post_to_asset_detail_returns_400_without_side_effects(
        self, session_client, workspace, project
    ):
        detail_url = f"{collection_url(workspace, project)}{uuid4()}/"

        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            response = session_client.post(detail_url, {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            "error": "POST is not allowed on an existing asset.",
            "status": False,
        }
        assert FileAsset.objects.filter(project=project).count() == 0
        mock_storage.return_value.generate_presigned_post.assert_not_called()

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        ("mime_type", "expected_disposition"),
        [("image/png", "inline"), ("application/pdf", "attachment")],
    )
    def test_page_asset_disposition_depends_on_mime_type(
        self,
        session_client,
        workspace,
        project,
        page,
        create_user,
        mime_type,
        expected_disposition,
    ):
        asset = FileAsset.objects.create(
            attributes={"name": "page-asset", "type": mime_type, "size": 100},
            asset=f"{workspace.id}/page-asset",
            size=100,
            workspace=workspace,
            project=project,
            page=page,
            created_by=create_user,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
            is_uploaded=True,
        )

        with mock.patch(S3_STORAGE_PATH) as mock_storage:
            mock_storage.return_value.generate_presigned_url.return_value = (
                "https://storage.example/download"
            )
            response = session_client.get(detail_url(workspace, project, asset))

        assert response.status_code == status.HTTP_302_FOUND
        mock_storage.return_value.generate_presigned_url.assert_called_once_with(
            object_name=asset.asset.name,
            disposition=expected_disposition,
            filename="page-asset",
        )


@pytest.mark.contract
class TestPageDescriptionRegeneration:
    @pytest.mark.django_db
    def test_regenerate_binary_converts_and_saves_all_editor_formats(
        self, settings, session_client, workspace, project, page
    ):
        settings.LIVE_URL = "http://live:3000/live/"
        encoded_binary = base64.b64encode(b"valid-yjs-update").decode()
        conversion_response = mock.Mock()
        conversion_response.json.return_value = {
            "description_binary": encoded_binary,
            "description_json": {"type": "doc", "content": []},
        }
        html = (
            '<p>Existing content</p><image-component id="asset-id" '
            'src="/api/assets/image-id/" status="uploaded"></image-component><p></p>'
        )

        with (
            mock.patch(
                "plane.app.views.page.base.requests.post",
                return_value=conversion_response,
            ) as convert,
            mock.patch("plane.app.views.page.base.page_transaction.delay"),
            mock.patch("plane.app.views.page.base.track_page_version.delay"),
        ):
            response = session_client.patch(
                page_description_url(workspace, project, page),
                {"description_html": html, "regenerate_binary": True},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        page.refresh_from_db()
        assert bytes(page.description_binary) == b"valid-yjs-update"
        assert page.description_json == {"type": "doc", "content": []}
        assert "<image-component" in page.description_html
        convert.assert_called_once_with(
            "http://live:3000/live/convert-document/",
            json={"description_html": page.description_html, "variant": "document"},
            timeout=10,
        )
        conversion_response.raise_for_status.assert_called_once_with()

    @pytest.mark.django_db
    def test_regenerate_binary_failure_does_not_change_page(
        self, settings, session_client, workspace, project, page
    ):
        settings.LIVE_URL = "http://live:3000/live/"
        original_html = page.description_html

        with mock.patch(
            "plane.app.views.page.base.requests.post",
            side_effect=Timeout,
        ):
            response = session_client.patch(
                page_description_url(workspace, project, page),
                {"description_html": "<p>new</p>", "regenerate_binary": True},
                format="json",
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        page.refresh_from_db()
        assert page.description_html == original_html
        assert page.description_binary is None
