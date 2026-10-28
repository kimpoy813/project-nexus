from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0059_documentation_photos_and_participants"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposal",
            name="complete_research_file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="proposal_files/complete_research/",
            ),
        ),
    ]
