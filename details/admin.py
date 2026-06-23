from django.contrib import admin
from .models import Personnel, Activity, ProcessStep, Target, ExtensionProcess

admin.site.register(Personnel)
admin.site.register(Activity)

class ProcessStepInline(admin.TabularInline):
    model = ProcessStep
    extra = 1
    ordering = ['order']

@admin.register(ExtensionProcess)
class ExtensionProcessAdmin(admin.ModelAdmin):
    list_display = ('title', 'order')
    ordering = ['order']
    inlines = [ProcessStepInline]

@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ('year', 'campus', 'metric', 'planned_total', 'actual_total')
    list_filter = ('year', 'campus', 'metric')
    search_fields = ('campus',)
    ordering = ('-year', 'campus', 'metric')