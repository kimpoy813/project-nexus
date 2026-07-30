# Generated manually for institution-scoped content and builders.

from django.db import migrations, models
import django.db.models.deletion


def assign_default_institution(apps, schema_editor):
    Institution = apps.get_model("accounts", "Institution")
    default_institution = Institution.objects.filter(slug="ispsc").first()
    if default_institution is None:
        return

    for model_name in [
        "AccomplishmentReport",
        "Activity",
        "DocumentTemplate",
        "DynamicFormTemplate",
        "ExtensionProcess",
        "HomeSectionHeading",
        "HomeThrust",
        "Personnel",
        "ProposalWizardStepConfig",
        "RoleCapability",
        "SitePage",
        "Target",
        "WorkflowPhase",
    ]:
        Model = apps.get_model("details", model_name)
        Model.objects.filter(institution__isnull=True).update(institution=default_institution)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_institution_multitenancy"),
        ("details", "0012_services_hero_copy"),
    ]

    operations = [
        migrations.AddField(
            model_name="accomplishmentreport",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="accomplishment_reports", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="activity",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="documenttemplate",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="document_templates", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="dynamicformtemplate",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="dynamic_form_templates", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="extensionprocess",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="extension_processes", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="homesectionheading",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="home_section_headings", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="homethrust",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="home_thrusts", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="personnel",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="personnel", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="proposalwizardstepconfig",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="proposal_wizard_steps", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="rolecapability",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="role_capabilities", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="sitepage",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="site_pages", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="target",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="targets", to="accounts.institution"),
        ),
        migrations.AddField(
            model_name="workflowphase",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="workflow_phases", to="accounts.institution"),
        ),
        migrations.AlterField(
            model_name="dynamicformtemplate",
            name="slug",
            field=models.SlugField(max_length=200),
        ),
        migrations.AlterField(
            model_name="homesectionheading",
            name="section",
            field=models.SlugField(choices=[("thrust", "Extension Thrust"), ("process", "Extension Processes"), ("targets", "Extension Targets"), ("personnel", "Extension Personnel"), ("sdg", "Sustainable Development Goals"), ("activities", "Extension Activities")], max_length=40),
        ),
        migrations.AlterField(
            model_name="proposalwizardstepconfig",
            name="step_no",
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AlterField(
            model_name="sitepage",
            name="slug",
            field=models.SlugField(choices=[("home", "Home"), ("services", "Services"), ("reports", "Reports"), ("achievements", "Achievements")], max_length=40),
        ),
        migrations.AlterField(
            model_name="workflowphase",
            name="key",
            field=models.SlugField(choices=[("proposal", "Proposal"), ("moa", "MOA"), ("implementation", "Implementation")], help_text="Identifies which set of model statuses this phase displays.", max_length=30),
        ),
        migrations.AlterUniqueTogether(
            name="target",
            unique_together={("institution", "year", "campus", "metric")},
        ),
        migrations.RemoveConstraint(
            model_name="rolecapability",
            name="unique_role_capability",
        ),
        migrations.RunPython(assign_default_institution, noop_reverse),
        migrations.AddConstraint(
            model_name="dynamicformtemplate",
            constraint=models.UniqueConstraint(fields=("institution", "slug"), name="unique_dynamic_form_slug_per_institution"),
        ),
        migrations.AddConstraint(
            model_name="homesectionheading",
            constraint=models.UniqueConstraint(fields=("institution", "section"), name="unique_home_heading_per_institution"),
        ),
        migrations.AddConstraint(
            model_name="proposalwizardstepconfig",
            constraint=models.UniqueConstraint(fields=("institution", "step_no"), name="unique_wizard_step_per_institution"),
        ),
        migrations.AddConstraint(
            model_name="rolecapability",
            constraint=models.UniqueConstraint(fields=("institution", "role", "capability"), name="unique_role_capability_per_institution"),
        ),
        migrations.AddConstraint(
            model_name="sitepage",
            constraint=models.UniqueConstraint(fields=("institution", "slug"), name="unique_site_page_per_institution"),
        ),
        migrations.AddConstraint(
            model_name="workflowphase",
            constraint=models.UniqueConstraint(fields=("institution", "key"), name="unique_workflow_phase_per_institution"),
        ),
    ]
