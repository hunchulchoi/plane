# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.app.views.forgejo import ForgejoRepositoryEndpoint, ForgejoRepositoryDetailEndpoint, ForgejoWebhookEndpoint

urlpatterns = [
    path("workspaces/<str:slug>/forgejo-repositories/", ForgejoRepositoryEndpoint.as_view()),
    path("workspaces/<str:slug>/forgejo-repositories/<uuid:pk>/", ForgejoRepositoryDetailEndpoint.as_view()),
    path("integrations/forgejo/<uuid:pk>/webhook/", ForgejoWebhookEndpoint.as_view()),
]
