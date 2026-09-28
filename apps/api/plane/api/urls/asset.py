# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views import (
    UserAssetEndpoint,
    UserServerAssetEndpoint,
    GenericAssetEndpoint,
)
from plane.api.views.project_asset import ProjectAttachmentAssetEndpoint

urlpatterns = [
    path(
        "assets/user-assets/",
        UserAssetEndpoint.as_view(http_method_names=["post"]),
        name="user-assets",
    ),
    path(
        "assets/user-assets/<uuid:asset_id>/",
        UserAssetEndpoint.as_view(http_method_names=["patch", "delete"]),
        name="user-assets-detail",
    ),
    path(
        "assets/user-assets/server/",
        UserServerAssetEndpoint.as_view(http_method_names=["post"]),
        name="user-server-assets",
    ),
    path(
        "assets/user-assets/<uuid:asset_id>/server/",
        UserServerAssetEndpoint.as_view(http_method_names=["patch", "delete"]),
        name="user-server-assets-detail",
    ),
    path(
        "workspaces/<str:slug>/assets/",
        GenericAssetEndpoint.as_view(http_method_names=["post"]),
        name="generic-asset",
    ),
    path(
        "workspaces/<str:slug>/assets/<uuid:asset_id>/",
        GenericAssetEndpoint.as_view(http_method_names=["get", "patch"]),
        name="generic-asset-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/assets/",
        ProjectAttachmentAssetEndpoint.as_view(http_method_names=["post"]),
        name="project-attachment-asset",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/assets/<uuid:asset_id>/",
        ProjectAttachmentAssetEndpoint.as_view(http_method_names=["patch"]),
        name="project-attachment-asset-detail",
    ),
]
