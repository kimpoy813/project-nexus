"""
The Proponents section: saving the roster and the roles that follow from it.

The admin decides which fields a proponent row shows (see
``proposals.views.repeaters``); this module owns what happens to the proposal
when the step is saved: rows added by hand or picked from an account, removals,
the creator's automatic role, and the per-phase project leaders of a program.
"""

from django.contrib.auth import get_user_model

from ..models import ProposalProponent
from .repeaters import (
    proponent_repeater_form_for_step,
    save_repeater_rows,
)


User = get_user_model()


def _update_creator_role(proposal):
    creator_pp = proposal.proponents.filter(user=proposal.created_by).first()
    if not creator_pp:
        return

    if proposal.scope_type == "PROGRAM":
        creator_pp.role = "Program Leader"
    elif proposal.scope_type == "PROJECT":
        creator_pp.role = "Project Leader"
    else:
        creator_pp.role = "Proponent"

    creator_pp.save(update_fields=["role"])



def save_step_three_proponents(proposal, request, step=None):
    """Persist the Proponents section and return the required problems left.

    ``step`` is the wizard step the section currently sits on (the admin can
    move it); it defaults to wherever the proponents section is configured.
    The step's repeatable proponent group (when the admin built one) owns the
    rows; otherwise the built-in ``p_<id>_...`` roster fields are saved, so a
    wizard whose repeatable group was turned off keeps working.
    """
    if step is None:
        from .sections import proponents_step_no
        step = proponents_step_no()

    explicit_role_ids = set()
    missing = []
    repeater_form = proponent_repeater_form_for_step(step) if step else None

    if repeater_form is not None:
        repeater_problems, meta = save_repeater_rows(proposal, repeater_form, request, request.user)
        missing.extend(repeater_problems)
        explicit_role_ids = meta.get("explicit_role_ids", set())

    remove_ids = request.POST.getlist("remove_proponent_ids")
    if remove_ids:
        ProposalProponent.objects.filter(
            proposal=proposal,
            id__in=remove_ids,
        ).exclude(user=proposal.created_by).delete()

    add_user_id = (request.POST.get("add_user_id") or "").strip()
    if add_user_id.isdigit():
        user_obj = User.objects.filter(id=int(add_user_id)).first()
        if user_obj:
            prof = getattr(user_obj, "profile", None)
            ProposalProponent.objects.get_or_create(
                proposal=proposal,
                user=user_obj,
                defaults={
                    "full_name": getattr(prof, "full_name", user_obj.username),
                    "email": user_obj.email or "",
                    "role": "Proponent",
                    "designation": "",
                    "specialization": "",
                    "cp_number": "",
                },
            )

    if repeater_form is None:
        for proponent in proposal.proponents.all():
            prefix = f"p_{proponent.id}_"
            proponent.designation = request.POST.get(prefix + "designation", proponent.designation)
            proponent.specialization = request.POST.get(prefix + "specialization", proponent.specialization)
            proponent.cp_number = request.POST.get(prefix + "cp_number", proponent.cp_number)
            proponent.email = request.POST.get(prefix + "email", proponent.email)
            proponent.save(update_fields=["designation", "specialization", "cp_number", "email"])

    _update_creator_role(proposal)

    if proposal.scope_type == "PROGRAM":
        # Roles typed into the repeater's Role field survive the automatic
        # reset; the creator's own role and the per-phase leaders still win.
        proposal.proponents.exclude(user=proposal.created_by).exclude(
            id__in=explicit_role_ids
        ).update(role="Proponent")

        for prj in proposal.program_projects.all():
            uid = (request.POST.get(f"project_leader_{prj.id}") or "").strip()
            if uid.isdigit():
                prj.leader_user_id = int(uid)
                prj.save(update_fields=["leader_user"])

                proponent = proposal.proponents.filter(user_id=int(uid)).first()
                if proponent and proponent.user_id != proposal.created_by_id:
                    proponent.role = "Project Leader"
                    proponent.save(update_fields=["role"])
            else:
                prj.leader_user = None
                prj.save(update_fields=["leader_user"])

    return missing

