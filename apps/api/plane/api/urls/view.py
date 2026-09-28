# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.api.views.view import ProjectViewAPIEndpoint


urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/views/",
        ProjectViewAPIEndpoint.as_view({"get": "list", "post": "create"}),
        name="api-project-views",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/views/<uuid:pk>/",
        ProjectViewAPIEndpoint.as_view({"get": "retrieve", "delete": "destroy"}),
        name="api-project-view",
    ),
]
