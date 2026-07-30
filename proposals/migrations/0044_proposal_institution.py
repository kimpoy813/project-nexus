# Generated manually for institution-scoped proposals.

from django.db import migrations, models
import django.db.models.deletion


def assign_proposal_institutions(apps, schema_editor):
    Institution = apps.get_model("accounts", "Institution")
    Proposal = apps.get_model("proposals", "Proposal")
    Profile = apps.get_model("accounts", "Profile")
    default_institution = Institution.objects.filter(slug="ispsc").first()

    profiles = {
        profile.user_id: profile.institution_id
        for profile in Profile.objects.exclude(institution__isnull=True)
    }

    for proposal in Proposal.objects.filter(institution__isnull=True).only("id", "created_by_id", "institution"):
        institution_id = profiles.get(proposal.created_by_id) or (default_institution.id if default_institution else None)
        if institution_id:
            proposal.institution_id = institution_id
            proposal.save(update_fields=["institution"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_institution_multitenancy"),
        ("proposals", "0043_alter_proposal_implementation_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposal",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="proposals", to="accounts.institution"),
        ),
        migrations.RunPython(assign_proposal_institutions, noop_reverse),
    ]
