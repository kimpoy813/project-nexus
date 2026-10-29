from django.http import FileResponse, Http404
from django.shortcuts import render

from .models import SitePage, resolve_section_data


def build_visible_blocks(page):
    """``(section, data)`` pairs for every visible section of ``page``.

    Data-driven blocks carry their resolved data; text blocks carry ``None``.
    Shared by the public pages so they all render from the same
    block partial with the same data lookups.
    """
    blocks = []
    for section in page.visible_sections:
        data = resolve_section_data(section) if section.is_data_layout else None
        blocks.append((section, data))
    return blocks


def details_page(request):
    page = SitePage.get_for(SitePage.Slug.HOME)
    context = {
        'page': page,
        'visible_blocks': build_visible_blocks(page),
    }

    return render(request, 'details/details_page.html', context)


def help_page(request):
    """The written help: how the workflow, documents, account rules, and FAQs work.

    Deliberately a template backed by live model choices and institutional
    contact details from Site Configuration — see ``details/system_profile.py``.
    """
    from . import system_profile

    return render(request, "details/help.html", system_profile.help_context())


def _render_content_page(
    request, slug, template="details/content_page.html", extra_context=None
):
    """Render a fully admin-managed public page.

    Unpublished pages stay reachable for admins (so they can preview drafts)
    but return 404 for everyone else.
    """
    page = SitePage.get_for(slug)

    if not page.is_published:
        profile = getattr(getattr(request, "user", None), "profile", None)
        role = (getattr(profile, "role", "") or "").upper()
        is_admin = role == "ADMIN" or getattr(request.user, "is_superuser", False)
        if not is_admin:
            raise Http404("This page is not available.")

    context = {
        "page": page,
        "sections": page.visible_sections,
        "visible_blocks": build_visible_blocks(page),
        "is_preview": not page.is_published,
    }
    if extra_context:
        context.update(extra_context)

    return render(request, template, context)


def programs_page(request):
    """Every published extension program, as a filterable directory."""
    return _render_content_page(request, SitePage.Slug.PROGRAMS)


def gallery_page(request):
    """Photographs of extension programs."""
    return _render_content_page(request, SitePage.Slug.GALLERY)


def about_page(request):
    """The Extension Office's story, system architecture, contacts, and mandate."""
    from . import system_profile

    return _render_content_page(
        request,
        SitePage.Slug.ABOUT,
        template="details/about.html",
        extra_context=system_profile.about_context(),
    )


def program_document(request, key):
    """Serve the document behind one Programs directory entry.

    A program's paper trail is already in the system — the signed proposal of
    an approved proposal, or the file attached to a legacy upload — so the
    directory links here instead of asking the office to re-upload it.

    ``key`` is an opaque entry id (see ``details.program_directory``), not a
    storage path, and only entries the directory publishes resolve at all: a
    draft's signed document 404s. Files are streamed through Django so the
    active storage backend (local media or Supabase) behaves the same.
    """
    from .program_directory import find_program_document

    resolved = find_program_document(key)
    if resolved is None:
        raise Http404("That document is not available.")

    field, filename, title = resolved
    try:
        handle = field.open("rb")
    except FileNotFoundError as error:
        raise Http404("That document is not available.") from error
    except Exception as error:  # storage outage must not become a 500
        raise Http404("That document is not available.") from error

    response = FileResponse(handle, as_attachment=False, filename=filename)
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
