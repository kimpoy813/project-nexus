from django.contrib import admin
from django.apps import apps
from .models import (
    Personnel, Activity, ActivityDate, ProcessStep, ExtensionProcess, Target,
    SitePage, PageSection, HomeThrust, HomeSectionHeading, WorkflowPhase,
)

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

class PageSectionInline(admin.StackedInline):
    model = PageSection
    extra = 0
    ordering = ['order', 'id']

@admin.register(SitePage)
class SitePageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'updated_at')
    list_filter = ('is_published',)
    search_fields = ('title', 'hero_heading')
    inlines = [PageSectionInline]

@admin.register(PageSection)
class PageSectionAdmin(admin.ModelAdmin):
    list_display = ('heading', 'page', 'layout', 'is_visible', 'order')
    list_filter = ('page', 'layout', 'is_visible')
    search_fields = ('heading', 'subheading')
    ordering = ('page', 'order', 'id')

@admin.register(HomeThrust)
class HomeThrustAdmin(admin.ModelAdmin):
    list_display = ('title', 'color_class', 'is_visible', 'order')
    list_filter = ('is_visible',)
    search_fields = ('title', 'description')
    ordering = ('order', 'id')

@admin.register(HomeSectionHeading)
class HomeSectionHeadingAdmin(admin.ModelAdmin):
    list_display = ('section', 'heading', 'subtitle', 'is_visible', 'order')
    list_filter = ('is_visible',)
    ordering = ('order', 'id')

@admin.register(WorkflowPhase)
class WorkflowPhaseAdmin(admin.ModelAdmin):
    list_display = ('label', 'key', 'weight_percent', 'is_visible', 'order')
    list_filter = ('is_visible',)
    ordering = ('order', 'id')


class DetailsModelAdmin(admin.ModelAdmin):
    """Generic editor for detail/content records not covered by a dashboard."""
    list_per_page = 50
    save_on_top = True


# Activity dates, process steps, and any future detail models are editable from
# the admin automatically. Existing specialized admins above remain preferred.
for model in apps.get_app_config("details").get_models():
    if model in admin.site._registry:
        continue
    admin.site.register(model, DetailsModelAdmin)
