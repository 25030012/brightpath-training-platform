import pytest
from core.models import Client, Staff, Course, CourseStaff, Learner, Enrolment


@pytest.mark.django_db
def test_enrolment_withdrawal_reenrolment_and_reports(client):
    cl = Client.objects.create(client_id="CL01", name="Northwind", seats=100)
    admin = Staff.objects.create(
        staff_id="S001",
        full_name="Admin",
        email="a@bp.example",
        role="administrator",
        password_hash="password123",
    )
    inst = Staff.objects.create(
        staff_id="S007",
        full_name="Inst",
        email="i@bp.example",
        role="instructor",
        password_hash="password123",
    )
    course = Course.objects.create(
        course_id="c1-2026-02",
        title="Course 1",
        category="Data",
        cohort="Feb 2026",
        starts_on="2026-02-01",
        ends_on="2026-06-01",
        status="published",
    )
    CourseStaff.objects.create(
        course=course, staff=inst, role="lead", assigned_on="2026-02-01"
    )
    learner = Learner.objects.create(
        learner_id="L1",
        full_name="Learner 1",
        email="l1@bp.example",
        client=cl,
        department="Sales",
        account_status="active",
        password_hash="password123",
    )

    # Admin enrols learner (calling twice while active does not duplicate active run)
    client.post("/login/", {"username": "S001", "password": "password123"})
    client.post("/admin-portal/enrol/", {"learner_id": "L1", "course_id": "c1-2026-02"})
    client.post("/admin-portal/enrol/", {"learner_id": "L1", "course_id": "c1-2026-02"})
    assert Enrolment.objects.filter(learner=learner, course=course).count() == 1
    e1 = Enrolment.objects.get(learner=learner, course=course)
    assert e1.enrolled_by == "S001"

    # Learner withdraws and then re-enrols; both runs kept
    client.post("/login/", {"username": "L1", "password": "password123"})
    client.post(f"/learner/enrolments/{e1.enrolment_id}/withdraw/")
    e1.refresh_from_db()
    assert e1.outcome == "Withdrawn" and e1.withdrawn_on != ""

    client.post(f"/learner/courses/{course.course_id}/enrol/")
    runs = Enrolment.objects.filter(learner=learner, course=course).order_by("enrolled_on", "enrolment_id")
    assert runs.count() == 2
    assert {r.enrolled_by for r in runs} == {"S001", "self"}

    # Reports and CSV downloads work and enforce RBAC
    assert client.get("/admin-portal/reports/").status_code == 403
    client.post("/login/", {"username": "S001", "password": "password123"})
    r_adm = client.get("/admin-portal/reports/")
    assert r_adm.status_code == 200 and b"Northwind" in r_adm.content
    r_csv = client.get("/admin-portal/reports/csv/")
    assert r_csv.status_code == 200 and "text/csv" in r_csv["Content-Type"]

    # Instructor report and CSV download
    client.post("/login/", {"username": "S007", "password": "password123"})
    r_inst = client.get("/instructor/reports/")
    assert r_inst.status_code == 200 and b"Learner 1" in r_inst.content
    r_inst_csv = client.get("/instructor/reports/csv/")
    assert r_inst_csv.status_code == 200 and "text/csv" in r_inst_csv["Content-Type"]


@pytest.mark.django_db
def test_end_to_end_journey(client):
    """The one journey that must work:
    An administrator creates a learner's account.
    An instructor publishes a course containing at least one quiz.
    The learner enrols, takes the quiz, and the instructor can see the result.
    """
    Client.objects.create(client_id="CL01", name="Northwind Logistics", seats=6000)
    Staff.objects.create(
        staff_id="S001",
        full_name="Imran Doyle",
        email="imran.doyle@brightpath.example",
        role="administrator",
        password_hash="password123",
    )
    Staff.objects.create(
        staff_id="S007",
        full_name="Priya Varma",
        email="priya.varma@brightpath.example",
        role="instructor",
        password_hash="password123",
    )

    # 1. Administrator signs in and creates a learner's account
    client.post("/login/", {"username": "S001", "password": "password123"})
    client.post(
        "/admin-portal/learners/create/",
        {
            "learner_id": "L99999",
            "full_name": "Zara Siddiqui",
            "email": "zara.siddiqui@northwind.example",
            "client_id": "CL01",
            "department": "Analytics",
            "password": "password123",
        },
    )

    # 2. Instructor signs in, creates a course, adds a quiz, and publishes the course
    client.post("/login/", {"username": "S007", "password": "password123"})
    client.post(
        "/instructor/courses/create/",
        {
            "course_id": "applied-analytics-2026-10",
            "title": "Applied Analytics",
            "category": "Data",
            "description": "End-to-end analytics cohort",
            "cohort": "Oct 2026",
            "starts_on": "2026-10-01",
            "ends_on": "2027-03-31",
        },
    )
    client.post(
        "/instructor/courses/applied-analytics-2026-10/assessments/create/",
        {
            "assessment_id": "Q9001",
            "title": "Analytics Readiness Quiz",
            "type": "Quiz",
            "due_on": "2026-11-01",
            "weight_pct": "100",
            "status": "published",
            "q1_prompt": "Which SQL aggregate returns the highest value?",
            "q1_opt_a": "MIN",
            "q1_opt_b": "MAX",
            "q1_opt_c": "AVG",
            "q1_opt_d": "SUM",
            "q1_correct": "B",
        },
    )
    client.post(
        "/instructor/courses/applied-analytics-2026-10/publish/",
        {"status": "published"},
    )

    # 3. Learner signs in, enrols in the published course, and takes the quiz twice (0% then 100%)
    client.post("/login/", {"username": "L99999", "password": "password123"})
    client.post("/learner/courses/applied-analytics-2026-10/enrol/")
    from core.models import QuizQuestion
    q = QuizQuestion.objects.get(assessment_id="Q9001")
    client.post("/learner/assessments/Q9001/submit/", {f"q_{q.id}": "A"})
    client.post("/learner/assessments/Q9001/submit/", {f"q_{q.id}": "B"})

    # 4. Instructor signs in and sees the learner's quiz result (avg_score=100.0 from MAX per assessment, not 50.0)
    client.post("/login/", {"username": "S007", "password": "password123"})
    edit_page = client.get("/instructor/courses/applied-analytics-2026-10/edit/")
    assert b"Zara Siddiqui" in edit_page.content
    assert b"100.0" in edit_page.content

    report_page = client.get("/instructor/reports/?course_id=applied-analytics-2026-10")
    assert b"Zara Siddiqui" in report_page.content
    assert b"50.0" not in report_page.content
    assert b"100.0" in report_page.content
