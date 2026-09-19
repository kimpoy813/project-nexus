from django.db import migrations


RESEARCH_TYPES = ("RESEARCH_FACULTY", "RESEARCH_STUDENT")


def split_utility_model_step(apps, schema_editor):
    Step = apps.get_model("details", "ProposalWizardStepConfig")
    Proposal = apps.get_model("proposals", "Proposal")
    Comment = apps.get_model("proposals", "ProposalSectionComment")

    # Move from the end down to avoid the per-flow unique step constraint.
    for row in Step.objects.filter(flow="RESEARCH", step_no__gte=8).order_by("-step_no"):
        row.step_no += 1
        row.save(update_fields=["step_no"])

    Step.objects.update_or_create(
        flow="RESEARCH",
        step_no=8,
        defaults={
            "title": "Utility Model",
            "description": "",
            "instructions": "",
            "is_visible": True,
            "is_required": False,
        },
    )
    Step.objects.filter(flow="RESEARCH", step_no=7).update(description="")

    # Preserve progress and review comments for existing research proposals.
    for proposal in Proposal.objects.filter(extension_type__in=RESEARCH_TYPES).only(
        "id", "completed_steps", "skipped_steps"
    ):
        proposal.completed_steps = [n + 1 if n >= 8 else n for n in (proposal.completed_steps or [])]
        proposal.skipped_steps = [n + 1 if n >= 8 else n for n in (proposal.skipped_steps or [])]
        proposal.save(update_fields=["completed_steps", "skipped_steps"])

    for comment in Comment.objects.filter(
        proposal__extension_type__in=RESEARCH_TYPES, step_no__gte=8
    ):
        comment.step_no += 1
        comment.save(update_fields=["step_no"])


class Migration(migrations.Migration):
    dependencies = [
        ("details", "0024_agenda_checklist_retitles"),
        ("proposals", "0048_proposal_technology_title_and_more"),
    ]
    operations = [migrations.RunPython(split_utility_model_step, migrations.RunPython.noop)]
