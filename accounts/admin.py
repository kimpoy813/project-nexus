from django.contrib import admin

from .models import Profile, Signatory, SiteConfiguration, SiteConfigurationLog, Campus, College, Department
from details.models import (
    AccomplishmentReport, DocumentTemplate, DynamicFormTemplate, DynamicFormField,
    DynamicFormResponse, DynamicFormAnswer, ProposalWizardStepConfig, RoleCapability,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "role", "campus", "email_verified", "updated_at")
    list_filter = ("role", "campus", "email_verified")
    search_fields = ("full_name", "user__username", "user__email", "campus", "college", "department")


@admin.register(Signatory)
class SignatoryAdmin(admin.ModelAdmin):
    list_display = ("position_title", "display_name", "scope_label", "updated_at")
    list_filter = ("position_title", "campus")
    search_fields = ("full_name", "credentials", "campus", "college", "department")


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ("site_name", "maintenance_mode", "registration_enabled", "announcement_enabled", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SiteConfigurationLog)
class SiteConfigurationLogAdmin(admin.ModelAdmin):
    list_display = ("summary", "changed_by", "created_at")
    readonly_fields = ("changed_by", "summary", "before", "after", "created_at")
    search_fields = ("summary", "changed_by__username", "changed_by__profile__full_name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class DynamicFormFieldInline(admin.TabularInline):
    model = DynamicFormField
    extra = 1


@admin.register(DynamicFormTemplate)
class DynamicFormTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "applies_to", "is_active", "updated_at")
    list_filter = ("applies_to", "is_active")
    search_fields = ("name", "description", "instructions")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [DynamicFormFieldInline]


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "version_label", "is_active", "updated_at")
    list_filter = ("category", "is_active")
    search_fields = ("title", "description", "version_label")


class DynamicFormAnswerInline(admin.TabularInline):
    model = DynamicFormAnswer
    extra = 0
    readonly_fields = ("field", "value", "file", "updated_at")
    can_delete = False


@admin.register(DynamicFormResponse)
class DynamicFormResponseAdmin(admin.ModelAdmin):
    list_display = ("form", "proposal", "submitted_by", "updated_at")
    list_filter = ("form__applies_to", "form")
    search_fields = ("form__name", "proposal__title", "proposal__research_title", "submitted_by__username")
    inlines = [DynamicFormAnswerInline]


@admin.register(ProposalWizardStepConfig)
class ProposalWizardStepConfigAdmin(admin.ModelAdmin):
    list_display = ("step_no", "flow", "title", "is_visible", "is_required", "updated_at")
    list_filter = ("flow", "is_visible", "is_required")
    search_fields = ("title", "description", "instructions")


@admin.register(RoleCapability)
class RoleCapabilityAdmin(admin.ModelAdmin):
    list_display = ("role", "capability", "enabled", "updated_at")
    list_filter = ("role", "capability", "enabled")
    search_fields = ("notes",)


@admin.register(AccomplishmentReport)
class AccomplishmentReportAdmin(admin.ModelAdmin):
    list_display = ("title", "year", "quarter", "campus", "department", "submitted_by", "submitted_at")
    list_filter = ("year", "quarter", "campus")
    search_fields = ("title", "narrative", "submitted_by__username", "submitted_by__profile__full_name")


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("name", "campus")
    list_filter = ("campus",)
    search_fields = ("name", "campus__name")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "college", "campus")
    list_filter = ("campus", "college")
    search_fields = ("name", "college__name", "campus__name")
