from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("research", "0009_sourcelicense_is_current_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="sourcelicense",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_current=True),
                fields=("source",),
                name="one_current_license_per_source",
            ),
        ),
    ]
