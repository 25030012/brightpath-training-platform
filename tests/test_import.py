import pytest
from core.management.commands.import_seed import run_import
from core.models import Client, Staff, Course, Learner, Enrolment, Attempt


@pytest.mark.django_db
def test_import_seed_and_idempotency():
    stats1 = run_import("data")
    assert stats1["clients"]["inserted"] == 7
    assert stats1["staff"]["inserted"] == 19
    assert stats1["courses"]["inserted"] == 22
    assert stats1["learners"]["rejected"] == 2338
    assert stats1["attempts"]["rejected"] > 0
    count_learners = Learner.objects.count()
    count_attempts = Attempt.objects.count()
    # Second run must not duplicate rows
    stats2 = run_import("data")
    assert Learner.objects.count() == count_learners
    assert Attempt.objects.count() == count_attempts
