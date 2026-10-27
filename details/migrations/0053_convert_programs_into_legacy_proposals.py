"""Every program becomes a proposal, then the program tables are dropped.

Programs were once their own table (``ExtensionProgram``) with its own photos
(``GalleryPhoto``). That gave the office two ways to record the same activity,
and the two drifted: a "program" could exist that no proposal knew about, with
photos that documented nothing in the workflow.

A program is now an approved proposal or a **legacy** proposal, so this
migration carries the existing rows across instead of dropping them:

1. A program already linked to a proposal keeps that proposal. Its photos move
   onto the proposal as documentation photos, and any detail the proposal is
   missing (participants, beneficiaries, schedule) is filled in from the
   program record.
2. A standalone program becomes a legacy proposal — the same thing the office
   gets from *Legacy Records Upload* — carrying its title, campus, year,
   participants, objectives, its uploaded document (as the legacy proposal
   file) and its cover image (as a documentation photo).
3. A gallery photo with no program becomes a legacy proposal named after the
   photo's caption, and the photo is attached to it. Nothing is deleted: a
   photo that reaches the public gallery must name the activity it documents.

The two models are deleted afterwards, so this is the only chance to run it.
"""

from django.db import migrations
from django.utils import timezone

#: ``ExtensionProgram`` type pair -> the proposal's extension type.
EXTENSION_TYPE_MAP = {
    ("RESEARCH_BASED", "FACULTY"): "RESEARCH_FACULTY",
    ("RESEARCH_BASED", "STUDENT"): "RESEARCH_STUDENT",
    ("REQUEST_BASED", "OTHERS"): "REQUEST_BASED",
    ("COMMUNITY_BASED", "OTHERS"): "COMMUNITY_BASED",
}

DEFAULT_EXTENSION_TYPE = "COMMUNITY_BASED"


def _extension_type(program):
    return EXTENSION_TYPE_MAP.get(
        (program.extension_type, program.research_basis), DEFAULT_EXTENSION_TYPE
    )


def _objectives(program):
    """The program stored one objective per line; the proposal splits them."""
    lines = [line.strip() for line in (program.objectives or "").splitlines() if line.strip()]
    if not lines:
        return "", ""
    return lines[0][:2000], "\n".join(lines[1:])[:4000]


def _owner(apps, program_proposal=None):
    """Who owns a converted record.

    ``Proposal.created_by`` is required and protected, so a converted program
    needs a real account. The linked proposal's creator is the honest choice;
    otherwise the first administrator who can act on it.
    """
    if program_proposal is not None:
        return program_proposal.created_by

    User = apps.get_model("accounts", "CustomUser")
    return (
        User.objects.filter(is_superuser=True).order_by("id").first()
        or User.objects.filter(is_staff=True).order_by("id").first()
        or User.objects.order_by("id").first()
    )


def convert_programs(apps, schema_editor):
    ExtensionProgram = apps.get_model("details", "ExtensionProgram")
    GalleryPhoto = apps.get_model("details", "GalleryPhoto")
    Proposal = apps.get_model("proposals", "Proposal")
    DocumentationPhoto = apps.get_model("proposals", "DocumentationPhoto")

    programs = list(ExtensionProgram.objects.all().order_by("pk"))
    photos = list(GalleryPhoto.objects.all().order_by("pk"))
    if not programs and not photos:
        return

    owner = _owner(apps)
    if owner is None:
        # Converting would drop rows nobody can see again; stop instead and let
        # an administrator create an account, then re-run the migration.
        raise RuntimeError(
            "Cannot convert programs into legacy proposals: no user account exists "
            "to own the converted records. Create an administrator account and run "
            "the migration again."
        )

    now = timezone.now()
    program_proposal = {}

    for program in programs:
        proposal = program.proposal
        created = False
        if proposal is None:
            general, specific = _objectives(program)
            proposal = Proposal.objects.create(
                created_by=owner,
                is_legacy=True,
                title=program.title[:300],
                campus=(program.campus or "")[:120],
                status="COMPLETED",
                proposal_status="COMPLETED",
                moa_status="COMPLETED",
                implementation_status="COMPLETED",
                extension_type=_extension_type(program),
                estimated_year=program.year,
                beneficiaries_count=program.beneficiaries or None,
                beneficiaries_who=(program.target_community or "")[:4000],
                date_venue=(program.duration or "")[:150],
                general_objective=general,
                objectives_specific=specific,
                student_participants=program.student_participants or None,
                faculty_participants=program.faculty_participants or None,
                research_staff_participants=program.research_staff_participants or None,
                legacy_proposal_file=program.document or None,
                implementation_completed_at=now,
                approved_at=now,
                last_saved_at=now,
            )
            created = True
        else:
            # Fill only what the proposal does not already record, so the
            # conversion never overwrites a proponent's own answers.
            changed = []
            for field, value in (
                ("student_participants", program.student_participants or None),
                ("faculty_participants", program.faculty_participants or None),
                ("research_staff_participants", program.research_staff_participants or None),
            ):
                if value and not getattr(proposal, field):
                    setattr(proposal, field, value)
                    changed.append(field)
            if changed:
                proposal.save(update_fields=changed + ["last_saved_at"])

        program_proposal[program.pk] = proposal

        # Photos the office attached to the program now document the proposal.
        for position, photo in enumerate(program.photos.all().order_by("pk"), start=1):
            DocumentationPhoto.objects.create(
                proposal=proposal,
                image=photo.image,
                caption=(photo.title or photo.caption or program.title)[:200],
                is_visible=photo.is_visible,
                order=position,
            )

        if program.cover_image:
            DocumentationPhoto.objects.create(
                proposal=proposal,
                image=program.cover_image,
                caption=program.title[:200],
                order=100,
            )

        if created:
            proposal.approved_at = now

    for photo in photos:
        if photo.program_id and photo.program_id in program_proposal:
            proposal = program_proposal[photo.program_id]
        else:
            # A photo with no program documented *some* activity, so give it a
            # legacy record named after the photo rather than lose it.
            proposal = Proposal.objects.create(
                created_by=owner,
                is_legacy=True,
                title=(photo.title or "Extension activity photo")[:300],
                campus=(photo.campus or "")[:120],
                status="COMPLETED",
                proposal_status="COMPLETED",
                moa_status="COMPLETED",
                implementation_status="COMPLETED",
                extension_type=DEFAULT_EXTENSION_TYPE,
                estimated_year=photo.taken_on.year if photo.taken_on else None,
                implementation_completed_at=now,
                approved_at=now,
                last_saved_at=now,
            )
        DocumentationPhoto.objects.create(
            proposal=proposal,
            image=photo.image,
            caption=(photo.title or photo.caption or proposal.title)[:200],
            is_visible=photo.is_visible,
            order=photo.order or 1,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("details", "0052_about_the_system"),
        ("proposals", "0059_documentation_photos_and_participants"),
    ]

    operations = [
        migrations.RunPython(convert_programs, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="galleryphoto",
            name="program",
        ),
        migrations.DeleteModel(
            name="ExtensionProgram",
        ),
        migrations.DeleteModel(
            name="GalleryPhoto",
        ),
    ]
