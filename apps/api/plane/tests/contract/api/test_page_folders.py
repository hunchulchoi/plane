# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from plane.db.models import Page, PageFolder, Project, ProjectMember, ProjectPage


@pytest.fixture
def folder_project(workspace, create_user, monkeypatch):
    monkeypatch.setattr("plane.db.mixins.soft_delete_related_objects.delay", lambda *args, **kwargs: None)
    monkeypatch.setattr("plane.app.views.page.base.page_transaction.delay", lambda *args, **kwargs: None)
    project = Project.objects.create(workspace=workspace, name="Pages", identifier="PAG")
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
    return project


def folders_url(workspace, project, folder=None):
    base = f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/page-folders/"
    return f"{base}{folder.id}/" if folder else base


@pytest.mark.contract
@pytest.mark.django_db
class TestPageFolderAPI:
    def test_folder_lifecycle_preserves_live_and_deleted_pages(
        self, api_key_client, workspace, create_user, folder_project
    ):
        url = folders_url(workspace, folder_project)
        created = api_key_client.post(url, {"name": "  Specs  "}, format="json")
        assert created.status_code == 201, created.data
        folder = PageFolder.objects.get(pk=created.data["id"])
        assert folder.name == "Specs"
        assert folder.project_id == folder_project.id
        assert folder.workspace_id == workspace.id

        pages = []
        for deleted in (False, True):
            page = Page.objects.create(workspace=workspace, owned_by=create_user, folder=folder)
            ProjectPage.objects.create(workspace=workspace, project=folder_project, page=page)
            if deleted:
                page.delete()
            pages.append(page)

        listed = api_key_client.get(url)
        assert listed.status_code == 200
        assert [str(item["id"]) for item in listed.data] == [str(folder.id)]
        detail_url = folders_url(workspace, folder_project, folder)
        assert api_key_client.get(detail_url).status_code == 200
        renamed = api_key_client.patch(detail_url, {"name": "Design"}, format="json")
        assert renamed.status_code == 200, renamed.data
        folder.refresh_from_db()
        assert folder.name == "Design"
        assert api_key_client.delete(detail_url).status_code == 204
        for page in pages:
            page.refresh_from_db()
            assert page.folder_id is None
        assert pages[0].deleted_at is None
        assert pages[1].deleted_at is not None
        assert not PageFolder.objects.filter(pk=folder.id).exists()

    def test_create_and_move_page_between_folders(self, api_key_client, workspace, folder_project):
        first, second = [
            PageFolder.objects.create(workspace=workspace, project=folder_project, name=name)
            for name in ("Specs", "Design")
        ]
        url = f"/api/v1/workspaces/{workspace.slug}/projects/{folder_project.id}/pages/"
        created = api_key_client.post(url, {"name": "Doc", "folder": str(first.id)}, format="json")
        assert created.status_code == 201, created.data
        page = Page.objects.get(pk=created.data["id"])
        assert page.folder_id == first.id
        for folder_id in (str(second.id), None):
            moved = api_key_client.patch(f"{url}{page.id}/", {"folder": folder_id}, format="json")
            assert moved.status_code == 200, moved.data
            page.refresh_from_db()
            assert str(page.folder_id) == str(folder_id)

    def test_foreign_project_folder_is_inaccessible(self, api_key_client, workspace, folder_project, create_user):
        other = Project.objects.create(workspace=workspace, name="Other", identifier="OTH")
        folder = PageFolder.objects.create(workspace=workspace, project=other, name="Other")
        url = folders_url(workspace, folder_project, folder)
        assert api_key_client.get(folders_url(workspace, folder_project)).data == []
        assert api_key_client.get(url).status_code == 404
        assert api_key_client.patch(url, {"name": "Changed"}, format="json").status_code == 404
        assert api_key_client.delete(url).status_code == 404

        pages_url = f"/api/v1/workspaces/{workspace.slug}/projects/{folder_project.id}/pages/"
        assert api_key_client.post(pages_url, {"folder": str(folder.id)}, format="json").status_code == 400
        page = Page.objects.create(workspace=workspace, owned_by=create_user)
        ProjectPage.objects.create(workspace=workspace, project=folder_project, page=page)
        response = api_key_client.patch(f"{pages_url}{page.id}/", {"folder": str(folder.id)}, format="json")
        assert response.status_code == 400
        page.refresh_from_db()
        assert page.folder_id is None

    @pytest.mark.parametrize("role", [5, 15, 20])
    def test_role_permissions(self, api_key_client, workspace, create_user, folder_project, role):
        ProjectMember.objects.filter(project=folder_project, member=create_user).update(role=role)
        folder = PageFolder.objects.create(workspace=workspace, project=folder_project, name="Specs")
        url = folders_url(workspace, folder_project, folder)
        assert api_key_client.get(url).status_code == 200
        assert api_key_client.post(
            folders_url(workspace, folder_project), {"name": "New"}, format="json"
        ).status_code == (403 if role == 5 else 201)
        assert api_key_client.patch(url, {"name": "Changed"}, format="json").status_code == (403 if role == 5 else 200)
        assert api_key_client.delete(url).status_code == (204 if role == 20 else 403)

    @pytest.mark.parametrize("membership", ["inactive", "missing"])
    def test_requires_active_membership(self, api_key_client, workspace, create_user, folder_project, membership):
        members = ProjectMember.objects.filter(project=folder_project, member=create_user)
        if membership == "inactive":
            members.update(is_active=False)
        else:
            members.delete()
        url = folders_url(workspace, folder_project)
        assert api_key_client.get(url).status_code == 403
        assert api_key_client.post(url, {"name": "Denied"}, format="json").status_code == 403

    def test_requires_api_key(self, api_client, workspace, folder_project):
        response = api_client.get(folders_url(workspace, folder_project))
        assert response.status_code in (401, 403)

    @pytest.mark.parametrize("payload", [{"name": ""}, {"name": " "}, {"name": "a" * 256}, []])
    def test_rejects_invalid_payloads(self, api_key_client, workspace, folder_project, payload):
        response = api_key_client.post(folders_url(workspace, folder_project), payload, format="json")
        assert response.status_code == 400
        assert not PageFolder.objects.filter(project=folder_project).exists()

    def test_rejects_project_reassignment(self, api_key_client, workspace, folder_project):
        url = folders_url(workspace, folder_project)
        folder = PageFolder.objects.create(workspace=workspace, project=folder_project, name="Specs")
        payload = {"name": "Changed", "project": str(workspace.id)}
        for method, target in ((api_key_client.post, url), (api_key_client.patch, f"{url}{folder.id}/")):
            response = method(target, payload, format="json")
            assert response.status_code == 400
            assert response.data["fields"] == ["project"]
        folder.refresh_from_db()
        assert folder.name == "Specs"
