from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0128_forgejo")]

    operations = [
        migrations.AddField(
            model_name="page",
            name="description_binary_outdated",
            field=models.BooleanField(default=False),
        ),
    ]
