# Generated for admin site-wide controls on 2026-07-25

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_alter_signatory_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_name", models.CharField(default="NExUS", max_length=120)),
                ("short_name", models.CharField(default="NExUS", max_length=40)),
                ("tagline", models.CharField(default="Networked Extension Unified System", max_length=220)),
                ("contact_email", models.EmailField(blank=True, default="ispsc.nexus@gmail.com", max_length=254)),
                ("facebook_url", models.URLField(blank=True, default="https://facebook.com")),
                ("primary_color", models.CharField(default="#a16207", max_length=7)),
                ("secondary_color", models.CharField(default="#5a1113", max_length=7)),
                ("accent_color", models.CharField(default="#f5e587", max_length=7)),
                ("announcement_enabled", models.BooleanField(default=False)),
                ("announcement_title", models.CharField(blank=True, default="", max_length=120)),
                ("announcement_message", models.TextField(blank=True, default="")),
                ("announcement_tone", models.CharField(choices=[("INFO", "Info"), ("SUCCESS", "Success"), ("WARNING", "Warning"), ("DANGER", "Critical")], default="INFO", max_length=20)),
                ("registration_enabled", models.BooleanField(default=True)),
                ("maintenance_mode", models.BooleanField(default=False)),
                ("maintenance_message", models.TextField(blank=True, default="NExUS is temporarily under maintenance. Please check back soon.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="site_configuration_updates", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Site Configuration",
            },
        ),
        migrations.CreateModel(
            name="SiteConfigurationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("summary", models.CharField(max_length=255)),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="site_configuration_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Site Configuration Log",
                "ordering": ["-created_at"],
            },
        ),
    ]
