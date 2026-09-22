"""
Make every no-code builder a draggable content source.

Two things change:

1. The 17 Sustainable Development Goals become rows. They were hardcoded in
   the block template, which is why the SDG section had "data" that no admin
   screen could edit and no query could find. The seeded titles are the same
   strings the template printed, so the public page is unchanged until
   somebody edits a goal.

2. ``FORMS`` joins the layout choices, so the Form Builder's output can be
   dropped onto a page like every other source.
"""

from django.db import migrations, models


#: The goals exactly as the old block template printed them. Codes match
#: ``proposals.views.constants.SDG_LIST`` and ``ProposalSDG.sdg_code``, so a
#: proposal's stored SDG links keep resolving to the same goal.
SDG_SEED = [
    ("01", "No Poverty"),
    ("02", "Zero Hunger"),
    ("03", "Good Health and Well-being"),
    ("04", "Quality Education"),
    ("05", "Gender Equality"),
    ("06", "Clean Water and Sanitation"),
    ("07", "Affordable and Clean Energy"),
    ("08", "Decent Work and Economic Growth"),
    ("09", "Industry, Innovation and Infrastructure"),
    ("10", "Reduced Inequalities"),
    ("11", "Sustainable Cities and Communities"),
    ("12", "Responsible Consumption and Production"),
    ("13", "Climate Action"),
    ("14", "Life Below Water"),
    ("15", "Life on Land"),
    ("16", "Peace, Justice and Strong Institutions"),
    ("17", "Partnerships for the Goals"),
]


def seed_sdgs(apps, schema_editor):
    Goal = apps.get_model("details", "SustainableDevelopmentGoal")
    if Goal.objects.exists():
        return
    Goal.objects.bulk_create([
        Goal(code=code, title=title, order=index, is_visible=True)
        for index, (code, title) in enumerate(SDG_SEED, start=1)
    ])


def unseed_sdgs(apps, schema_editor):
    apps.get_model("details", "SustainableDevelopmentGoal").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('details', '0033_home_sections_consolidation'),
    ]

    operations = [
        migrations.CreateModel(
            name='SustainableDevelopmentGoal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(help_text='Goal number, e.g. "01". Matches the code stored on proposals.', max_length=10, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('summary', models.CharField(blank=True, default='', help_text='Optional line shown under the goal title.', max_length=255)),
                ('image', models.ImageField(blank=True, help_text='Custom artwork. Leave empty to use the official UN icon.', null=True, upload_to='sdg/')),
                ('is_visible', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=1)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Sustainable Development Goal',
                'ordering': ['order', 'code'],
            },
        ),
        migrations.AlterField(
            model_name='pagesection',
            name='layout',
            field=models.CharField(choices=[('RICH_TEXT', 'Rich text'), ('CARD', 'Card'), ('CALLOUT', 'Callout / highlight'), ('CTA', 'Call to action'), ('THRUST', 'Extension Thrust cards'), ('PROCESSES', 'Extension Processes'), ('TARGETS', 'Extension Targets'), ('PERSONNEL', 'Extension Personnel'), ('SDG', 'Sustainable Development Goals'), ('ACTIVITIES', 'Extension Activities'), ('TEMPLATES', 'Template Library'), ('FORMS', 'Office Forms')], default='RICH_TEXT', max_length=20),
        ),
        migrations.RunPython(seed_sdgs, unseed_sdgs),
    ]
