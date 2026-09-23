"""
Remove the Office Forms block.

The Form Builder was dropped from the system, so the ``FORMS`` content source
no longer exists. Any page section still using that layout (including the one
seeded on the Services page by migration 0035) would render nothing, so the
rows are deleted before the layout choice disappears.
"""

from django.db import migrations, models


def remove_forms_sections(apps, schema_editor):
    PageSection = apps.get_model("details", "PageSection")
    PageSection.objects.filter(layout="FORMS").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('details', '0035_compose_pages_from_blocks'),
    ]

    operations = [
        migrations.RunPython(remove_forms_sections, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='pagesection',
            name='layout',
            field=models.CharField(choices=[('RICH_TEXT', 'Rich text'), ('CARD', 'Card'), ('CALLOUT', 'Callout / highlight'), ('CTA', 'Call to action'), ('THRUST', 'Extension Thrust cards'), ('PROCESSES', 'Extension Processes'), ('TARGETS', 'Extension Targets'), ('PERSONNEL', 'Extension Personnel'), ('SDG', 'Sustainable Development Goals'), ('ACTIVITIES', 'Extension Activities'), ('TEMPLATES', 'Template Library')], default='RICH_TEXT', max_length=20),
        ),
    ]
