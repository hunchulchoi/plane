import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0127_passkey")]

    operations = [
        migrations.CreateModel(
            name="ForgejoRepository",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("repository_url", models.URLField(max_length=500)),
                ("secret", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_received_at", models.DateTimeField(blank=True, null=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forgejo_repositories",
                        to="db.project",
                    ),
                ),
            ],
            options={
                "db_table": "forgejo_repositories",
                "ordering": ("created_at", "id"),
                "constraints": [
                    models.UniqueConstraint(fields=("project", "repository_url"), name="forgejo_project_repository")
                ],
            },
        ),
        migrations.CreateModel(
            name="ForgejoDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("delivery_id", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "repository",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="db.forgejorepository",
                    ),
                ),
            ],
            options={
                "db_table": "forgejo_deliveries",
                "constraints": [
                    models.UniqueConstraint(fields=("repository", "delivery_id"), name="forgejo_repository_delivery")
                ],
            },
        ),
    ]
