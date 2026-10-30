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


PROGRAMS_SUBNAV_ITEMS = (
    {"anchor": "program-summary", "label": "Summary"},
    {"anchor": "program-overview", "label": "Overview"},
    {"anchor": "program-rankings", "label": "Rankings"},
    {"anchor": "program-filters", "label": "Filters"},
    {"anchor": "program-directory", "label": "Directory"},
)

GALLERY_SUBNAV_ITEMS = (
    {"anchor": "gallery-summary", "label": "Summary"},
    {"anchor": "gallery-overview", "label": "Overview"},
    {"anchor": "gallery-filters", "label": "Filters"},
    {"anchor": "gallery-photos", "label": "Photos"},
)

#: Concise, Programs-style jump labels for seeded section headings. When an
#: admin renames a section heading in the Page Editor, their custom heading is
#: preserved instead.
DEFAULT_SUBNAV_LABELS = {
    ("THRUST", "extension thrust"): "Thrusts",
    ("THRUST", "extension thrusts"): "Thrusts",
    ("PROCESSES", "extension processes"): "Processes",
    ("PROCESSES", "current process flow"): "Processes",
    ("TARGETS", "extension targets"): "Targets",
    ("PERSONNEL", "extension personnel"): "Personnel",
    ("SDG", "sustainable development goals"): "SDGs",
    ("ACTIVITIES", "extension activities"): "Activities",
    ("TEMPLATES", "official templates"): "Templates",
    ("TEMPLATES", "template library"): "Templates",
    ("CAMPUSES", "campuses we serve"): "Campuses",
    ("SYSTEM_PROFILE", "system profile"): "Profile",
}


def _concise_subnav_label(section):
    heading = (section.heading or "").strip()
    if not heading:
        return ""
    key = (section.layout or "", heading.casefold())
    return DEFAULT_SUBNAV_LABELS.get(key, heading)


def build_subnav_items(visible_blocks):
    """``{"anchor": ..., "label": ...}`` dicts for visible page subsections.

    Multi-part directory/gallery blocks expand into their structured in-page
    subsections (Summary, Overview, Filters, …), while standard blocks use
    concise jump labels unless an admin customized the section heading.
    """
    items = []
    for section, _data in visible_blocks:
        if section.layout == "PROGRAMS":
            items.extend(dict(item) for item in PROGRAMS_SUBNAV_ITEMS)
        elif section.layout == "GALLERY":
            items.extend(dict(item) for item in GALLERY_SUBNAV_ITEMS)
        elif section.anchor and section.heading:
            items.append(
                {
                    "anchor": section.anchor,
                    "label": _concise_subnav_label(section),
                }
            )
    return items


def details_page(request):
    page = SitePage.get_for(SitePage.Slug.HOME)
    visible_blocks = build_visible_blocks(page)
    anchored = build_subnav_items(visible_blocks)
    context = {
        'page': page,
        'visible_blocks': visible_blocks,
        'subnav_items': anchored if len(anchored) > 1 else [],
        'subnav_aria_label': 'Home sections',
    }

    return render(request, 'details/details_page.html', context)


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

    visible_blocks = build_visible_blocks(page)
    anchored = build_subnav_items(visible_blocks)
    subnav_items = anchored if len(anchored) > 1 else []

    context = {
        "page": page,
        "sections": page.visible_sections,
        "visible_blocks": visible_blocks,
        "subnav_items": subnav_items,
        "subnav_aria_label": f"{page.title} sections",
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


def program_document(request, key):
    """Serve the document behind one Programs directory entry.

    A program's paper trail is already in the system — the signed proposal of
    an approved proposal, or the file attached to a legacy upload — so the
    directory links here instead of asking the office to re-upload it.

    ``key`` is an opaque entry id (see ``details.program_directory``), not a
    storage path, and only entries the directory publishes at all resolve: a
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
