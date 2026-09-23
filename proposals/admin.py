from django.contrib import admin

from .models import ProposalPhaseLog
from .models import ProposalTemplateOverride


@admin.register(ProposalPhaseLog)
class ProposalPhaseLogAdmin(admin.ModelAdmin):
    list_display = ("proposal", "phase", "from_status", "to_status", "changed_by", "created_at")
    list_filter = ("phase", "to_status")
    search_fields = ("proposal__title", "proposal__research_title", "remarks")
    readonly_fields = ("proposal", "phase", "from_status", "to_status", "remarks", "changed_by", "created_at")
    ordering = ("-created_at",)

@admin.register(ProposalTemplateOverride)
class ProposalTemplateOverrideAdmin(admin.ModelAdmin):
    list_display = ("key", "file", "uploaded_by", "updated_at")
    list_filter = ("key",)
    search_fields = ("key", "notes")
    readonly_fields = ("uploaded_at", "updated_at")
    ordering = ("key",)
