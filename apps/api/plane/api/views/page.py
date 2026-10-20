# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.api.rate_limit import ApiKeyRateThrottle
from plane.app.views.page.base import PageViewSet
from rest_framework import status
from rest_framework.response import Response


class ProjectPageAPIEndpoint(PageViewSet):
    """Expose project pages through the API-key authenticated public API."""

    authentication_classes = [APIKeyAuthentication]
    throttle_classes = [ApiKeyRateThrottle]

    # The app serializer also accepts editor-only relations and audit fields.
    # Keep the public write surface limited to page metadata and content.
    writable_fields = {
        "name",
        "description_html",
        "access",
        "color",
        "is_locked",
        "archived_at",
        "view_props",
        "logo_props",
    }

    def _check_write_fields(self, request):
        unexpected = set(request.data) - self.writable_fields
        if unexpected:
            return Response(
                {"error": "Unsupported page fields", "fields": sorted(unexpected)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def create(self, request, *args, **kwargs):
        error = self._check_write_fields(request)
        if error is not None:
            return error
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        error = self._check_write_fields(request)
        if error is not None:
            return error
        return super().partial_update(request, *args, **kwargs)
