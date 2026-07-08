from django.contrib import admin

from .models import ProposalPhaseLog


@admin.register(ProposalPhaseLog)
class ProposalPhaseLogAdmin(admin.ModelAdmin):
    list_display = ("proposal", "phase", "from_status", "to_status", "changed_by", "created_at")
    list_filter = ("phase", "to_status")
    search_fields = ("proposal__title", "proposal__research_title", "remarks")
    readonly_fields = ("proposal", "phase", "from_status", "to_status", "remarks", "changed_by", "created_at")
    ordering = ("-created_at",)