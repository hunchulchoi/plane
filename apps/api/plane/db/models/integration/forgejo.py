# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import uuid

from django.db import models


class ForgejoRepository(models.Model):
    """One signed incoming webhook per project/repository mapping."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="forgejo_repositories")
    repository_url = models.URLField(max_length=500)
    secret = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "forgejo_repositories"
        ordering = ("created_at", "id")
        constraints = [models.UniqueConstraint(fields=("project", "repository_url"), name="forgejo_project_repository")]


class ForgejoDelivery(models.Model):
    repository = models.ForeignKey(ForgejoRepository, on_delete=models.CASCADE, related_name="deliveries")
    delivery_id = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "forgejo_deliveries"
        constraints = [
            models.UniqueConstraint(fields=("repository", "delivery_id"), name="forgejo_repository_delivery")
        ]
