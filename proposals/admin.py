"""Admin access to the complete proposal lifecycle.

The dashboard contains friendly, purpose-built editors for common tasks. The
Django admin is the escape hatch for administrators: every proposal model is
registered here so no workflow data is trapped in a read-only screen.
"""
from django.contrib import admin
from django.apps import apps

from .models import ProposalPhaseLog


@admin.register(ProposalPhaseLog)
class ProposalPhaseLogAdmin(admin.ModelAdmin):
    list_display = ("proposal", "phase", "from_status", "to_status", "changed_by", "created_at")
    list_filter = ("phase", "to_status")
    search_fields = ("proposal__title", "proposal__research_title", "remarks")
    readonly_fields = ("proposal", "phase", "from_status", "to_status", "remarks", "changed_by", "created_at")
    ordering = ("-created_at",)


class ProposalLifecycleAdmin(admin.ModelAdmin):
    """Useful defaults while retaining all editable model fields."""
    list_per_page = 50
    save_on_top = True

    def get_search_fields(self, request):
        # Search text-like fields without hard-coding the large Proposal schema.
        return tuple(
            field.name for field in self.model._meta.get_fields()
            if getattr(field, "get_internal_type", lambda: "")() in {"CharField", "TextField"}
            and not getattr(field, "many_to_many", False)
        )[:12]


# Keep this intentionally model-driven. New proposal lifecycle models become
# editable automatically when added, rather than requiring another admin PR.
for model in apps.get_app_config("proposals").get_models():
    if model is ProposalPhaseLog or model in admin.site._registry:
        continue
    admin.site.register(model, ProposalLifecycleAdmin)
