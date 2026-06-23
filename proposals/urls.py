from django.urls import path
from . import views

urlpatterns = [
    # Services home / proposal creation
    path("proposals/", views.services_home, name="services_home"),
    path("proposals/new/", views.proposal_create, name="proposal_create"),

    # Proposal wizard flow
    path(
        "proposals/<uuid:proposal_id>/edit/step/<int:step>/",
        views.proposal_wizard,
        name="proposal_wizard",
    ),
    path(
        "proposals/<uuid:proposal_id>/share/",
        views.proposal_share,
        name="proposal_share",
    ),
    path(
        "proposals/<uuid:proposal_id>/submit/",
        views.proposal_submit,
        name="proposal_submit",
    ),

    # Wizard helper endpoints
    path(
        "proposals/title-suggest/",
        views.title_suggest,
        name="title_suggest",
    ),
    path(
        "proposals/proponent-search/",
        views.proponent_search,
        name="proponent_search",
    ),
    path(
        "proposals/<uuid:proposal_id>/editor-ping/",
        views.proposal_editor_ping,
        name="proposal_editor_ping",
    ),

    # Review / summary flow
    path(
        "proposals/<uuid:proposal_id>/review/step/<int:step>/",
        views.proposal_review_comments,
        name="proposal_review_comments",
    ),
    path(
        "proposals/<uuid:proposal_id>/comments-summary/",
        views.proposal_comment_summary,
        name="proposal_comment_summary",
    ),
    path(
        "proposals/<uuid:proposal_id>/version/<int:round_no>/view/",
        views.proposal_version_summary,
        name="proposal_version_summary",
    ),
    path(
        "proposals/<uuid:proposal_id>/return-for-revision/",
        views.proposal_return_for_revision,
        name="proposal_return_for_revision",
    ),
    path(
        "proposals/<uuid:proposal_id>/approve/",
        views.proposal_approve,
        name="proposal_approve",
    ),

    # Review actions
    path(
        "proposals/<uuid:proposal_id>/assign-evaluator/",
        views.proposal_assign_evaluator,
        name="proposal_assign_evaluator",
    ),
    path(
        "proposals/<uuid:proposal_id>/assign-evaluator/<int:evaluator_id>/",
        views.proposal_assign_evaluator,
        name="proposal_assign_evaluator_ajax",
    ),
    path(
        "proposals/<uuid:proposal_id>/remove-evaluator/<int:evaluator_id>/",
        views.proposal_remove_evaluator,
        name="proposal_remove_evaluator",
    ),
    path(
        "proposals/<uuid:proposal_id>/complete-evaluation/",
        views.proposal_complete_evaluation,
        name="proposal_complete_evaluation",
    ),
    path(
        "proposals/<uuid:proposal_id>/mark-ready-for-summary/",
        views.proposal_mark_ready_for_summary,
        name="proposal_mark_ready_for_summary",
    ),
    path(
        "proposals/<uuid:proposal_id>/department-review-done/",
        views.proposal_mark_department_review_done,
        name="proposal_mark_department_review_done",
    ),
    path(
        "proposals/<uuid:proposal_id>/campus-review-done/",
        views.proposal_mark_campus_review_done,
        name="proposal_mark_campus_review_done",
    ),

    # Downloadable templates
    path(
        "proposals/<uuid:proposal_id>/download/work-plan-template/",
        views.download_work_plan_template,
        name="download_work_plan_template",
    ),
    path(
        "proposals/<uuid:proposal_id>/download/gantt-chart-template/",
        views.download_gantt_chart_template,
        name="download_gantt_chart_template",
    ),
    path(
        "proposals/<uuid:proposal_id>/download/funding-template/",
        views.download_funding_template,
        name="download_funding_template",
    ),

    # File preview
    path(
        "proposals/<uuid:proposal_id>/preview/<str:file_type>/",
        views.proposal_file_preview,
        name="proposal_file_preview",
    ),
    path(
        "proposals/<uuid:proposal_id>/preview/<str:file_type>/<int:attachment_id>/",
        views.proposal_file_preview,
        name="proposal_attachment_preview",
    ),
    path('proposal/<uuid:proposal_id>/comment-summary/', views.proposal_comment_summary, name='proposal_comment_summary'),
    path('proposal/<uuid:proposal_id>/send-summary/', views.proposal_send_summary, name='proposal_send_summary'),
    path('proposal/<uuid:proposal_id>/print-summary/', views.proposal_print_summary, name='proposal_print_summary'),
    path('proposal/<uuid:proposal_id>/view-summary/', views.proposal_view_summary, name='proposal_view_summary'),
    path("<uuid:proposal_id>/staff/summary/preview/", views.staff_comment_summary_preview, name="staff_comment_summary_preview"),
    path("<uuid:proposal_id>/staff/summary/docx/", views.staff_comment_summary_docx, name="staff_comment_summary_docx"),
    
    path("proposals/<uuid:proposal_id>/download-proposal/",
         views.proposal_download_approved_docx,
         name="proposal_download_approved_docx"),
    path("proposals/<uuid:proposal_id>/download-approval/<str:document_type>/",
         views.proposal_download_approval_document,
         name="proposal_download_approval_document"),

    path("proposals/<uuid:proposal_id>/upload-signed/",
         views.proposal_upload_signed_proposal,
         name="proposal_upload_signed_proposal"),

    path("proposals/<uuid:proposal_id>/release-docs/",
         views.staff_release_approval_documents,
         name="staff_release_approval_documents"),
    path("proposals/<uuid:proposal_id>/claim/",
        views.proposal_mark_claimed,
        name="proposal_mark_claimed"),
    path("proposals/<uuid:proposal_id>/storage/",
        views.proposal_storage,
        name="proposal_storage"),
    path("proposals/<uuid:proposal_id>/moa-draft/",
        views.proposal_moa_draft,
        name="proposal_moa_draft"),
    ]