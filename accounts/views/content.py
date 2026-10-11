"""
Admin CRUD for public content: personnel, activities, processes, targets, signatories.
"""
import logging

import json
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.db.models import Min
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST
from details.models import Activity
from details.models import ActivityDate
from details.models import ExtensionProcess
from details.models import Personnel
from details.models import ProcessStep
from details.models import Target
from ..campus_data import get_campus_choices
from ..campus_data import get_college_choices
from ..campus_data import get_department_choices
from ..decorators import admin_required
from ..models import Profile
from .process_steps import _sync_process_steps
from .target_helpers import _parse_target_numbers
from ..models import Signatory
from ..models import Campus
from ..models import College
from ..models import Department

logger = logging.getLogger(__name__)

@login_required
@admin_required
def admin_content_dashboard(request):
    context = {
        "personnel_count": Personnel.objects.count(),
        "activities_count": Activity.objects.count(),
        "processes_count": ExtensionProcess.objects.count(),
        "targets_count": Target.objects.count(),
        "signatories_count": Signatory.objects.count(),
    }
    return render(request, "dashboard/admin/content_dashboard.html", context)


@login_required
@admin_required
def signatories_list(request):
    signatories = Signatory.objects.all().order_by(
        "position_title",
        "campus",
        "college",
        "department",
        "full_name",
    )
    return render(request, "dashboard/admin/signatories_list.html", {"signatories": signatories})


def _signatory_scope_meta(position_title):
    # Returns (scope_level, help_text)
    pt = (position_title or "").strip()

    global_positions = {
        Signatory.Position.DIRECTOR_EXTENSION,
        Signatory.Position.VPRDE,
        Signatory.Position.SUC_PRESIDENT_III,
    }
    campus_positions = {
        Signatory.Position.CAMPUS_EXTENSION_COORDINATOR,
        Signatory.Position.CAMPUS_DIRECTOR,
    }
    college_positions = {Signatory.Position.DEAN}
    dept_positions = {Signatory.Position.DEPARTMENT_EXTENSION_COORDINATOR}

    if pt in global_positions:
        return "global", "Global position: leave campus/college/department blank."
    if pt in campus_positions:
        return "campus", "Campus-scoped position: select a campus."
    if pt in college_positions:
        return "college", "College-scoped position: select campus and college."
    if pt in dept_positions:
        return "department", "Department-scoped position: select campus, college, and department."
    return "global", "Set the scope fields as needed."


def _build_scope_choices(campus_value, college_value):
    campus_value = (campus_value or "").strip()
    college_value = (college_value or "").strip()

    college_choices = []
    dept_choices = []

    if campus_value:
        college_choices = [c[0] for c in get_college_choices(campus_value)]
        if college_value:
            dept_choices = [d[0] for d in get_department_choices(campus_value, college_value)]

    return college_choices, dept_choices


@login_required
@admin_required
def signatory_create(request):
    if request.method == "POST":
        position_title = (request.POST.get("position_title") or Signatory.Position.DIRECTOR_EXTENSION).strip()
        campus = (request.POST.get("campus") or "").strip()
        college = (request.POST.get("college") or "").strip()
        department = (request.POST.get("department") or "").strip()

        full_name = (request.POST.get("full_name") or "").strip()
        credentials = (request.POST.get("credentials") or "").strip()

        signatory = Signatory(
            position_title=position_title,
            campus=campus,
            college=college,
            department=department,
            full_name=full_name,
            credentials=credentials,
        )

        try:
            signatory.full_clean()
            signatory.save()
            messages.success(request, f'Signatory "{signatory.display_name}" added successfully.')
            return redirect("signatories_list")
        except ValidationError as exc:
            # Validation text is written for the user, so it is safe to show.
            messages.error(request, "; ".join(exc.messages))
        except Exception:
            logger.exception("Failed to create signatory.")
            messages.error(request, "Could not save this signatory. The error has been logged.")

        college_choices, dept_choices = _build_scope_choices(campus, college)
        scope_level, scope_help = _signatory_scope_meta(position_title)

        return render(
            request,
            "dashboard/admin/signatory_form.html",
            {
                "mode": "create",
                "position_choices": Signatory.Position.choices,
                "campus_choices": [c[0] for c in get_campus_choices()],
                "college_choices": college_choices,
                "department_choices": dept_choices,
                "scope_level": scope_level,
                "scope_help": scope_help,
                "form_data": request.POST,
            },
        )

    scope_level, scope_help = _signatory_scope_meta(Signatory.Position.DIRECTOR_EXTENSION)
    return render(
        request,
        "dashboard/admin/signatory_form.html",
        {
            "mode": "create",
            "position_choices": Signatory.Position.choices,
            "campus_choices": [c[0] for c in get_campus_choices()],
            "college_choices": [],
            "department_choices": [],
            "scope_level": scope_level,
            "scope_help": scope_help,
            "form_data": {},
        },
    )


@login_required
@admin_required
def signatory_edit(request, pk):
    signatory = get_object_or_404(Signatory, pk=pk)

    if request.method == "POST":
        signatory.position_title = (request.POST.get("position_title") or signatory.position_title).strip()
        signatory.campus = (request.POST.get("campus") or "").strip()
        signatory.college = (request.POST.get("college") or "").strip()
        signatory.department = (request.POST.get("department") or "").strip()

        signatory.full_name = (request.POST.get("full_name") or "").strip()
        signatory.credentials = (request.POST.get("credentials") or "").strip()

        try:
            signatory.full_clean()
            signatory.save()
            messages.success(request, "Signatory updated successfully.")
            return redirect("signatories_list")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        except Exception:
            logger.exception("Failed to update signatory %s.", signatory.pk)
            messages.error(request, "Could not save this signatory. The error has been logged.")

    college_choices, dept_choices = _build_scope_choices(signatory.campus, signatory.college)
    scope_level, scope_help = _signatory_scope_meta(signatory.position_title)

    return render(
        request,
        "dashboard/admin/signatory_form.html",
        {
            "mode": "edit",
            "signatory": signatory,
            "position_choices": Signatory.Position.choices,
            "campus_choices": [c[0] for c in get_campus_choices()],
            "college_choices": college_choices,
            "department_choices": dept_choices,
            "scope_level": scope_level,
            "scope_help": scope_help,
            "form_data": {
                "position_title": signatory.position_title,
                "campus": signatory.campus,
                "college": signatory.college,
                "department": signatory.department,
                "full_name": signatory.full_name,
                "credentials": signatory.credentials,
            },
        },
    )


@login_required
@admin_required
@require_POST
def signatory_delete(request, pk):
    signatory = get_object_or_404(Signatory, pk=pk)
    name = signatory.display_name
    signatory.delete()
    messages.success(request, f'Signatory "{name}" deleted successfully.')
    return redirect("signatories_list")


@login_required
@admin_required
def personnel_list(request):
    personnel = Personnel.objects.all().order_by("name")
    return render(request, "dashboard/admin/personnel_list.html", {"personnel": personnel})


@login_required
@admin_required
def personnel_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        position = (request.POST.get("position") or "").strip()
        email = (request.POST.get("email") or "").strip()
        photo = request.FILES.get("photo")

        if name and position and photo:
            Personnel.objects.create(name=name, position=position, email=email, photo=photo)
            messages.success(request, f'Personnel "{name}" added successfully!')
            return redirect("personnel_list")

        messages.error(request, "Name, position, and photo are required.")

    return render(request, "dashboard/admin/personnel_form.html")


@login_required
@admin_required
def personnel_edit(request, pk):
    person = get_object_or_404(Personnel, pk=pk)

    if request.method == "POST":
        person.name = (request.POST.get("name") or "").strip()
        person.position = (request.POST.get("position") or "").strip()
        person.email = (request.POST.get("email") or "").strip()
        if request.FILES.get("photo"):
            person.photo = request.FILES["photo"]
        person.save()
        messages.success(request, f'"{person.name}" updated successfully!')
        return redirect("personnel_list")

    return render(request, "dashboard/admin/personnel_form.html", {"person": person})


@login_required
@admin_required
def personnel_delete(request, pk):
    person = get_object_or_404(Personnel, pk=pk)
    name = person.name
    person.delete()
    messages.success(request, f'"{name}" deleted successfully!')
    return redirect("personnel_list")


@login_required
@admin_required
def activities_list(request):
    activities = Activity.objects.all().annotate(first_date=Min("dates__date")).order_by("-first_date", "-id")
    return render(request, "dashboard/admin/activities_list.html", {"activities": activities})


@login_required
@admin_required
def activity_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        image = request.FILES.get("image")
        active = request.POST.get("active") == "on"
        dates = request.POST.getlist("dates[]")

        cleaned_dates = [(d or "").strip() for d in dates if (d or "").strip()]

        if title and description and cleaned_dates:
            activity = Activity.objects.create(
                title=title,
                description=description,
                image=image,
                active=active,
            )
            for d in cleaned_dates:
                ActivityDate.objects.get_or_create(activity=activity, date=d)

            messages.success(request, f'Activity "{title}" added successfully!')
            return redirect("activities_list")

        messages.error(request, "Title, description, and at least one date are required.")

    return render(request, "dashboard/admin/activity_form.html")


@login_required
@admin_required
def activity_edit(request, pk):
    activity = get_object_or_404(Activity, pk=pk)

    if request.method == "POST":
        activity.title = (request.POST.get("title") or "").strip()
        activity.description = (request.POST.get("description") or "").strip()
        activity.active = request.POST.get("active") == "on"
        if request.FILES.get("image"):
            activity.image = request.FILES["image"]
        activity.save()

        ActivityDate.objects.filter(activity=activity).delete()
        for d in request.POST.getlist("dates[]"):
            d = (d or "").strip()
            if d:
                ActivityDate.objects.get_or_create(activity=activity, date=d)

        messages.success(request, f'"{activity.title}" updated successfully!')
        return redirect("activities_list")

    return render(request, "dashboard/admin/activity_form.html", {"activity": activity})


@login_required
@admin_required
def activity_delete(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    title = activity.title
    activity.delete()
    messages.success(request, f'"{title}" deleted successfully!')
    return redirect("activities_list")


@login_required
@admin_required
def processes_list(request):
    processes = ExtensionProcess.objects.all().prefetch_related("steps")
    return render(request, "dashboard/admin/processes_list.html", {"processes": processes})


@login_required
@admin_required
def process_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "Title is required.")
            return redirect("processes_list")

        process = ExtensionProcess.objects.create(title=title)
        _sync_process_steps(process, request.POST)

        messages.success(request, f'Process "{title}" created successfully!')
        return redirect("processes_list")

    return render(
        request,
        "dashboard/admin/process_form.html",
        {"editor_id": "new"},
    )


@login_required
@admin_required
def process_edit(request, pk):
    process = get_object_or_404(ExtensionProcess, pk=pk)

    if request.method == "POST":
        process.title = (request.POST.get("title") or "").strip()
        process.order = request.POST.get("order") or 0
        process.save()

        _sync_process_steps(process, request.POST)

        messages.success(request, f'Process "{process.title}" updated successfully!')
        return redirect("processes_list")

    return render(
        request,
        "dashboard/admin/process_form.html",
        {
            "process": process,
            "editor_id": f"process-{process.pk}",
            # Drag results are saved straight away; new rows wait for the form.
            "persist_url": reverse("reorder_process_steps", args=[process.pk]),
        },
    )


@login_required
@admin_required
def process_delete(request, pk):
    process = get_object_or_404(ExtensionProcess, pk=pk)
    title = process.title
    process.delete()
    messages.success(request, f'Process "{title}" deleted successfully!')
    return redirect("processes_list")


@login_required
@admin_required
@require_POST
def reorder_process_steps(request, pk):
    """Persist a drag result: step order plus which step each one sits under.

    Accepts either ``{"step_ids": [...]}`` (flat reorder, kept for backwards
    compatibility) or ``{"steps": [{"id": 1, "parent": 2}, ...]}`` where an
    empty parent means top level. A step whose parent has not been saved yet
    is left alone -- the full form submit is what stores new rows.
    """
    process = get_object_or_404(ExtensionProcess, pk=pk)

    try:
        data = json.loads(request.body.decode("utf-8"))

        if isinstance(data.get("steps"), list):
            known = {str(step.id): step for step in process.steps.all()}
            resolved = []
            for entry in data.get("steps") or []:
                step = known.get(str(entry.get("id", "")).strip())
                if step is None:
                    continue
                parent_ref = str(entry.get("parent", "")).strip()
                if parent_ref and parent_ref not in known:
                    # The parent is a row the editor has not saved yet.
                    continue
                resolved.append((step, known.get(parent_ref) if parent_ref else None))

            for index, (step, parent) in enumerate(resolved, start=1):
                step.parent = parent
                step.order = index
                step.save(update_fields=["parent", "order"])

            return JsonResponse({"ok": True, "saved": len(resolved)})

        step_ids = data.get("step_ids", [])

        for index, step_id in enumerate(step_ids, start=1):
            ProcessStep.objects.filter(process=process, id=step_id).update(order=index)

        return JsonResponse({"ok": True})

    except (ValueError, TypeError, KeyError, AttributeError):
        logger.warning("Malformed reorder_process_steps payload.", exc_info=True)
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)
    except Exception:
        logger.exception("Failed to reorder process steps for process %s.", pk)
        return JsonResponse({"ok": False, "error": "Server error."}, status=500)


@login_required
@admin_required
def targets_list(request):
    current_year = timezone.now().year
    try:
        year = int(request.GET.get("year", current_year))
    except (TypeError, ValueError):
        year = current_year

    targets = Target.objects.filter(year=year).order_by("campus", "metric")
    years = list(Target.objects.values_list("year", flat=True).distinct().order_by("-year"))

    # Always offer the selected and current year so the dropdown never dead-ends.
    for extra in (year, current_year):
        if extra not in years:
            years.append(extra)
    years.sort(reverse=True)

    context = {
        "targets": targets,
        "current_year": year,
        "years": years,
    }
    return render(request, "dashboard/admin/targets_list.html", context)


def _target_form_context(request, *, default_year=None):
    """Shared context for the create form, including data the template needs
    for live duplicate detection."""
    # Campus choices must come from the admin-managed Campus table (with the
    # static fallback), NOT from user profiles — profiles are empty on a fresh
    # install, which used to leave this dropdown blank even when the admin had
    # already set up campuses, colleges, and departments.
    campus_choices = [value for value, _label in get_campus_choices()]
    existing_targets = [
        {
            "year": t.year,
            "campus": t.campus,
            "metric": t.metric,
            "edit_url": reverse("target_edit", args=[t.id]),
        }
        for t in Target.objects.all().only("id", "year", "campus", "metric")
    ]
    return {
        "campuses": campus_choices,
        "metric_choices": Target.METRIC_CHOICES,
        "default_year": default_year or timezone.now().year,
        "existing_targets_json": json.dumps(existing_targets),
    }


@login_required
@admin_required
def target_create(request):
    # Allow the list page (or "Save & add another") to pre-select year/campus.
    try:
        prefill_year = int(request.GET.get("year", ""))
        if prefill_year < 2000 or prefill_year > 2100:
            raise ValueError
    except (TypeError, ValueError):
        prefill_year = None

    context = _target_form_context(request, default_year=prefill_year)
    context["prefill_campus"] = (request.GET.get("campus") or "").strip()

    if request.method == "POST":
        year = request.POST.get("year")
        campus = (request.POST.get("campus") or "").strip()
        metric = (request.POST.get("metric") or "").strip()

        try:
            year = int(year)
            if year < 2000 or year > 2100:
                raise ValueError("Year must be between 2000 and 2100.")
            if not campus:
                raise ValueError("Select a campus.")
            if metric not in dict(Target.METRIC_CHOICES):
                raise ValueError("Select a valid metric.")
            values = _parse_target_numbers(request.POST)
        except (TypeError, ValueError) as exc:
            messages.error(request, str(exc) or "Enter valid target values.")
            return render(request, "dashboard/admin/target_form.html", context)

        if Target.objects.filter(year=year, campus=campus, metric=metric).exists():
            # Re-render (not redirect) so the admin keeps everything they typed.
            messages.error(
                request,
                "A target already exists for this year, campus, and metric. "
                "Edit the existing one instead.",
            )
            return render(request, "dashboard/admin/target_form.html", context)

        target = Target.objects.create(
            year=year,
            campus=campus,
            metric=metric,
            **values,
        )

        messages.success(
            request,
            f"Target saved: {target.campus} · {target.get_metric_display()} ({target.year}).",
        )

        # Admins usually add several metrics for the same campus in one
        # sitting — keep them in the form with year and campus pre-selected.
        if request.POST.get("save_and_add"):
            params = urlencode({"year": year, "campus": campus})
            return redirect(f"{reverse('target_create')}?{params}")

        return redirect(f"{reverse('targets_list')}?{urlencode({'year': year})}")

    return render(request, "dashboard/admin/target_form.html", context)


@login_required
@admin_required
def target_edit(request, pk):
    target = get_object_or_404(Target, pk=pk)

    if request.method == "POST":
        try:
            values = _parse_target_numbers(request.POST)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            for field, value in values.items():
                setattr(target, field, value)
            target.save()
            messages.success(request, "Target updated successfully!")
            return redirect(f"{reverse('targets_list')}?{urlencode({'year': target.year})}")

    return render(request, "dashboard/admin/target_form.html", {"target": target})


@login_required
@admin_required
@require_POST
def target_delete(request, pk):
    target = get_object_or_404(Target, pk=pk)
    campus = target.campus
    metric = target.get_metric_display()
    year = target.year
    target.delete()

    messages.success(request, f"Target deleted: {campus} - {metric} ({year})")
    return redirect(f"{reverse('targets_list')}?{urlencode({'year': year})}")


@login_required
@admin_required
def campuses_list(request):
    campuses = Campus.objects.prefetch_related("colleges", "departments").all().order_by("name")
    return render(request, "dashboard/admin/campuses_list.html", {"campuses": campuses})


@login_required
@admin_required
def campus_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Campus name is required.")
        elif Campus.objects.filter(name__iexact=name).exists():
            messages.error(request, "A campus with this name already exists.")
        else:
            try:
                Campus.objects.create(name=name)
                messages.success(request, f'Campus "{name}" created successfully.')
                return redirect("campuses_list")
            except Exception:
                logger.exception("Failed to create campus.")
                messages.error(request, "Could not save campus.")
    return render(request, "dashboard/admin/campus_form.html", {"mode": "create"})


@login_required
@admin_required
def campus_edit(request, pk):
    campus = get_object_or_404(Campus, pk=pk)
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Campus name is required.")
        elif Campus.objects.filter(name__iexact=name).exclude(pk=campus.pk).exists():
            messages.error(request, "A campus with this name already exists.")
        else:
            try:
                campus.name = name
                campus.save()
                messages.success(request, "Campus updated successfully.")
                return redirect("campuses_list")
            except Exception:
                logger.exception("Failed to update campus %s.", pk)
                messages.error(request, "Could not update campus.")
    return render(request, "dashboard/admin/campus_form.html", {"mode": "edit", "campus": campus})


@login_required
@admin_required
@require_POST
def campus_delete(request, pk):
    campus = get_object_or_404(Campus, pk=pk)
    name = campus.name
    try:
        campus.delete()
        messages.success(request, f'Campus "{name}" deleted successfully.')
    except Exception:
        logger.exception("Failed to delete campus %s.", pk)
        messages.error(request, "Could not delete campus (it may have related colleges or departments).")
    return redirect("campuses_list")


@login_required
@admin_required
def colleges_list(request):
    colleges = College.objects.select_related("campus").prefetch_related("departments").all().order_by("campus__name", "name")
    return render(request, "dashboard/admin/colleges_list.html", {"colleges": colleges})


@login_required
@admin_required
def college_create(request):
    campuses = Campus.objects.all().order_by("name")
    if request.method == "POST":
        campus_id = request.POST.get("campus")
        name = (request.POST.get("name") or "").strip()
        campus = get_object_or_404(Campus, pk=campus_id) if campus_id else None

        if not campus or not name:
            messages.error(request, "Campus and college name are required.")
        elif College.objects.filter(campus=campus, name__iexact=name).exists():
            messages.error(request, "A college with this name already exists in this campus.")
        else:
            try:
                College.objects.create(campus=campus, name=name)
                messages.success(request, f'College "{name}" created successfully.')
                return redirect("colleges_list")
            except Exception:
                logger.exception("Failed to create college.")
                messages.error(request, "Could not save college.")
    return render(request, "dashboard/admin/college_form.html", {"mode": "create", "campuses": campuses})


@login_required
@admin_required
def college_edit(request, pk):
    college = get_object_or_404(College, pk=pk)
    campuses = Campus.objects.all().order_by("name")
    if request.method == "POST":
        campus_id = request.POST.get("campus")
        name = (request.POST.get("name") or "").strip()
        campus = get_object_or_404(Campus, pk=campus_id) if campus_id else None

        if not campus or not name:
            messages.error(request, "Campus and college name are required.")
        elif College.objects.filter(campus=campus, name__iexact=name).exclude(pk=college.pk).exists():
            messages.error(request, "A college with this name already exists in this campus.")
        else:
            try:
                college.campus = campus
                college.name = name
                college.save()
                messages.success(request, "College updated successfully.")
                return redirect("colleges_list")
            except Exception:
                logger.exception("Failed to update college %s.", pk)
                messages.error(request, "Could not update college.")
    return render(request, "dashboard/admin/college_form.html", {"mode": "edit", "college": college, "campuses": campuses})


@login_required
@admin_required
@require_POST
def college_delete(request, pk):
    college = get_object_or_404(College, pk=pk)
    name = college.name
    try:
        college.delete()
        messages.success(request, f'College "{name}" deleted successfully.')
    except Exception:
        logger.exception("Failed to delete college %s.", pk)
        messages.error(request, "Could not delete college.")
    return redirect("colleges_list")


@login_required
@admin_required
def departments_list(request):
    departments = Department.objects.select_related("campus", "college").all().order_by("campus__name", "college__name", "name")
    return render(request, "dashboard/admin/departments_list.html", {"departments": departments})


@login_required
@admin_required
def department_create(request):
    campuses = Campus.objects.prefetch_related("colleges").all().order_by("name")
    if request.method == "POST":
        campus_id = request.POST.get("campus")
        college_id = request.POST.get("college")
        name = (request.POST.get("name") or "").strip()
        campus = get_object_or_404(Campus, pk=campus_id) if campus_id else None
        college = College.objects.filter(pk=college_id, campus=campus).first() if college_id else None

        if not campus or not name:
            messages.error(request, "Campus and department name are required.")
        elif Department.objects.filter(campus=campus, college=college, name__iexact=name).exists():
            messages.error(request, "A department with this name already exists in this college/campus.")
        else:
            try:
                dept = Department(campus=campus, college=college, name=name)
                dept.full_clean()
                dept.save()
                messages.success(request, f'Department "{name}" created successfully.')
                return redirect("departments_list")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            except Exception:
                logger.exception("Failed to create department.")
                messages.error(request, "Could not save department.")
    return render(request, "dashboard/admin/department_form.html", {"mode": "create", "campuses": campuses})


@login_required
@admin_required
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    campuses = Campus.objects.prefetch_related("colleges").all().order_by("name")
    colleges = College.objects.filter(campus=department.campus).order_by("name") if department.campus else []

    if request.method == "POST":
        campus_id = request.POST.get("campus")
        college_id = request.POST.get("college")
        name = (request.POST.get("name") or "").strip()
        campus = get_object_or_404(Campus, pk=campus_id) if campus_id else None
        college = College.objects.filter(pk=college_id, campus=campus).first() if college_id else None

        if not campus or not name:
            messages.error(request, "Campus and department name are required.")
        elif Department.objects.filter(campus=campus, college=college, name__iexact=name).exclude(pk=department.pk).exists():
            messages.error(request, "A department with this name already exists in this college/campus.")
        else:
            try:
                department.campus = campus
                department.college = college
                department.name = name
                department.full_clean()
                department.save()
                messages.success(request, "Department updated successfully.")
                return redirect("departments_list")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            except Exception:
                logger.exception("Failed to update department %s.", pk)
                messages.error(request, "Could not update department.")

    colleges = College.objects.filter(campus=department.campus).order_by("name") if department.campus else []
    return render(request, "dashboard/admin/department_form.html", {
        "mode": "edit",
        "department": department,
        "campuses": campuses,
        "colleges": colleges,
    })


@login_required
@admin_required
@require_POST
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    name = department.name
    try:
        department.delete()
        messages.success(request, f'Department "{name}" deleted successfully.')
    except Exception:
        logger.exception("Failed to delete department %s.", pk)
        messages.error(request, "Could not delete department.")
    return redirect("departments_list")
