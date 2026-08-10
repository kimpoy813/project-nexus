from django.db import models
from django_ckeditor_5.fields import CKEditor5Field

class Personnel(models.Model):
    name = models.CharField(max_length=150)
    position = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    photo = models.ImageField(upload_to='personnel/')

    def __str__(self):
        return self.name

class Activity(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    # REMOVE/STOP using single "date" if you have it, or keep it but it becomes legacy
    image = models.ImageField(upload_to="activities/", blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    @property
    def primary_date(self):
        first = self.dates.order_by("date").first()
        return first.date if first else None


class ActivityDate(models.Model):
    activity = models.ForeignKey(Activity, related_name="dates", on_delete=models.CASCADE)
    date = models.DateField()

    class Meta:
        ordering = ["date"]
        unique_together = ("activity", "date")

    def __str__(self):
        return f"{self.activity.title} - {self.date}"
    
from django.db import models
from django.db.models import Max

class ExtensionProcess(models.Model):
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(blank=True, null=True)  # IMPORTANT: no default=1

    def save(self, *args, **kwargs):
        # Auto-increment ONLY when creating a new process
        if self._state.adding:
            max_order = ExtensionProcess.objects.aggregate(m=Max("order"))["m"] or 0
            self.order = max_order + 1
        super().save(*args, **kwargs)


class ProcessStep(models.Model):
    process = models.ForeignKey(ExtensionProcess, related_name="steps", on_delete=models.CASCADE)
    description = models.TextField()
    order = models.PositiveIntegerField(blank=True, null=True)  # IMPORTANT: no default=1

    def save(self, *args, **kwargs):
        # Auto-increment ONLY when creating a new step
        if self._state.adding:
            max_order = ProcessStep.objects.filter(process=self.process).aggregate(m=Max("order"))["m"] or 0
            self.order = max_order + 1
        super().save(*args, **kwargs)

class Target(models.Model):
    METRIC_CHOICES = [
        ('programs', 'Programs'),
        ('participants', 'Participants'),
        ('partners', 'Partners'),
        ('technology', 'Technology Transfer'),
    ]

    year = models.PositiveIntegerField(default=2026)
    campus = models.CharField(max_length=100)
    metric = models.CharField(max_length=32, choices=METRIC_CHOICES)

    # Planned by quarter (editable)
    planned_q1 = models.PositiveIntegerField(default=0)
    planned_q2 = models.PositiveIntegerField(default=0)
    planned_q3 = models.PositiveIntegerField(default=0)
    planned_q4 = models.PositiveIntegerField(default=0)
    # Yearly planned total (editable, but auto-filled if zero)
    planned_total = models.PositiveIntegerField(default=0)

    # Actual accomplishments by quarter (editable)
    actual_q1 = models.PositiveIntegerField(default=0)
    actual_q2 = models.PositiveIntegerField(default=0)
    actual_q3 = models.PositiveIntegerField(default=0)
    actual_q4 = models.PositiveIntegerField(default=0)
    # Yearly actual total (editable, but auto-filled if zero)
    actual_total = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('year', 'campus', 'metric')
        ordering = ['campus', 'metric']

    def save(self, *args, **kwargs):
        # If totals left as 0, auto-calc from quarters
        calc_planned = self.planned_q1 + self.planned_q2 + self.planned_q3 + self.planned_q4
        calc_actual = self.actual_q1 + self.actual_q2 + self.actual_q3 + self.actual_q4

        if not self.planned_total:
            self.planned_total = calc_planned
        if not self.actual_total:
            self.actual_total = calc_actual

        super().save(*args, **kwargs)

    def computed_planned_total(self):
        return self.planned_q1 + self.planned_q2 + self.planned_q3 + self.planned_q4

    def computed_actual_total(self):
        return self.actual_q1 + self.actual_q2 + self.actual_q3 + self.actual_q4

    def __str__(self):
        return f"{self.year} • {self.campus} • {self.get_metric_display()}"

# ==============================
# ADMIN NO-CODE BUILDER MODELS
# ==============================

class DocumentTemplate(models.Model):
    """Admin-managed downloadable files used by the Extension Office."""

    class Category(models.TextChoices):
        PROPOSAL = "PROPOSAL", "Proposal"
        MOA = "MOA", "MOA"
        IMPLEMENTATION = "IMPLEMENTATION", "Implementation"
        REPORT = "REPORT", "Report"
        CERTIFICATE = "CERTIFICATE", "Certificate"
        OTHER = "OTHER", "Other"

    title = models.CharField(max_length=180)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.PROPOSAL)
    description = models.TextField(blank=True, default="")
    file = models.FileField(upload_to="office_templates/")
    version_label = models.CharField(max_length=40, blank=True, default="")
    is_active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "title", "-updated_at"]

    def __str__(self):
        return self.title


class DynamicFormTemplate(models.Model):
    """Admin-defined form blueprint for office checklists/intake forms."""

    class AppliesTo(models.TextChoices):
        PROPOSAL = "PROPOSAL", "Proposal"
        MOA = "MOA", "MOA"
        IMPLEMENTATION = "IMPLEMENTATION", "Implementation"
        EVALUATION = "EVALUATION", "Evaluation"
        GENERAL = "GENERAL", "General"

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    applies_to = models.CharField(max_length=30, choices=AppliesTo.choices, default=AppliesTo.GENERAL)
    proposal_wizard_step = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Optional: show this form inside proposal wizard step when Applies To is Proposal.",
    )
    blocks_proposal_submission = models.BooleanField(
        default=True,
        help_text="If enabled, required fields in this form must be completed before proposal submission.",
    )
    description = models.TextField(blank=True, default="")
    instructions = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["applies_to", "name"]

    def __str__(self):
        return self.name


class DynamicFormField(models.Model):
    """Field definitions belonging to a DynamicFormTemplate."""

    class FieldType(models.TextChoices):
        TEXT = "TEXT", "Short Text"
        TEXTAREA = "TEXTAREA", "Long Text"
        NUMBER = "NUMBER", "Number"
        DATE = "DATE", "Date"
        EMAIL = "EMAIL", "Email"
        SELECT = "SELECT", "Dropdown"
        CHECKBOX = "CHECKBOX", "Checkbox"
        FILE = "FILE", "File Upload"

    form = models.ForeignKey(DynamicFormTemplate, related_name="fields", on_delete=models.CASCADE)
    label = models.CharField(max_length=180)
    field_key = models.SlugField(max_length=120)
    field_type = models.CharField(max_length=20, choices=FieldType.choices, default=FieldType.TEXT)
    required = models.BooleanField(default=False)
    placeholder = models.CharField(max_length=180, blank=True, default="")
    help_text = models.CharField(max_length=255, blank=True, default="")
    choices_text = models.TextField(blank=True, default="", help_text="One dropdown choice per line.")
    depends_on_key = models.CharField(max_length=120, blank=True, default="", help_text="The key of the parent field this field depends on.")
    depends_on_value = models.CharField(max_length=255, blank=True, default="", help_text="The parent field value(s), comma-separated, that make this field visible.")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["form", "field_key"], name="unique_dynamic_form_field_key"),
        ]

    def __str__(self):
        return f"{self.form.name}: {self.label}"

    @property
    def choices_list(self):
        return [line.strip() for line in self.choices_text.splitlines() if line.strip()]

    @property
    def parsed_choices(self):
        result = []
        for line in self.choices_list:
            if "|" in line:
                val, label = line.split("|", 1)
                result.append({"value": val.strip(), "label": label.strip()})
            else:
                result.append({"value": line, "label": line})
        return result


class DynamicFormResponse(models.Model):
    """A filled instance of an admin-built form, optionally attached to a proposal."""

    form = models.ForeignKey(DynamicFormTemplate, related_name="responses", on_delete=models.CASCADE)
    proposal = models.ForeignKey(
        "proposals.Proposal",
        related_name="dynamic_form_responses",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    submitted_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dynamic_form_responses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["form", "proposal"],
                condition=models.Q(proposal__isnull=False),
                name="unique_dynamic_form_response_per_proposal",
            ),
        ]

    def __str__(self):
        target = self.proposal.display_title if self.proposal_id else "General"
        return f"{self.form.name} - {target}"


class DynamicFormAnswer(models.Model):
    response = models.ForeignKey(DynamicFormResponse, related_name="answers", on_delete=models.CASCADE)
    field = models.ForeignKey(DynamicFormField, related_name="answers", on_delete=models.CASCADE)
    value = models.TextField(blank=True, default="")
    file = models.FileField(upload_to="dynamic_form_answers/", blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["field__order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["response", "field"], name="unique_answer_per_dynamic_field"),
        ]

    def __str__(self):
        return f"{self.response} - {self.field.label}"

    @property
    def has_value(self):
        return bool((self.value or "").strip() or self.file)


class ProposalWizardStepConfig(models.Model):
    """Admin overrides for the built-in 19 proposal wizard steps."""

    step_no = models.PositiveSmallIntegerField(unique=True)
    title = models.CharField(max_length=160)
    description = models.CharField(max_length=255, blank=True, default="")
    instructions = models.TextField(blank=True, default="")
    is_visible = models.BooleanField(default=True)
    is_required = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["step_no"]

    def __str__(self):
        return f"Step {self.step_no}: {self.title}"


class RoleCapability(models.Model):
    """Admin-managed feature switches for each account role."""

    class Role(models.TextChoices):
        FACULTY = "FACULTY", "Faculty"
        STAFF = "STAFF", "Staff"
        EVALUATOR = "EVALUATOR", "Evaluator"
        DEPARTMENT_COORDINATOR = "DEPARTMENT_COORDINATOR", "Department Coordinator"
        CAMPUS_COORDINATOR = "CAMPUS_COORDINATOR", "Campus Coordinator"
        DIRECTOR = "DIRECTOR", "Director"
        ADMIN = "ADMIN", "Admin"

    class Capability(models.TextChoices):
        CREATE_PROPOSAL = "CREATE_PROPOSAL", "Create proposals"
        REVIEW_PROPOSAL = "REVIEW_PROPOSAL", "Review/comment on proposals"
        MANAGE_MOA = "MANAGE_MOA", "Manage MOA workflow"
        MANAGE_IMPLEMENTATION = "MANAGE_IMPLEMENTATION", "Manage implementation workflow"
        SUBMIT_QUARTERLY_ACCOMPLISHMENT = "SUBMIT_QUARTERLY_ACCOMPLISHMENT", "Submit quarterly accomplishment reports"
        VIEW_ANALYTICS = "VIEW_ANALYTICS", "View analytics dashboards"

    role = models.CharField(max_length=50, choices=Role.choices)
    capability = models.CharField(max_length=80, choices=Capability.choices)
    enabled = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role", "capability"]
        constraints = [
            models.UniqueConstraint(fields=["role", "capability"], name="unique_role_capability"),
        ]

    def __str__(self):
        return f"{self.get_role_display()} - {self.get_capability_display()}"


class AccomplishmentReport(models.Model):
    """Quarterly accomplishment report submitted by roles with the capability."""

    class Quarter(models.TextChoices):
        Q1 = "Q1", "1st Quarter"
        Q2 = "Q2", "2nd Quarter"
        Q3 = "Q3", "3rd Quarter"
        Q4 = "Q4", "4th Quarter"

    title = models.CharField(max_length=220)
    year = models.PositiveIntegerField(default=2026)
    quarter = models.CharField(max_length=2, choices=Quarter.choices)
    campus = models.CharField(max_length=150, blank=True, default="")
    college = models.CharField(max_length=255, blank=True, default="")
    department = models.CharField(max_length=255, blank=True, default="")
    narrative = models.TextField(blank=True, default="")
    activities_count = models.PositiveIntegerField(default=0)
    beneficiaries_count = models.PositiveIntegerField(default=0)
    partners_count = models.PositiveIntegerField(default=0)
    attachment = models.FileField(upload_to="accomplishment_reports/", blank=True, null=True)
    submitted_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accomplishment_reports",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "quarter", "campus", "department"]

    def __str__(self):
        return f"{self.title} ({self.year} {self.quarter})"


# ==============================
# EDITABLE PAGE CONTENT (ADMIN MANAGED CMS)
# ==============================

class SitePage(models.Model):
    """
    An admin-editable public page (Home, Services, Reports, Achievements).

    Rows are seeded by migration for the four known pages and are looked up by
    ``slug``. Each page owns an ordered set of :class:`PageSection` records that
    hold the actual rich-text content.
    """

    class Slug(models.TextChoices):
        HOME = "home", "Home"
        SERVICES = "services", "Services"
        REPORTS = "reports", "Reports"
        ACHIEVEMENTS = "achievements", "Achievements"

    slug = models.SlugField(max_length=40, unique=True, choices=Slug.choices)
    title = models.CharField(max_length=150)

    # Hero / masthead
    hero_eyebrow = models.CharField(max_length=120, blank=True, default="")
    hero_heading = models.CharField(max_length=220, blank=True, default="")
    hero_subheading = models.TextField(blank=True, default="")

    # Browser <title> / SEO
    meta_title = models.CharField(max_length=180, blank=True, default="")
    meta_description = models.TextField(blank=True, default="")

    is_published = models.BooleanField(
        default=True,
        help_text="Unpublish to hide this page from visitors (admins can still preview it).",
    )

    updated_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_page_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]
        verbose_name = "Site Page"

    def __str__(self):
        return self.title or self.get_slug_display()

    @classmethod
    def get_for(cls, slug):
        """Fetch a page by slug, creating a sensible default row if missing."""
        defaults = {"title": dict(cls.Slug.choices).get(slug, slug.title())}
        obj, _ = cls.objects.get_or_create(slug=slug, defaults=defaults)
        return obj

    @property
    def visible_sections(self):
        return self.sections.filter(is_visible=True)


class PageSection(models.Model):
    """An ordered, rich-text content block belonging to a :class:`SitePage`."""

    class Layout(models.TextChoices):
        RICH_TEXT = "RICH_TEXT", "Rich text"
        CARD = "CARD", "Card"
        CALLOUT = "CALLOUT", "Callout / highlight"

    page = models.ForeignKey(SitePage, related_name="sections", on_delete=models.CASCADE)
    heading = models.CharField(max_length=220, blank=True, default="")
    subheading = models.CharField(max_length=300, blank=True, default="")
    body = CKEditor5Field(blank=True, default="", config_name="default")
    layout = models.CharField(max_length=20, choices=Layout.choices, default=Layout.RICH_TEXT)

    anchor = models.SlugField(
        max_length=60,
        blank=True,
        default="",
        help_text="Optional #anchor so the section can be linked to directly.",
    )
    image = models.ImageField(upload_to="page_sections/", blank=True, null=True)

    is_visible = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Page Section"

    def __str__(self):
        return f"{self.page.slug} · {self.heading or 'Untitled section'}"

    def save(self, *args, **kwargs):
        if self.order is None or self.order == 0:
            last = PageSection.objects.filter(page=self.page).aggregate(Max("order"))["order__max"]
            self.order = (last or 0) + 1
        super().save(*args, **kwargs)


# ==============================
# HOME PAGE BUILT-IN SECTIONS (ADMIN MANAGED)
# ==============================

class HomeSectionHeading(models.Model):
    """
    Editable headings for the Home page's built-in sections.

    The sections themselves (Thrust, Processes, Targets, Personnel, SDGs,
    Activities) are rendered from their own data, but their titles and
    subtitles used to be hardcoded. One row per section, seeded by migration.
    """

    class Section(models.TextChoices):
        THRUST = "thrust", "Extension Thrust"
        PROCESS = "process", "Extension Processes"
        TARGETS = "targets", "Extension Targets"
        PERSONNEL = "personnel", "Extension Personnel"
        SDG = "sdg", "Sustainable Development Goals"
        ACTIVITIES = "activities", "Extension Activities"

    section = models.SlugField(max_length=40, unique=True, choices=Section.choices)
    heading = models.CharField(max_length=200, blank=True, default="")
    subtitle = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text='Emphasised line under the heading, e.g. "Isem Ni Aran".',
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text='Smaller line under the subtitle, e.g. "Approved BR No. 95-1517, S. 2022".',
    )
    nav_label = models.CharField(
        max_length=60,
        blank=True,
        default="",
        help_text="Label used in the sticky section navigation.",
    )
    is_visible = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this whole section from the Home page.",
    )
    order = models.PositiveIntegerField(default=1)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Home Section Heading"

    def __str__(self):
        return self.heading or self.get_section_display()

    @classmethod
    def get_for(cls, section):
        obj, _ = cls.objects.get_or_create(
            section=section,
            defaults={"heading": dict(cls.Section.choices).get(section, section.title())},
        )
        return obj

    @classmethod
    def as_map(cls):
        """All headings keyed by section, for cheap template lookup."""
        return {row.section: row for row in cls.objects.all()}


class HomeThrust(models.Model):
    """
    A single Extension Thrust card on the Home page.

    Replaces the 14 hardcoded cards so the Extension Office can add, edit,
    reorder, or remove thrusts without a developer.
    """

    # Tailwind text colour classes offered in the admin picker. Kept as an
    # explicit allow-list so admin input can never inject arbitrary classes.
    COLOR_CHOICES = [
        ("text-green-600", "Green"),
        ("text-blue-600", "Blue"),
        ("text-yellow-500", "Yellow"),
        ("text-purple-600", "Purple"),
        ("text-red-600", "Red"),
        ("text-indigo-600", "Indigo"),
        ("text-pink-500", "Pink"),
        ("text-teal-600", "Teal"),
        ("text-orange-500", "Orange"),
        ("text-lime-600", "Lime"),
        ("text-rose-500", "Rose"),
        ("text-amber-500", "Amber"),
        ("text-cyan-600", "Cyan"),
        ("text-violet-600", "Violet"),
        ("text-gray-700", "Gray"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    color_class = models.CharField(
        max_length=40,
        choices=COLOR_CHOICES,
        default="text-green-600",
        help_text="Accent colour for the card title.",
    )
    is_visible = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Home Extension Thrust"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.order is None or self.order == 0:
            last = HomeThrust.objects.aggregate(Max("order"))["order__max"]
            self.order = (last or 0) + 1
        super().save(*args, **kwargs)


# ==============================
# WORKFLOW PHASES (ADMIN MANAGED)
# ==============================

class WorkflowPhase(models.Model):
    """
    The Proposal / MOA / Implementation phase cards on the Services page.

    The underlying status codes and progress maps still live in the Proposal
    model (they drive real permissions and must stay in code), but the public
    presentation - label, summary, and progress weight - is admin-editable.
    """

    class Key(models.TextChoices):
        PROPOSAL = "proposal", "Proposal"
        MOA = "moa", "MOA"
        IMPLEMENTATION = "implementation", "Implementation"

    key = models.SlugField(
        max_length=30,
        unique=True,
        choices=Key.choices,
        help_text="Identifies which set of model statuses this phase displays.",
    )
    label = models.CharField(max_length=80)
    summary = models.TextField(blank=True, default="")
    weight_percent = models.PositiveSmallIntegerField(
        default=40,
        help_text="Share of overall progress, 0-100. Also sets the bar width.",
    )
    weight_label = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text='Caption beside the bar, e.g. "40% of overall progress when MOA is required".',
    )
    is_visible = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Workflow Phase"

    def __str__(self):
        return self.label or self.get_key_display()

    def save(self, *args, **kwargs):
        if self.weight_percent is None:
            self.weight_percent = 0
        self.weight_percent = max(0, min(100, int(self.weight_percent)))
        super().save(*args, **kwargs)

    @classmethod
    def ordered_visible(cls):
        return cls.objects.filter(is_visible=True)
