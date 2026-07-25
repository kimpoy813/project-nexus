# Generated to restore Evaluator as a first-class account role on 2026-07-25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_siteconfiguration_siteconfigurationlog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="role",
            field=models.CharField(
                choices=[
                    ("FACULTY", "Faculty"),
                    ("STAFF", "Staff"),
                    ("EVALUATOR", "Evaluator"),
                    ("DEPARTMENT_COORDINATOR", "Department Coordinator"),
                    ("CAMPUS_COORDINATOR", "Campus Coordinator"),
                    ("DIRECTOR", "Director"),
                    ("ADMIN", "Admin"),
                ],
                default="FACULTY",
                max_length=50,
            ),
        ),
    ]
