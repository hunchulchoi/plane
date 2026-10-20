# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Page, PageFolder, Project, ProjectMember, ProjectPage


@pytest.fixture
def folder_project(workspace, create_user, monkeypatch):
    monkeypatch.setattr("plane.db.mixins.soft_delete_related_objects.delay", lambda *args, **kwargs: None)
    monkeypatch.setattr("plane.app.views.page.base.page_transaction.delay", lambda *args, **kwargs: None)
    project = Project.objects.create(workspace=workspace, name="Pages", identifier="PAG")
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
    return project


def _url(workspace, project, folder=None):
    base = f"/api/workspaces/{workspace.slug}/projects/{project.id}/page-folders/"
    return f"{base}{folder.id}/" if folder else base


def _page(workspace, project, owner, folder=None, **kwargs):
    page = Page.objects.create(workspace=workspace, owned_by=owner, folder=folder, name="Spec", **kwargs)
    ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return page


@pytest.mark.contract
@pytest.mark.django_db
class TestPageFolders:
    def test_create_list_rename_delete_preserves_pages(self, session_client, workspace, create_user, folder_project):
        project = folder_project
        response = session_client.post(_url(workspace, project), {"name": "  Specs  "}, format="json")
        assert response.status_code == 201
        folder = PageFolder.objects.get(pk=response.data["id"])
        assert folder.name == "Specs"
        assert folder.workspace_id == workspace.id
        assert folder.project_id == project.id
        page = _page(workspace, project, create_user, folder)
        deleted_page = _page(workspace, project, create_user, folder)
        deleted_page.delete()

        response = session_client.get(_url(workspace, project))
        assert [str(item["id"]) for item in response.data] == [str(folder.id)]
        response = session_client.patch(_url(workspace, project, folder), {"name": "Design"}, format="json")
        assert response.status_code == 200
        folder.refresh_from_db()
        assert folder.name == "Design"
        response = session_client.delete(_url(workspace, project, folder))
        assert response.status_code == 204
        page.refresh_from_db()
        deleted_page.refresh_from_db()
        assert page.folder_id is None
        assert page.deleted_at is None
        assert deleted_page.folder_id is None
        assert not PageFolder.objects.filter(pk=folder.id).exists()

    def test_create_page_in_folder_and_move_out(self, session_client, workspace, create_user, folder_project):
        project = folder_project
        folder = PageFolder.objects.create(workspace=workspace, project=project, name="Specs")
        pages_url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/"
        response = session_client.post(pages_url, {"name": "New spec", "folder": str(folder.id)}, format="json")
        assert response.status_code == 201
        page = Page.objects.get(pk=response.data["id"])
        assert page.folder_id == folder.id
        response = session_client.get(pages_url)
        assert any(str(item["id"]) == str(page.id) and item["folder"] == folder.id for item in response.data)
        response = session_client.patch(f"{pages_url}{page.id}/", {"folder": None}, format="json")
        assert response.status_code == 200
        page.refresh_from_db()
        assert page.folder_id is None
        response = session_client.patch(f"{pages_url}{page.id}/", {"folder": str(folder.id)}, format="json")
        assert response.status_code == 200
        page.refresh_from_db()
        assert page.folder_id == folder.id

    def test_folder_scoped_to_project(self, session_client, workspace, create_user, folder_project):
        other = Project.objects.create(workspace=workspace, name="Other", identifier="OTH")
        folder = PageFolder.objects.create(workspace=workspace, project=other, name="Other specs")
        project = folder_project
        assert session_client.get(_url(workspace, project)).data == []
        assert session_client.get(_url(workspace, project, folder)).status_code == 404
        assert (
            session_client.patch(_url(workspace, project, folder), {"name": "Changed"}, format="json").status_code
            == 404
        )
        assert session_client.delete(_url(workspace, project, folder)).status_code == 404
        page = _page(workspace, project, create_user)
        pages_url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/"
        assert session_client.post(pages_url, {"folder": str(folder.id)}, format="json").status_code == 400
        assert (
            session_client.patch(f"{pages_url}{page.id}/", {"folder": str(folder.id)}, format="json").status_code == 400
        )

    @pytest.mark.parametrize("role", [5, 15, 20])
    def test_folder_permissions(self, session_client, workspace, create_user, folder_project, role):
        project = folder_project
        ProjectMember.objects.filter(project=project, member=create_user).update(role=role)
        folder = PageFolder.objects.create(workspace=workspace, project=project, name="Specs")
        assert session_client.get(_url(workspace, project)).status_code == 200
        assert session_client.post(_url(workspace, project), {"name": "New"}, format="json").status_code == (
            403 if role == 5 else 201
        )
        assert session_client.patch(
            _url(workspace, project, folder), {"name": "Renamed"}, format="json"
        ).status_code == (403 if role == 5 else 200)
        assert session_client.delete(_url(workspace, project, folder)).status_code == (204 if role == 20 else 403)

    def test_inactive_member_denied(self, session_client, workspace, create_user, folder_project):
        ProjectMember.objects.filter(project=folder_project, member=create_user).update(is_active=False)
        assert session_client.get(_url(workspace, folder_project)).status_code == 403
