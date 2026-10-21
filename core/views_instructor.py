from datetime import date
import os
import uuid
from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.db.models import Max
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from core.auth import require_role, get_current_staff
from core.models import (
    Course,
    CourseStaff,
    CoursePage,
    Assessment,
    QuizQuestion,
    Enrolment,
    Attempt,
)

ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
ALLOWED_PDF_EXTS = {".pdf"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _is_assigned(staff, course: Course) -> bool:
    return CourseStaff.objects.filter(
        course=course, staff=staff, unassigned_on=""
    ).exists()


def recalculate_enrolment_outcome(learner, course: Course):
    """Update active Enrolment outcome when all published assessments in a cohort have a graded attempt."""
    published_assessments = list(course.assessments.filter(status="published"))
    if not published_assessments:
        return
    best_scores = dict(
        Attempt.objects.filter(
            learner=learner, course=course, score__isnull=False
        )
        .values_list("assessment_id")
        .annotate(best=Max("score"))
    )
    if all(a.assessment_id in best_scores for a in published_assessments):
        total_weight = sum(a.weight_pct for a in published_assessments) or 0.0
        if total_weight > 0:
            weighted = sum(
                best_scores[a.assessment_id] * a.weight_pct
                for a in published_assessments
            ) / total_weight
        else:
            weighted = sum(best_scores.values()) / len(best_scores)
        new_outcome = (
            "Distinction"
            if weighted >= 75.0
            else ("Pass" if weighted >= 40.0 else "Fail")
        )
        Enrolment.objects.filter(
            learner=learner, course=course, withdrawn_on=""
        ).update(outcome=new_outcome)


@require_role("instructor")
def instructor_home(request):
    staff = get_current_staff(request)
    assigned_course_ids = list(
        CourseStaff.objects.filter(staff=staff, unassigned_on="").values_list(
            "course_id", flat=True
        )
    )
    my_courses = (
        Course.objects.filter(course_id__in=assigned_course_ids)
        .prefetch_related("pages", "assessments")
        .order_by("course_id")
    )
    other_courses = Course.objects.exclude(course_id__in=assigned_course_ids).order_by(
        "course_id"
    )
    ungraded_attempts = (
        Attempt.objects.filter(course_id__in=assigned_course_ids, score__isnull=True)
        .select_related("learner", "assessment", "course")
        .order_by("-submitted_on", "-attempt_id")[:50]
    )
    recent_attempts = (
        Attempt.objects.filter(course_id__in=assigned_course_ids)
        .select_related("learner", "assessment", "course")
        .order_by("-submitted_on", "-attempt_id")[:30]
    )

    return render(
        request,
        "instructor/home.html",
        {
            "staff": staff,
            "my_courses": my_courses,
            "other_courses": other_courses,
            "ungraded_attempts": ungraded_attempts,
            "recent_attempts": recent_attempts,
        },
    )


@require_role("instructor")
def create_course(request):
    if request.method != "POST":
        return redirect("/instructor/")
    staff = get_current_staff(request)
    title = (request.POST.get("title") or "").strip()
    cohort = (request.POST.get("cohort") or "Oct 2026").strip()
    course_id = (request.POST.get("course_id") or "").strip()
    if not course_id:
        slug = "-".join(title.lower().split())[:40]
        course_id = f"{slug}-{uuid.uuid4().hex[:4]}"

    course, _ = Course.objects.update_or_create(
        course_id=course_id,
        defaults={
            "title": title,
            "category": (request.POST.get("category") or "General").strip(),
            "description": (request.POST.get("description") or "").strip(),
            "cohort": cohort,
            "starts_on": (request.POST.get("starts_on") or date.today().isoformat()).strip(),
            "ends_on": (request.POST.get("ends_on") or "2027-06-30").strip(),
            "length_days": int(request.POST.get("length_days") or 180),
            "status": "draft",
        },
    )
    CourseStaff.objects.get_or_create(
        course=course,
        staff=staff,
        assigned_on=date.today().isoformat(),
        defaults={"role": "lead", "unassigned_on": ""},
    )
    messages.success(request, f"Created draft course '{course.title}' ({course.course_id}).")
    return redirect(f"/instructor/courses/{course.course_id}/edit/")


@require_role("instructor")
def course_edit_view(request, course_id):
    staff = get_current_staff(request)
    course = get_object_or_404(Course, course_id=course_id)
    if not _is_assigned(staff, course):
        return HttpResponseForbidden(
            "403 Forbidden: Instructors can edit only cohorts they are assigned to."
        )
    pages = course.pages.all()
    assessments = course.assessments.prefetch_related("questions").all()
    attempts = (
        Attempt.objects.filter(course=course)
        .select_related("learner", "assessment")
        .order_by("-submitted_on", "-attempt_id")[:50]
    )
    return render(
        request,
        "instructor/course_edit.html",
        {
            "staff": staff,
            "course": course,
            "pages": pages,
            "assessments": assessments,
            "attempts": attempts,
        },
    )


@require_role("instructor")
def publish_course(request, course_id):
    if request.method != "POST":
        return redirect(f"/instructor/courses/{course_id}/edit/")
    staff = get_current_staff(request)
    course = get_object_or_404(Course, course_id=course_id)
    if not _is_assigned(staff, course):
        return HttpResponseForbidden(
            "403 Forbidden: Instructors can edit only cohorts they are assigned to."
        )
    new_status = (request.POST.get("status") or "published").strip()
    course.status = new_status if new_status in ("draft", "published") else "published"
    course.save(update_fields=["status"])
    messages.success(request, f"Course '{course.title}' is now {course.status.upper()}.")
    return redirect(f"/instructor/courses/{course.course_id}/edit/")


@require_role("instructor")
def create_course_page(request, course_id):
    if request.method != "POST":
        return redirect(f"/instructor/courses/{course_id}/edit/")
    staff = get_current_staff(request)
    course = get_object_or_404(Course, course_id=course_id)
    if not _is_assigned(staff, course):
        return HttpResponseForbidden(
            "403 Forbidden: Instructors can edit only cohorts they are assigned to."
        )

    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    fs = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)

    image_url = ""
    if "image" in request.FILES:
        img_file = request.FILES["image"]
        ext = os.path.splitext(img_file.name)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTS or img_file.size > MAX_UPLOAD_BYTES:
            return HttpResponseBadRequest("Invalid image file type or file exceeds 10 MB.")
        saved_img = fs.save(f"pages/{course.course_id}_{os.path.basename(img_file.name)}", img_file)
        image_url = fs.url(saved_img)

    pdf_url = ""
    if "pdf" in request.FILES:
        pdf_file = request.FILES["pdf"]
        ext = os.path.splitext(pdf_file.name)[1].lower()
        if ext not in ALLOWED_PDF_EXTS or pdf_file.size > MAX_UPLOAD_BYTES:
            return HttpResponseBadRequest("Invalid PDF file type or file exceeds 10 MB.")
        saved_pdf = fs.save(f"pages/{course.course_id}_{os.path.basename(pdf_file.name)}", pdf_file)
        pdf_url = fs.url(saved_pdf)

    order_val = int(request.POST.get("order") or (course.pages.count() + 1))
    page_title = (request.POST.get("title") or "Untitled Page").strip()
    CoursePage.objects.create(
        course=course,
        order=order_val,
        title=page_title,
        body_text=(request.POST.get("body_text") or "").strip(),
        image_path=image_url,
        pdf_path=pdf_url,
    )
    messages.success(request, f"Added page '{page_title}' to {course.title}.")
    return redirect(f"/instructor/courses/{course.course_id}/edit/")


@require_role("instructor")
def create_assessment(request, course_id):
    if request.method != "POST":
        return redirect(f"/instructor/courses/{course_id}/edit/")
    staff = get_current_staff(request)
    course = get_object_or_404(Course, course_id=course_id)
    if not _is_assigned(staff, course):
        return HttpResponseForbidden(
            "403 Forbidden: Instructors can edit only cohorts they are assigned to."
        )

    assessment_id = (
        request.POST.get("assessment_id") or f"AS{uuid.uuid4().hex[:6].upper()}"
    ).strip()
    atype = (request.POST.get("type") or "Quiz").strip()
    status = (request.POST.get("status") or "published").strip()
    published_on = date.today().isoformat() if status == "published" else ""

    assessment, _ = Assessment.objects.update_or_create(
        assessment_id=assessment_id,
        defaults={
            "course": course,
            "type": atype,
            "title": (request.POST.get("title") or f"{atype} — {course.title}").strip(),
            "due_on": (request.POST.get("due_on") or date.today().isoformat()).strip(),
            "weight_pct": float(request.POST.get("weight_pct") or 20.0),
            "author": staff,
            "status": status,
            "published_on": published_on,
        },
    )

    if atype == "Quiz":
        for idx in (1, 2, 3):
            prompt = (request.POST.get(f"q{idx}_prompt") or "").strip()
            if prompt:
                QuizQuestion.objects.create(
                    assessment=assessment,
                    prompt=prompt,
                    option_a=(request.POST.get(f"q{idx}_opt_a") or "Option A").strip(),
                    option_b=(request.POST.get(f"q{idx}_opt_b") or "Option B").strip(),
                    option_c=(request.POST.get(f"q{idx}_opt_c") or "Option C").strip(),
                    option_d=(request.POST.get(f"q{idx}_opt_d") or "Option D").strip(),
                    correct_option=(
                        request.POST.get(f"q{idx}_correct") or "A"
                    ).strip().upper(),
                )

    messages.success(request, f"Created {atype} '{assessment.title}' ({assessment.assessment_id}).")
    return redirect(f"/instructor/courses/{course.course_id}/edit/")


@require_role("instructor")
def add_quiz_question(request, assessment_id):
    if request.method != "POST":
        return redirect("/instructor/")
    staff = get_current_staff(request)
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id)
    if not _is_assigned(staff, assessment.course):
        return HttpResponseForbidden("403 Forbidden: Not assigned to this cohort.")

    prompt = (request.POST.get("prompt") or "").strip()
    if prompt:
        QuizQuestion.objects.create(
            assessment=assessment,
            prompt=prompt,
            option_a=(request.POST.get("option_a") or "Option A").strip(),
            option_b=(request.POST.get("option_b") or "Option B").strip(),
            option_c=(request.POST.get("option_c") or "Option C").strip(),
            option_d=(request.POST.get("option_d") or "Option D").strip(),
            correct_option=(request.POST.get("correct_option") or "A").strip().upper(),
        )
        messages.success(request, f"Added question to '{assessment.title}'.")
    return redirect(f"/instructor/courses/{assessment.course_id}/edit/")


@require_role("instructor")
def publish_assessment(request, assessment_id):
    if request.method != "POST":
        return redirect("/instructor/")
    staff = get_current_staff(request)
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id)
    if not _is_assigned(staff, assessment.course):
        return HttpResponseForbidden("403 Forbidden: Not assigned to this cohort.")
    assessment.status = "published"
    assessment.published_on = date.today().isoformat()
    assessment.save(update_fields=["status", "published_on"])
    messages.success(request, f"Published assessment '{assessment.title}'.")
    return redirect(f"/instructor/courses/{assessment.course_id}/edit/")


@require_role("instructor")
def grade_attempt(request, attempt_id):
    if request.method != "POST":
        return redirect("/instructor/")
    staff = get_current_staff(request)
    attempt = get_object_or_404(Attempt, attempt_id=attempt_id)
    if not _is_assigned(staff, attempt.course):
        return HttpResponseForbidden("403 Forbidden: Not assigned to this cohort.")
    score_val = float(request.POST.get("score") or 0.0)
    attempt.score = max(0.0, min(100.0, score_val))
    attempt.graded_by = staff.staff_id
    attempt.save(update_fields=["score", "graded_by"])
    recalculate_enrolment_outcome(attempt.learner, attempt.course)
    messages.success(request, f"Graded attempt {attempt.attempt_id} with score {attempt.score}%.")
    return redirect(f"/instructor/courses/{attempt.course_id}/edit/")
