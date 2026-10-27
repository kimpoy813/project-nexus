from django.http import Http404
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


def _render_content_page(request, slug, template="details/content_page.html"):
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

    return render(
        request,
        template,
        {
            "page": page,
            "sections": page.visible_sections,
            "visible_blocks": build_visible_blocks(page),
            "is_preview": not page.is_published,
        },
    )


def programs_page(request):
    """Every published extension program, as a filterable directory."""
    return _render_content_page(request, SitePage.Slug.PROGRAMS)


def gallery_page(request):
    """Photographs of extension programs."""
    return _render_content_page(request, SitePage.Slug.GALLERY)


def about_page(request):
    """The Extension Office's story, contacts, and mandate."""
    return _render_content_page(request, SitePage.Slug.ABOUT)
