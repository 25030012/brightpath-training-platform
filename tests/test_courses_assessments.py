import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import (
    Client,
    Staff,
    Course,
    CourseStaff,
    CoursePage,
    Assessment,
    QuizQuestion,
    Learner,
    Enrolment,
    Attempt,
)


@pytest.mark.django_db
def test_course_draft_visibility_quiz_autograde_and_retake_highest_score(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    cl = Client.objects.create(client_id="CL01", name="C1", seats=100)
    inst1 = Staff.objects.create(
        staff_id="S007",
        full_name="Inst 1",
        email="i1@bp.example",
        role="instructor",
        password_hash="password123",
    )
    inst2 = Staff.objects.create(
        staff_id="S008",
        full_name="Inst 2",
        email="i2@bp.example",
        role="instructor",
        password_hash="password123",
    )
    learner = Learner.objects.create(
        learner_id="L100",
        full_name="Learner",
        email="l@bp.example",
        client=cl,
        department="IT",
        account_status="active",
        password_hash="password123",
    )

    # Inst 1 creates draft course
    client.post("/login/", {"username": "S007", "password": "password123"})
    client.post(
        "/instructor/courses/create/",
        {
            "course_id": "python-101-2026-10",
            "title": "Python 101",
            "category": "Data",
            "description": "Intro",
            "cohort": "Oct 2026",
            "starts_on": "2026-10-01",
            "ends_on": "2026-12-01",
        },
    )
    course = Course.objects.get(course_id="python-101-2026-10")
    assert course.status == "draft"

    # Inst 1 adds a page with text, image, and PDF
    img = SimpleUploadedFile("diagram.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
    pdf = SimpleUploadedFile("handout.pdf", b"%PDF-1.4 dummy", content_type="application/pdf")
    client.post(
        f"/instructor/courses/{course.course_id}/pages/create/",
        {
            "title": "Module 1: Variables",
            "body_text": "Welcome to Python variables.",
            "order": "1",
            "image": img,
            "pdf": pdf,
        },
    )
    page = CoursePage.objects.get(course=course)
    assert page.title == "Module 1: Variables"
    assert "diagram" in page.image_path and page.image_path.endswith(".png")
    assert "handout" in page.pdf_path and page.pdf_path.endswith(".pdf")

    # Unassigned instructor S008 gets 403 trying to edit or publish python-101-2026-10
    client.post("/login/", {"username": "S008", "password": "password123"})
    assert client.post(f"/instructor/courses/{course.course_id}/publish/").status_code == 403
    assert client.get(f"/instructor/courses/{course.course_id}/edit/").status_code == 403

    # Learner cannot see draft course
    client.post("/login/", {"username": "L100", "password": "password123"})
    assert b"Python 101" not in client.get("/learner/").content
    assert client.get(f"/learner/courses/{course.course_id}/").status_code == 404

    # Inst 1 publishes course & adds a 1-question quiz and a hand-marked assignment
    client.post("/login/", {"username": "S007", "password": "password123"})
    client.post(f"/instructor/courses/{course.course_id}/publish/")
    client.post(
        f"/instructor/courses/{course.course_id}/assessments/create/",
        {
            "title": "Quiz 1",
            "type": "Quiz",
            "due_on": "2026-11-01",
            "weight_pct": 50,
            "status": "published",
            "q1_prompt": "What is 2+2?",
            "q1_opt_a": "3",
            "q1_opt_b": "4",
            "q1_opt_c": "5",
            "q1_opt_d": "6",
            "q1_correct": "B",
        },
    )
    client.post(
        f"/instructor/courses/{course.course_id}/assessments/create/",
        {
            "title": "Assignment 1",
            "type": "Assignment",
            "due_on": "2026-11-15",
            "weight_pct": 50,
            "status": "published",
        },
    )
    quiz = Assessment.objects.get(course=course, title="Quiz 1")
    asgn = Assessment.objects.get(course=course, title="Assignment 1")
    q = quiz.questions.first()

    # Learner enrols, takes quiz twice (first wrong = 0, second right = 100); both attempts kept, highest score = 100
    client.post("/login/", {"username": "L100", "password": "password123"})
    client.post(f"/learner/courses/{course.course_id}/enrol/")
    client.post(f"/learner/assessments/{quiz.assessment_id}/submit/", {f"q_{q.id}": "A"})
    client.post(f"/learner/assessments/{quiz.assessment_id}/submit/", {f"q_{q.id}": "B"})
    attempts = Attempt.objects.filter(assessment=quiz, learner=learner).order_by("attempt_id")
    assert attempts.count() == 2
    assert sorted([a.score for a in attempts]) == [0.0, 100.0]

    # Learner submits assignment; instructor grades it by hand
    client.post(
        f"/learner/assessments/{asgn.assessment_id}/submit/",
        {"submission_text": "My assignment work"},
    )
    asgn_attempt = Attempt.objects.get(assessment=asgn, learner=learner)
    assert asgn_attempt.score is None

    client.post("/login/", {"username": "S007", "password": "password123"})
    client.post(
        f"/instructor/attempts/{asgn_attempt.attempt_id}/grade/",
        {"score": "88"},
    )
    asgn_attempt.refresh_from_db()
    assert asgn_attempt.score == 88.0
    assert asgn_attempt.graded_by == "S007"
