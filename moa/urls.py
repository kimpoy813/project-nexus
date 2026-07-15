# -----------------------------------------------------------------------
# ADD THIS TO: your moa app's urls.py (e.g. moa/urls.py)
# Then include it in your project's root urls.py:
#   path("moa/", include("moa.urls")),
# -----------------------------------------------------------------------

from django.urls import path

from . import views

urlpatterns = [
    path("proposal/<int:proposal_id>/generate/", views.generate_moa_draft, name="generate_moa_draft"),
    path("proposal/<int:proposal_id>/upload/", views.upload_moa, name="upload_moa"),
    path("proposal/<int:proposal_id>/", views.moa_detail, name="moa_detail"),
    path("document/<int:moa_id>/review/", views.review_moa, name="review_moa"),
]
