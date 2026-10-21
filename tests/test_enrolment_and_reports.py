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

    # Admin enrols learner
    client.post("/login/", {"username": "S001", "password": "password123"})
    client.post("/admin-portal/enrol/", {"learner_id": "L1", "course_id": "c1-2026-02"})
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
