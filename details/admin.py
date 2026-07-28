from django.contrib import admin
from .models import (
    Personnel, Activity, ProcessStep, Target, ExtensionProcess,
    SitePage, PageSection, HomeThrust, HomeSectionHeading,
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
