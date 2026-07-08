# Generated manually to support the MOA Tracker / Implementation Tracker feature.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('proposals', '0036_remove_proposal_approved_docx_downloaded_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proposal',
            name='moa_status',
            field=models.CharField(
                choices=[
                    ('NOT_REQUIRED', 'Not Required'),
                    ('NOT_STARTED', 'Not Started'),
                    ('DRAFT', 'Drafting'),
                    ('LEGAL_REVIEW', 'Legal Review'),
                    ('FOR_REVISION', 'Under Revision'),
                    ('CERTIFICATION_READY', 'Certification Ready'),
                    ('AGENDA_AND_PRESENTATION', 'Agenda Brief & Presentation'),
                    ('COMPLETED', 'MOA Completed'),
                ],
                default='NOT_STARTED',
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='implementation_status',
            field=models.CharField(
                choices=[
                    ('NOT_STARTED', 'Not Started'),
                    ('PREPARATION', 'Preparation'),
                    ('IMPLEMENTATION', 'Implementation'),
                    ('MONITORING', 'Monitoring'),
                    ('POST_ACTIVITY_REPORT', 'Post Activity Report / Progress Report'),
                    ('TERMINAL_REPORT', 'Terminal Report'),
                    ('REVISION', 'Revision'),
                    ('COMPLETED', 'Completed'),
                ],
                default='NOT_STARTED',
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name='ProposalPhaseLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phase', models.CharField(choices=[('MOA', 'MOA'), ('IMPLEMENTATION', 'Implementation')], max_length=20)),
                ('from_status', models.CharField(blank=True, default='', max_length=40)),
                ('to_status', models.CharField(max_length=40)),
                ('remarks', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='proposal_phase_logs', to=settings.AUTH_USER_MODEL)),
                ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='phase_logs', to='proposals.proposal')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]