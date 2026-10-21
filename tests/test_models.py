import pytest
from core.models import Client, Staff, Course, Learner


@pytest.mark.django_db
def test_create_core_entities():
    c = Client.objects.create(client_id="CL01", name="Northwind", seats=100)
    s = Staff.objects.create(
        staff_id="S001",
        full_name="Imran Doyle",
        email="imran@brightpath.example",
        role="administrator",
    )
    l = Learner.objects.create(
        learner_id="L001",
        full_name="Arjun",
        email="arjun@example.com",
        client=c,
        department="Eng",
        account_status="active",
    )
    assert l.client.client_id == "CL01"
    assert s.is_active_staff is True
