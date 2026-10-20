# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.api.views.page import ProjectPageAPIEndpoint


urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/",
        ProjectPageAPIEndpoint.as_view({"get": "list", "post": "create"}),
        name="api-project-pages",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/",
        ProjectPageAPIEndpoint.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="api-project-page",
    ),
]
