from django.contrib import admin

from .models import Profile, Signatory, SiteConfiguration, SiteConfigurationLog


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
