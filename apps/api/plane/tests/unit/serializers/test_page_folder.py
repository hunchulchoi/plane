# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from plane.app.serializers.page import PageFolderSerializer, PageSerializer


@pytest.mark.unit
class TestPageFolderSerializer:
    @pytest.mark.parametrize("name", ["", "   ", "a" * 256])
    def test_invalid_names(self, name):
        serializer = PageFolderSerializer(data={"name": name})
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_trim_name(self):
        serializer = PageFolderSerializer(data={"name": "  Product specs  "})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["name"] == "Product specs"

    def test_folder_project_scope(self):
        project_id = uuid.uuid4()
        folder = SimpleNamespace(project_id=project_id, deleted_at=None)
        serializer = PageSerializer(context={"project_id": str(project_id)})
        assert serializer.validate_folder(folder) is folder
        assert serializer.validate_folder(None) is None
        with pytest.raises(ValidationError):
            PageSerializer(context={"project_id": uuid.uuid4()}).validate_folder(folder)
        with pytest.raises(ValidationError):
            PageSerializer().validate_folder(folder)

    def test_deleted_folder_rejected(self):
        project_id = uuid.uuid4()
        folder = SimpleNamespace(project_id=project_id, deleted_at="2026-10-20")
        with pytest.raises(ValidationError):
            PageSerializer(context={"project_id": project_id}).validate_folder(folder)
