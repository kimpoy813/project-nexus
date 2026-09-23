from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import NexusSetPasswordForm


urlpatterns = [
    # Authentication
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("logout-idle/", views.logout_idle_view, name="logout_idle"),
    path("debug-login/", views.debug_login_view, name="debug_login"),

    # Email verification
    path("verify/<uidb64>/<token>/", views.verify_email, name="verify_email"),

    # Dashboard redirects
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/redirect/", views.dashboard_redirect, name="dashboard_redirect"),

    # Role-based dashboards
    path("dashboard/faculty/", views.faculty_dashboard, name="faculty_dashboard"),
    path("dashboard/staff/", views.staff_dashboard, name="staff_dashboard"),
    path("dashboard/evaluator/", views.evaluator_dashboard, name="evaluator_dashboard"),
    path(
        "dashboard/department-coordinator/",
        views.department_coordinator_dashboard,
        name="department_coordinator_dashboard",
    ),
    path(
        "dashboard/campus-coordinator/",
        views.campus_coordinator_dashboard,
        name="campus_coordinator_dashboard",
    ),
    path("dashboard/director/", views.director_dashboard, name="director_dashboard"),
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),

    # Faculty-like draft deletion
    path(
        "dashboard/faculty/drafts/<uuid:proposal_id>/delete/",
        views.faculty_delete_draft,
        name="faculty_delete_draft",
    ),

    # Profile
    path("profile/", views.profile_view, name="profile_view"),
    path("profile/edit/", views.profile_edit_view, name="profile_edit"),

    # Campus / College / Department AJAX
    path("ajax/colleges/", views.get_colleges_ajax, name="get_colleges_ajax"),
    path("ajax/departments/", views.get_departments_ajax, name="get_departments_ajax"),

    # Logged-in change-password by email
    path(
        "password/change-email/",
        views.change_password_email_view,
        name="change_password",
    ),

    # Public forgot-password flow
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.html",
            html_email_template_name="accounts/email/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            form_class=NexusSetPasswordForm,
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    # Admin user and role management
    path("manage-roles/", views.manage_roles, name="manage_roles"),
    path("admin/create-account/", views.admin_create_account, name="admin_create_account"),
    path("admin/site-control/", views.admin_site_control, name="admin_site_control"),
    path("admin/users/<int:user_id>/", views.admin_user_detail, name="admin_user_detail"),
    path("admin/users/<int:user_id>/edit/", views.admin_edit_user, name="admin_edit_user"),

    # Admin content dashboard
    path("admin/content/", views.admin_content_dashboard, name="admin_content_dashboard"),

    # Public page content editor (Home, Services, Reports, Achievements).
    # NOTE: literal sub-paths (logs/) must come before the <slug> catch-all.
    path("admin/pages/", views.page_content_list, name="page_content_list"),
    path("admin/pages/logs/", views.page_content_logs, name="page_content_logs"),
    path("admin/pages/<slug:slug>/", views.page_content_edit, name="page_content_edit"),
    path("admin/pages/<slug:slug>/sections/new/", views.page_section_create, name="page_section_create"),
    # Drag a no-code builder from the palette onto the page.
    path("admin/pages/<slug:slug>/sections/add-source/", views.page_section_add_source, name="page_section_add_source"),
    # Drag a section into a new position.
    path("admin/pages/<slug:slug>/sections/reorder/", views.page_sections_reorder, name="page_sections_reorder"),
    path("admin/pages/sections/<int:pk>/edit/", views.page_section_edit, name="page_section_edit"),
    path("admin/pages/sections/<int:pk>/delete/", views.page_section_delete, name="page_section_delete"),
    path("admin/pages/sections/<int:pk>/move/", views.page_section_move, name="page_section_move"),
    # Drag the items *inside* a source (thrust cards, SDG goals, processes).
    path("admin/content-sources/<str:source_key>/reorder/", views.content_source_reorder, name="content_source_reorder"),

    # Sustainable Development Goals — the source behind the SDG block
    path("admin/sdgs/", views.sdg_goals_manager, name="sdg_goals_manager"),
    path("admin/sdgs/create/", views.sdg_goal_create, name="sdg_goal_create"),
    path("admin/sdgs/<int:pk>/edit/", views.sdg_goal_update, name="sdg_goal_update"),
    path("admin/sdgs/<int:pk>/delete/", views.sdg_goal_delete, name="sdg_goal_delete"),

    # Home page built-in sections (headings + Extension Thrust cards)
    path("admin/home-sections/", views.home_sections_manager, name="home_sections_manager"),
    path("admin/home-sections/thrusts/new/", views.home_thrust_create, name="home_thrust_create"),
    path("admin/home-sections/thrusts/<int:pk>/edit/", views.home_thrust_edit, name="home_thrust_edit"),
    path("admin/home-sections/thrusts/<int:pk>/delete/", views.home_thrust_delete, name="home_thrust_delete"),
    path("admin/home-sections/thrusts/<int:pk>/move/", views.home_thrust_move, name="home_thrust_move"),

    # Home inline editors — every Linked-Data type editable directly on the
    # Home Page content editor (mirrors the standalone managers above).
    path("admin/pages/home/inline/thrusts/create/", views.home_inline_thrust_create, name="home_inline_thrust_create"),
    path("admin/pages/home/inline/thrusts/<int:pk>/edit/", views.home_inline_thrust_update, name="home_inline_thrust_update"),
    path("admin/pages/home/inline/thrusts/<int:pk>/delete/", views.home_inline_thrust_delete, name="home_inline_thrust_delete"),
    path("admin/pages/home/inline/thrusts/<int:pk>/move/", views.home_inline_thrust_move, name="home_inline_thrust_move"),
    path("admin/pages/home/inline/personnel/create/", views.home_inline_personnel_create, name="home_inline_personnel_create"),
    path("admin/pages/home/inline/personnel/<int:pk>/edit/", views.home_inline_personnel_update, name="home_inline_personnel_update"),
    path("admin/pages/home/inline/personnel/<int:pk>/delete/", views.home_inline_personnel_delete, name="home_inline_personnel_delete"),
    path("admin/pages/home/inline/activities/create/", views.home_inline_activity_create, name="home_inline_activity_create"),
    path("admin/pages/home/inline/activities/<int:pk>/edit/", views.home_inline_activity_update, name="home_inline_activity_update"),
    path("admin/pages/home/inline/activities/<int:pk>/delete/", views.home_inline_activity_delete, name="home_inline_activity_delete"),
    path("admin/pages/home/inline/processes/create/", views.home_inline_process_create, name="home_inline_process_create"),
    path("admin/pages/home/inline/processes/<int:pk>/edit/", views.home_inline_process_update, name="home_inline_process_update"),
    path("admin/pages/home/inline/processes/<int:pk>/delete/", views.home_inline_process_delete, name="home_inline_process_delete"),
    path("admin/pages/home/inline/targets/create/", views.home_inline_target_create, name="home_inline_target_create"),
    path("admin/pages/home/inline/targets/<int:pk>/edit/", views.home_inline_target_update, name="home_inline_target_update"),
    path("admin/pages/home/inline/targets/<int:pk>/delete/", views.home_inline_target_delete, name="home_inline_target_delete"),

    # Services page workflow phases (Proposal / MOA / Implementation)
    path("admin/workflow-phases/", views.workflow_phases_manager, name="workflow_phases_manager"),

    # Signatories management
    path("admin/signatories/", views.signatories_list, name="signatories_list"),
    path("admin/signatories/create/", views.signatory_create, name="signatory_create"),
    path("admin/signatories/<int:pk>/edit/", views.signatory_edit, name="signatory_edit"),
    path("admin/signatories/<int:pk>/delete/", views.signatory_delete, name="signatory_delete"),

    # Campuses management
    path("admin/campuses/", views.campuses_list, name="campuses_list"),
    path("admin/campuses/create/", views.campus_create, name="campus_create"),
    path("admin/campuses/<int:pk>/edit/", views.campus_edit, name="campus_edit"),
    path("admin/campuses/<int:pk>/delete/", views.campus_delete, name="campus_delete"),

    # Colleges management
    path("admin/colleges/", views.colleges_list, name="colleges_list"),
    path("admin/colleges/create/", views.college_create, name="college_create"),
    path("admin/colleges/<int:pk>/edit/", views.college_edit, name="college_edit"),
    path("admin/colleges/<int:pk>/delete/", views.college_delete, name="college_delete"),

    # Departments management
    path("admin/departments/", views.departments_list, name="departments_list"),
    path("admin/departments/create/", views.department_create, name="department_create"),
    path("admin/departments/<int:pk>/edit/", views.department_edit, name="department_edit"),
    path("admin/departments/<int:pk>/delete/", views.department_delete, name="department_delete"),


    # Personnel management
    path("admin/personnel/", views.personnel_list, name="personnel_list"),
    path("admin/personnel/create/", views.personnel_create, name="personnel_create"),
    path("admin/personnel/<int:pk>/edit/", views.personnel_edit, name="personnel_edit"),
    path("admin/personnel/<int:pk>/delete/", views.personnel_delete, name="personnel_delete"),

    # Activities management
    path("admin/activities/", views.activities_list, name="activities_list"),
    path("admin/activities/create/", views.activity_create, name="activity_create"),
    path("admin/activities/<int:pk>/edit/", views.activity_edit, name="activity_edit"),
    path("admin/activities/<int:pk>/delete/", views.activity_delete, name="activity_delete"),

    # Processes management
    path("admin/processes/", views.processes_list, name="processes_list"),
    path("admin/processes/create/", views.process_create, name="process_create"),
    path("admin/processes/<int:pk>/edit/", views.process_edit, name="process_edit"),
    path("admin/processes/<int:pk>/delete/", views.process_delete, name="process_delete"),
    path(
        "admin/processes/<int:pk>/reorder-steps/",
        views.reorder_process_steps,
        name="reorder_process_steps",
    ),

    # Admin no-code builder
    path("admin/templates/", views.document_templates_list, name="document_templates_list"),
    path("admin/templates/create/", views.document_template_create, name="document_template_create"),
    path("admin/templates/<int:pk>/edit/", views.document_template_edit, name="document_template_edit"),
    path("admin/templates/<int:pk>/delete/", views.document_template_delete, name="document_template_delete"),
    path(
        "admin/proposal-templates/",
        views.proposal_templates_list,
        name="proposal_templates_list",
    ),
    path(
        "admin/proposal-templates/replace/",
        views.proposal_template_replace,
        name="proposal_template_replace",
    ),
    path(
        "admin/proposal-templates/reset/",
        views.proposal_template_reset,
        name="proposal_template_reset",
    ),
    path(
        "admin/proposal-templates/<str:key>/download/",
        views.proposal_template_download,
        name="proposal_template_download",
    ),
    path(
        "admin/proposal-templates/<str:key>/edit/",
        views.proposal_template_edit,
        name="proposal_template_edit",
    ),
    path(
        "admin/proposal-templates/custom/add/",
        views.proposal_custom_template_add,
        name="proposal_custom_template_add",
    ),
    path(
        "admin/proposal-templates/custom/<int:pk>/edit/",
        views.proposal_custom_template_edit,
        name="proposal_custom_template_edit",
    ),
    path(
        "admin/proposal-templates/custom/<int:pk>/download/",
        views.proposal_custom_template_download,
        name="proposal_custom_template_download",
    ),
    path(
        "admin/proposal-templates/custom/<int:pk>/delete/",
        views.proposal_custom_template_delete,
        name="proposal_custom_template_delete",
    ),

    path("admin/wizard-steps/", views.wizard_steps_manager, name="wizard_steps_manager"),
    path("admin/wizard-steps/create/", views.wizard_step_create, name="wizard_step_create"),
    path("admin/wizard-steps/reorder/", views.wizard_steps_reorder, name="wizard_steps_reorder"),
    path("admin/wizard-steps/<int:step_no>/edit/", views.wizard_step_edit, name="wizard_step_edit"),
    path("admin/wizard-steps/<int:step_no>/delete/", views.wizard_step_delete, name="wizard_step_delete"),
    path("admin/role-capabilities/", views.role_capabilities_manager, name="role_capabilities_manager"),
    path("accomplishments/", views.accomplishment_reports_list, name="accomplishment_reports_list"),
    path("accomplishments/create/", views.accomplishment_report_create, name="accomplishment_report_create"),

    # Targets management
    path("admin/targets/", views.targets_list, name="targets_list"),
    path("admin/targets/create/", views.target_create, name="target_create"),
    path("admin/targets/<int:pk>/edit/", views.target_edit, name="target_edit"),
    path("admin/targets/<int:pk>/delete/", views.target_delete, name="target_delete"),

    # Director evaluator assignment
    path(
        "director/proposals/<uuid:proposal_id>/assign-evaluator/<int:evaluator_id>/",
        views.proposal_assign_evaluator,
        name="proposal_assign_evaluator",
    ),
    path(
        "director/proposals/<uuid:proposal_id>/remove-evaluator/<int:evaluator_id>/",
        views.proposal_remove_evaluator,
        name="proposal_remove_evaluator",
    ),
    path(
        "proposals/<uuid:proposal_id>/mark-ready-for-summary/",
        views.proposal_mark_ready_for_summary,
        name="proposal_mark_ready_for_summary",
    ),
    
]