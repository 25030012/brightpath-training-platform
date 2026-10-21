import pytest
from core.models import Client, Staff, Learner, Course, CourseStaff


@pytest.mark.django_db
def test_admin_create_deactivate_client_scoping_and_cohort_staff(client):
    cl1 = Client.objects.create(client_id="CL01", name="C1", seats=100)
    cl2 = Client.objects.create(client_id="CL02", name="C2", seats=100)
    Staff.objects.create(
        staff_id="S001",
        full_name="Global Admin",
        email="s1@bp.example",
        role="administrator",
        password_hash="password123",
    )
    Staff.objects.create(
        staff_id="S004",
        full_name="Client Admin",
        email="s4@bp.example",
        role="administrator",
        client=cl2,
        password_hash="password123",
    )
    inst = Staff.objects.create(
        staff_id="S007",
        full_name="Priya Varma",
        email="s7@bp.example",
        role="instructor",
        password_hash="password123",
    )
    course = Course.objects.create(
        course_id="data-2026-10",
        title="Data Analysis",
        cohort="Oct 2026",
        status="published",
    )
    Learner.objects.create(
        learner_id="L1",
        full_name="CL1 Learner",
        email="l1@c1.example",
        client=cl1,
        department="Ops",
        account_status="active",
    )

    # Client-scoped admin S004 cannot see CL1 Learner
    client.post("/login/", {"username": "S004", "password": "password123"})
    resp = client.get("/admin-portal/")
    assert b"CL1 Learner" not in resp.content

    # Client-scoped admin S004 blocked from creating learner in CL01
    r_cross = client.post(
        "/admin-portal/learners/create/",
        {
            "full_name": "Cross Client",
            "email": "cross@c1.example",
            "client_id": "CL01",
            "department": "Ops",
            "password": "password123",
        },
    )
    assert r_cross.status_code == 403

    # Create learner under CL02 and then deactivate
    client.post(
        "/admin-portal/learners/create/",
        {
            "full_name": "New Learner",
            "email": "new@c2.example",
            "client_id": "CL02",
            "department": "Finance",
            "password": "password123",
        },
    )
    nl = Learner.objects.get(email="new@c2.example")
    assert nl.account_status == "active"
    assert nl.created_by == "S004"

    client.post(f"/admin-portal/learners/{nl.learner_id}/deactivate/")
    nl.refresh_from_db()
    assert nl.account_status == "deactivated"

    # Assign instructor to cohort and then unassign; history remains visible
    client.post(
        f"/admin-portal/cohorts/{course.course_id}/staff/assign/",
        {"staff_id": "S007", "role": "lead"},
    )
    cs = CourseStaff.objects.get(course=course, staff=inst)
    assert cs.unassigned_on == ""

    client.post(f"/admin-portal/cohorts/{course.course_id}/staff/{cs.id}/unassign/")
    cs.refresh_from_db()
    assert cs.unassigned_on != ""

    hist_resp = client.get(f"/admin-portal/cohorts/{course.course_id}/staff/")
    assert hist_resp.status_code == 200
    assert b"Priya Varma" in hist_resp.content
    assert cs.unassigned_on.encode() in hist_resp.content
