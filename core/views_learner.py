from datetime import date
import uuid
from django.db.models import Max
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from core.auth import require_role, get_current_learner
from core.models import Course, Assessment, Enrolment, Attempt


@require_role("learner")
def learner_home(request):
    learner = get_current_learner(request)
    my_enrolments = list(
        Enrolment.objects.filter(learner=learner)
        .select_related("course")
        .order_by("-enrolled_on", "-enrolment_id")
    )
    best_by_course = dict(
        Attempt.objects.filter(learner=learner, score__isnull=False)
        .values_list("course_id")
        .annotate(avg_best=Max("score"))
    )
    for e in my_enrolments:
        e.best_score = best_by_course.get(e.course_id)

    published_courses = Course.objects.filter(status="published").order_by(
        "title", "starts_on"
    )

    return render(
        request,
        "learner/home.html",
        {
            "learner": learner,
            "my_enrolments": my_enrolments,
            "published_courses": published_courses,
        },
    )


@require_role("learner")
def learner_enrol(request, course_id):
    if request.method != "POST":
        return redirect("/learner/")
    learner = get_current_learner(request)
    course = get_object_or_404(Course, course_id=course_id, status="published")

    active_run = Enrolment.objects.filter(
        learner=learner, course=course, withdrawn_on=""
    ).exclude(outcome__in=["Fail", "Pass", "Distinction", "Withdrawn"]).first()
    if not active_run:
        prev_runs = Enrolment.objects.filter(
            learner=learner, course__title=course.title
        ).count()
        Enrolment.objects.create(
            enrolment_id=f"E{uuid.uuid4().hex[:7].upper()}",
            learner=learner,
            course=course,
            enrolled_on=date.today().isoformat(),
            withdrawn_on="",
            outcome="In Progress",
            previous_attempts=prev_runs,
            activity_clicks=1,
            enrolled_by="self",
        )
    return redirect(f"/learner/courses/{course.course_id}/")


@require_role("learner")
def learner_withdraw(request, enrolment_id):
    if request.method != "POST":
        return redirect("/learner/")
    learner = get_current_learner(request)
    enrolment = get_object_or_404(Enrolment, enrolment_id=enrolment_id, learner=learner)
    enrolment.withdrawn_on = date.today().isoformat()
    enrolment.outcome = "Withdrawn"
    enrolment.save(update_fields=["withdrawn_on", "outcome"])
    return redirect("/learner/")


@require_role("learner")
def learner_course_detail(request, course_id):
    learner = get_current_learner(request)
    course = get_object_or_404(Course, course_id=course_id)
    if course.status != "published":
        raise Http404("Course not found or not published.")

    enrolments = list(
        Enrolment.objects.filter(learner=learner, course=course).order_by(
            "-enrolled_on", "-enrolment_id"
        )
    )
    pages = list(course.pages.all())
    assessments = list(
        course.assessments.filter(status="published")
        .prefetch_related("questions")
        .order_by("due_on", "assessment_id")
    )
    attempts = list(
        Attempt.objects.filter(learner=learner, course=course)
        .select_related("assessment")
        .order_by("-submitted_on", "-attempt_id")
    )

    # Retake rule: highest score across all attempts for each assessment
    highest_by_assessment = {}
    attempts_by_assessment = {}
    for att in attempts:
        attempts_by_assessment.setdefault(att.assessment_id, []).append(att)
        if att.score is not None:
            prev_best = highest_by_assessment.get(att.assessment_id)
            if prev_best is None or att.score > prev_best:
                highest_by_assessment[att.assessment_id] = att.score

    for a in assessments:
        a.learner_attempts = attempts_by_assessment.get(a.assessment_id, [])
        a.highest_score = highest_by_assessment.get(a.assessment_id)

    return render(
        request,
        "learner/course_detail.html",
        {
            "learner": learner,
            "course": course,
            "enrolments": enrolments,
            "pages": pages,
            "assessments": assessments,
            "attempts": attempts,
        },
    )


@require_role("learner")
def learner_submit_assessment(request, assessment_id):
    if request.method != "POST":
        return redirect("/learner/")
    learner = get_current_learner(request)
    assessment = get_object_or_404(
        Assessment, assessment_id=assessment_id, status="published"
    )
    course = assessment.course
    if course.status != "published":
        raise Http404("Course is not published.")

    # Ensure learner has an enrolment record in this course
    if not Enrolment.objects.filter(learner=learner, course=course, withdrawn_on="").exists():
        prev_runs = Enrolment.objects.filter(
            learner=learner, course__title=course.title
        ).count()
        Enrolment.objects.create(
            enrolment_id=f"E{uuid.uuid4().hex[:7].upper()}",
            learner=learner,
            course=course,
            enrolled_on=date.today().isoformat(),
            withdrawn_on="",
            outcome="In Progress",
            previous_attempts=prev_runs,
            activity_clicks=1,
            enrolled_by="self",
        )

    score = None
    graded_by = ""
    submission_text = (request.POST.get("submission_text") or "").strip()

    if assessment.type == "Quiz":
        questions = list(assessment.questions.all())
        if questions:
            correct = 0
            ans_parts = []
            for q in questions:
                chosen = (request.POST.get(f"q_{q.id}") or "").strip().upper()
                ans_parts.append(f"Q{q.id}:{chosen}")
                if chosen == q.correct_option.upper():
                    correct += 1
            score = round((correct / len(questions)) * 100.0, 2)
            submission_text = ", ".join(ans_parts)
        else:
            score = float(request.POST.get("score") or 100.0)
        graded_by = ""

    Attempt.objects.create(
        attempt_id=f"AT{uuid.uuid4().hex[:7].upper()}",
        assessment=assessment,
        learner=learner,
        course=course,
        submitted_on=date.today().isoformat(),
        score=score,
        graded_by=graded_by,
        submission_text=submission_text,
    )

    return redirect(f"/learner/courses/{course.course_id}/")
