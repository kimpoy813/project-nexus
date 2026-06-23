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