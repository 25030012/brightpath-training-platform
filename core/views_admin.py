from datetime import date
import uuid
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from core.auth import require_role, get_current_staff, hash_password
from core.models import Client, Staff, Learner, Course, CourseStaff, Enrolment


@require_role("administrator")
def admin_home(request):
    staff = get_current_staff(request)
    q = (request.GET.get("q") or "").strip()
    dept_filter = (request.GET.get("department") or "").strip()
    client_filter = (request.GET.get("client_id") or "").strip()
    page_num = request.GET.get("page") or "1"

    if staff.client_id:
        clients = Client.objects.filter(client_id=staff.client_id)
        base_learners_qs = Learner.objects.filter(client_id=staff.client_id)
    else:
        clients = Client.objects.all().order_by("client_id")
        base_learners_qs = Learner.objects.all()

    learners_qs = base_learners_qs.select_related("client")
    if not staff.client_id and client_filter:
        learners_qs = learners_qs.filter(client_id=client_filter)
    if dept_filter:
        learners_qs = learners_qs.filter(department__iexact=dept_filter)
    if q:
        learners_qs = learners_qs.filter(
            Q(learner_id__icontains=q)
            | Q(full_name__icontains=q)
            | Q(email__icontains=q)
            | Q(department__icontains=q)
        )

    ordered_qs = learners_qs.order_by("-account_created_on", "learner_id")
    paginator = Paginator(ordered_qs, 50)
    page_obj = paginator.get_page(page_num)

    cohorts = Course.objects.prefetch_related("staff_assignments__staff").order_by("course_id")
    published_cohorts = Course.objects.filter(status="published").order_by("course_id")

    return render(
        request,
        "admin/home.html",
        {
            "staff": staff,
            "clients": clients,
            "learners": page_obj.object_list,
            "page_obj": page_obj,
            "total_learners_count": paginator.count,
            "active_learners_count": base_learners_qs.filter(account_status="active").count(),
            "deactivated_learners_count": base_learners_qs.filter(account_status="deactivated").count(),
            "cohorts": cohorts,
            "published_cohorts": published_cohorts,
            "q": q,
            "dept_filter": dept_filter,
            "client_filter": client_filter,
        },
    )


@require_role("administrator")
def create_learner(request):
    if request.method != "POST":
        return redirect("/admin-portal/")
    staff = get_current_staff(request)
    client_id = (request.POST.get("client_id") or "").strip()
    if staff.client_id and client_id != staff.client_id:
        return HttpResponseForbidden("403 Forbidden: Cannot create learners for another client.")

    client_obj = get_object_or_404(Client, client_id=client_id)
    learner_id = (request.POST.get("learner_id") or "").strip() or f"L{uuid.uuid4().hex[:6].upper()}"
    full_name = (request.POST.get("full_name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    department = (request.POST.get("department") or "").strip()
    password = (request.POST.get("password") or "password123").strip()

    Learner.objects.update_or_create(
        learner_id=learner_id,
        defaults={
            "full_name": full_name,
            "email": email,
            "client": client_obj,
            "department": department,
            "account_created_on": date.today().isoformat(),
            "created_by": staff.staff_id,
            "account_status": "active",
            "password_hash": hash_password(password),
        },
    )
    messages.success(request, f"Learner {full_name} ({learner_id}) created in {client_obj.name} · {department}.")
    return redirect(f"/admin-portal/?q={learner_id}")


@require_role("administrator")
def deactivate_learner(request, learner_id):
    if request.method != "POST":
        return redirect("/admin-portal/")
    staff = get_current_staff(request)
    learner = get_object_or_404(Learner, learner_id=learner_id)
    if staff.client_id and learner.client_id != staff.client_id:
        return HttpResponseForbidden("403 Forbidden: Cannot manage another client's learner.")
    learner.account_status = "deactivated"
    learner.save(update_fields=["account_status"])
    messages.warning(request, f"Learner {learner.full_name} ({learner.learner_id}) has been deactivated (record preserved).")
    return redirect(f"/admin-portal/?q={learner.learner_id}")


@require_role("administrator")
def admin_enrol_learner(request):
    if request.method != "POST":
        return redirect("/admin-portal/")
    staff = get_current_staff(request)
    learner_id = (request.POST.get("learner_id") or "").strip()
    course_id = (request.POST.get("course_id") or "").strip()
    learner = get_object_or_404(Learner, learner_id=learner_id)
    if staff.client_id and learner.client_id != staff.client_id:
        return HttpResponseForbidden("403 Forbidden: Cannot enrol another client's learner.")
    course = get_object_or_404(Course, course_id=course_id, status="published")

    active_run = (
        Enrolment.objects.filter(learner=learner, course=course, withdrawn_on="")
        .exclude(outcome__in=["Fail", "Pass", "Distinction", "Withdrawn"])
        .first()
    )
    if not active_run:
        prev_count = Enrolment.objects.filter(
            learner=learner, course__title=course.title
        ).count()
        enrolment_id = f"E{uuid.uuid4().hex[:7].upper()}"
        Enrolment.objects.create(
            enrolment_id=enrolment_id,
            learner=learner,
            course=course,
            enrolled_on=date.today().isoformat(),
            withdrawn_on="",
            outcome="In Progress",
            previous_attempts=prev_count,
            activity_clicks=0,
            enrolled_by=staff.staff_id,
        )
        messages.success(request, f"Enrolled {learner.full_name} ({learner.learner_id}) in {course.title} ({course.cohort}).")
    return redirect(f"/admin-portal/?q={learner.learner_id}")


@require_role("administrator")
def cohort_staff_view(request, course_id):
    course = get_object_or_404(Course, course_id=course_id)
    assignments = CourseStaff.objects.filter(course=course).select_related("staff").order_by("-assigned_on", "id")
    instructors = Staff.objects.filter(role="instructor").order_by("staff_id")
    return render(
        request,
        "admin/cohort_staff.html",
        {
            "course": course,
            "assignments": assignments,
            "instructors": instructors,
        },
    )


@require_role("administrator")
def assign_cohort_staff(request, course_id):
    if request.method != "POST":
        return redirect(f"/admin-portal/cohorts/{course_id}/staff/")
    course = get_object_or_404(Course, course_id=course_id)
    staff_id = (request.POST.get("staff_id") or "").strip()
    role = (request.POST.get("role") or "lead").strip()
    instructor = get_object_or_404(Staff, staff_id=staff_id, role="instructor")
    today_str = date.today().isoformat()

    existing = CourseStaff.objects.filter(course=course, staff=instructor, assigned_on=today_str).first()
    if existing:
        existing.unassigned_on = ""
        existing.role = role
        existing.save(update_fields=["unassigned_on", "role"])
    else:
        CourseStaff.objects.create(
            course=course,
            staff=instructor,
            role=role,
            assigned_on=today_str,
            unassigned_on="",
        )
    messages.success(request, f"Assigned {instructor.full_name} ({instructor.staff_id}) to {course.title} ({course.cohort}).")
    return redirect(f"/admin-portal/cohorts/{course_id}/staff/")


@require_role("administrator")
def unassign_cohort_staff(request, course_id, assignment_id):
    if request.method != "POST":
        return redirect(f"/admin-portal/cohorts/{course_id}/staff/")
    cs = get_object_or_404(CourseStaff, id=assignment_id, course_id=course_id)
    cs.unassigned_on = date.today().isoformat()
    cs.save(update_fields=["unassigned_on"])
    messages.info(request, f"Unassigned {cs.staff.full_name} from {course_id} (assignment history preserved).")
    return redirect(f"/admin-portal/cohorts/{course_id}/staff/")
