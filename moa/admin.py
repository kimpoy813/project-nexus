from django.contrib import admin

from .models import MOADocument


@admin.register(MOADocument)
class MOADocumentAdmin(admin.ModelAdmin):
    list_display = ("proposal", "version", "status", "uploaded_by", "uploaded_at")
    list_filter = ("status", "uploaded_at")
    search_fields = ("proposal__title", "uploaded_by__username", "uploaded_by__first_name", "uploaded_by__last_name")
    readonly_fields = ("version", "uploaded_at")
    ordering = ("-uploaded_at",)
