import pytest
from core.models import Client, Staff, Learner


@pytest.mark.django_db
def test_signin_roles_and_rbac(client):
    cl = Client.objects.create(client_id="CL01", name="Northwind", seats=100)
    Staff.objects.create(
        staff_id="S001",
        full_name="Admin",
        email="admin@bp.example",
        role="administrator",
        password_hash="password123",
    )
    Staff.objects.create(
        staff_id="S003",
        full_name="Left Admin",
        email="left@bp.example",
        role="administrator",
        left_on="2026-03-31",
        password_hash="password123",
    )
    Staff.objects.create(
        staff_id="S007",
        full_name="Inst",
        email="inst@bp.example",
        role="instructor",
        password_hash="password123",
    )
    Learner.objects.create(
        learner_id="1001",
        full_name="Active Learner",
        email="l1@bp.example",
        client=cl,
        department="IT",
        account_status="active",
        password_hash="password123",
    )
    Learner.objects.create(
        learner_id="1002",
        full_name="Deactivated",
        email="l2@bp.example",
        client=cl,
        department="IT",
        account_status="deactivated",
        password_hash="password123",
    )

    # Departed staff & deactivated learner refused
    r_left = client.post("/login/", {"username": "S003", "password": "password123"})
    assert r_left.status_code == 200 and b"cannot sign in" in r_left.content.lower()
    r_deact = client.post("/login/", {"username": "1002", "password": "password123"})
    assert r_deact.status_code == 200 and b"cannot sign in" in r_deact.content.lower()

    # Learner login redirects to /learner/ and gets 403 on /admin-portal/ and /instructor/
    r_learn = client.post("/login/", {"username": "1001", "password": "password123"})
    assert r_learn.status_code == 302 and r_learn.url == "/learner/"
    assert client.get("/admin-portal/").status_code == 403
    assert client.get("/instructor/").status_code == 403

    # Instructor login redirects to /instructor/ and gets 403 on /admin-portal/ and /learner/
    r_inst = client.post("/login/", {"username": "inst@bp.example", "password": "password123"})
    assert r_inst.status_code == 302 and r_inst.url == "/instructor/"
    assert client.get("/admin-portal/").status_code == 403
    assert client.get("/learner/").status_code == 403

    # Admin login redirects to /admin-portal/ and gets 403 on /instructor/ and /learner/
    r_adm = client.post("/login/", {"username": "S001", "password": "password123"})
    assert r_adm.status_code == 302 and r_adm.url == "/admin-portal/"
    assert client.get("/instructor/").status_code == 403
    assert client.get("/learner/").status_code == 403
