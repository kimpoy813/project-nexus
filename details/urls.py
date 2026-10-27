from django.urls import path
from django.views.generic import RedirectView

from .views import about_page, details_page, gallery_page, programs_page

urlpatterns = [
    path('', details_page, name='details_page'),
    path('programs/', programs_page, name='programs_page'),
    path('gallery/', gallery_page, name='gallery_page'),
    path('about/', about_page, name='about_page'),

    # The pages that used to sit here are now Programs and Gallery. Permanent
    # redirects keep old bookmarks, links, and shared URLs working.
    path(
        'reports/',
        RedirectView.as_view(pattern_name='programs_page', permanent=True),
        name='reports_page_legacy',
    ),
    path(
        'achievements/',
        RedirectView.as_view(pattern_name='gallery_page', permanent=True),
        name='achievements_page_legacy',
    ),
]
