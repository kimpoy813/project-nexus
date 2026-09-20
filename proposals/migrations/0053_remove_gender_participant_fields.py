"""Remove the retired gender breakdown from participant profiling.

The Participants / Proposed Clients step now collects only sex
Disaggregation.  The gender breakdown fields belonged to the removed second
section and are no longer part of the proposal data model.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0052_remove_gender_issue_other"),
    ]

    operations = [
        migrations.RemoveField(model_name="proposal", name="g_lesbian"),
        migrations.RemoveField(model_name="proposal", name="g_gay"),
        migrations.RemoveField(model_name="proposal", name="g_bisexual"),
        migrations.RemoveField(model_name="proposal", name="g_transgender"),
        migrations.RemoveField(model_name="proposal", name="g_straight"),
        migrations.RemoveField(model_name="proposal", name="g_others"),
        migrations.RemoveField(model_name="participantsprofiling", name="gender_lesbian"),
        migrations.RemoveField(model_name="participantsprofiling", name="gender_gay"),
        migrations.RemoveField(model_name="participantsprofiling", name="gender_bisexual"),
        migrations.RemoveField(model_name="participantsprofiling", name="gender_transgender"),
        migrations.RemoveField(model_name="participantsprofiling", name="gender_straight_male"),
        migrations.RemoveField(model_name="participantsprofiling", name="gender_straight_female"),
        migrations.RemoveField(model_name="participantsprofiling", name="gender_others"),
        migrations.RemoveField(model_name="participantsprofiling", name="gender_others_specify"),
    ]
