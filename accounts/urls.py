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
    path("admin/users/<int:user_id>/", views.admin_user_detail, name="admin_user_detail"),
    path("admin/users/<int:user_id>/edit/", views.admin_edit_user, name="admin_edit_user"),

    # Admin content dashboard
    path("admin/content/", views.admin_content_dashboard, name="admin_content_dashboard"),

    # Signatories management
    path("admin/signatories/", views.signatories_list, name="signatories_list"),
    path("admin/signatories/create/", views.signatory_create, name="signatory_create"),
    path("admin/signatories/<int:pk>/edit/", views.signatory_edit, name="signatory_edit"),
    path("admin/signatories/<int:pk>/delete/", views.signatory_delete, name="signatory_delete"),


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