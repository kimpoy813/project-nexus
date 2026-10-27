"""The two POST endpoints behind the undo bar.

Kept in their own module because they are the only views in this app that act
on something the request does not name: the token is an opaque handle into the
caller's own session, so an undo URL can be shared, cached or guessed without
revealing anything or letting one person restore another's deletion.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .. import deletion


def _back(request):
    """Where to go after the undo: the page it was pressed on, or the dashboard."""
    target = request.POST.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        url=target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(target)
    return redirect("dashboard_redirect")


@login_required
@require_POST
def undo_delete(request, token):
    """Put a deleted record back, if it is still this session's to undo."""
    result = deletion.restore(request, token)

    if result is None:
        # Expired, already undone, or never this user's: all the same to the
        # user, and none of them is an error worth a red screen.
        messages.warning(request, "That deletion can no longer be undone.")
        return _back(request)

    label, rows = result
    noun = "record" if rows == 1 else "records"
    messages.success(request, f'Restored {label} ({rows} {noun}).')
    return _back(request)


@login_required
@require_POST
def dismiss_undo(request, token):
    """Drop one pending undo — the user has read it and does not want it."""
    if not deletion.dismiss(request, token):
        raise Http404("Nothing to dismiss.")
    return _back(request)
