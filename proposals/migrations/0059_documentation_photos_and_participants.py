# Documentation photos, and the participant counts the terminal report asks for.
#
# ``TerminalReportPhoto`` becomes ``DocumentationPhoto``: the photos belong to
# the activity, not to one report, so the same table holds the photos a
# proponent files with the terminal report (appendix E.13, "photo documentation
# in action with caption") and the photos the office attaches when importing a
# legacy activity. Renaming keeps every row — and every image already on disk.
#
# The proposal also records its student, faculty, and research-staff
# participants, which is the matrix the terminal report requires and the split
# the Programs directory publishes.

import django.db.models.deletion
import proposals.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0058_terminalreportphoto"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(
            old_name="TerminalReportPhoto",
            new_name="DocumentationPhoto",
        ),
        migrations.AlterModelOptions(
            name="documentationphoto",
            options={
                "ordering": ["order", "id"],
                "verbose_name": "Documentation Photo",
            },
        ),
        migrations.AlterField(
            model_name="documentationphoto",
            name="image",
            field=models.ImageField(
                help_text="Photo of the activity, as submitted with the terminal report.",
                upload_to=proposals.models.documentation_photo_path,
            ),
        ),
        migrations.AlterField(
            model_name="documentationphoto",
            name="caption",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "What the photo shows, e.g. “Participants practising compost "
                    "preparation.” Required by the terminal report (appendix E.13)."
                ),
                max_length=200,
            ),
        ),
        migrations.AlterField(
            model_name="documentationphoto",
            name="uploaded_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="uploaded_documentation_photos",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="proposal",
            name="faculty_participants",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="ISPSC faculty involved.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="proposal",
            name="research_staff_participants",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="RDE / research staff involved.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="proposal",
            name="student_participants",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="ISPSC students involved, when the activity involved students.",
                null=True,
            ),
        ),
    ]
