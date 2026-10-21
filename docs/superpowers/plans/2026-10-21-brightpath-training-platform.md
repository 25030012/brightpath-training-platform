# BrightPath Training Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the BrightPath corporate training platform replacing 8 spreadsheets with a role-based web application (Import, Sign-in/RBAC, People, Courses, Quizzes/Assignments, Enrolment, and sub-2-second Reports).

**Architecture:** Single Django 5.x project (`brightpath`) with one cohesive `core` app backed by PostgreSQL, server-rendered templates with Tailwind CSS + HTMX, and bulk SQL operations (`bulk_create(ignore_conflicts=True)` and SQL `GROUP BY` aggregations) so importing 235k+ rows and rendering reports over 173k+ attempts run in under two seconds.

**Tech Stack:** Python 3, Django 5.x, PostgreSQL (`psycopg[binary]`), HTMX, Tailwind CSS, `pytest` + `pytest-django`.

**Spec:** `docs/superpowers/specs/2026-10-21-brightpath-training-platform-design.md`

## Global Constraints

- Must start with one command (`./start.sh`) from a fresh clone, documented in `README.md`, and be reachable over HTTP (`http://127.0.0.1:8000`).
- Ponytail discipline: smallest complete change, no unrequested features, reuse Django built-ins (`models`, `forms`, `HttpResponse`, SQL aggregations).
- Nothing is ever deleted (learners are deactivated, staff unassignments record `unassigned_on`, withdrawals record `withdrawn_on`, every assessment attempt is kept).
- Direct URL access to another role's views must return HTTP `403 Forbidden`.
- Both report pages must render in `< 2.0 seconds` with all imported attempts loaded and support CSV download.

## Review Focus

- Deactivated learners (`account_status='deactivated'`) and departed staff (`left_on` non-empty) attempting login must be rejected even with a valid password.
- Client-scoped administrators (`staff.client_id` set, e.g. `S004` for `CL02`) attempting to view, create, or enrol learners for another client (`CL01`) must be blocked (`403` or filtered queryset).
- Instructors attempting to edit a cohort or add an assessment to a cohort where they are not actively assigned (`unassigned_on` is empty) must receive `403 Forbidden`.
- Retaking a quiz or assignment must create a new `Attempt` row without overwriting earlier rows, and report/progress calculations must use `MAX(score)` per `(learner_id, assessment_id)`.
- Re-running `python manage.py import_seed` must produce 0 duplicates and identical row counts.

---

### Task 1: Project Scaffolding, PostgreSQL Startup & Core Schema

**Files:**
- Create: `requirements.txt`
- Create: `start.sh`
- Create: `README.md`
- Create: `manage.py`
- Create: `brightpath/__init__.py`
- Create: `brightpath/settings.py`
- Create: `brightpath/urls.py`
- Create: `core/__init__.py`
- Create: `core/models.py`
- Create: `pytest.ini`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Client`, `Staff`, `Course`, `CourseStaff`, `CoursePage`, `Assessment`, `QuizQuestion`, `Learner`, `Enrolment`, `Attempt` models in `core.models`.

- [ ] **Step 1: Write the failing model & schema test in `tests/test_models.py`**
```python
import pytest
from core.models import Client, Staff, Course, Learner

@pytest.mark.django_db
def test_create_core_entities():
    c = Client.objects.create(client_id="CL01", name="Northwind", seats=100)
    s = Staff.objects.create(staff_id="S001", full_name="Imran Doyle", email="imran@brightpath.example", role="administrator")
    l = Learner.objects.create(learner_id="L001", full_name="Arjun", email="arjun@example.com", client=c, department="Eng", account_status="active")
    assert l.client.client_id == "CL01"
    assert s.is_active_staff is True
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: FAIL (project/models not created yet)

- [ ] **Step 3: Create `requirements.txt`, local PostgreSQL bootstrap in `start.sh`, `brightpath/settings.py`, and `core/models.py` with indexes on foreign keys (`learner_id`, `course_id`, `assessment_id`, `client_id`) and migrations**

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add requirements.txt start.sh README.md manage.py pytest.ini brightpath core tests/test_models.py
git commit -m "feat: scaffold Django + PostgreSQL project and core models"
```

---

### Task 2: Module 1 — Idempotent Seed Importer (`import_seed`)

**Files:**
- Create: `core/management/commands/import_seed.py`
- Test: `tests/test_import.py`

**Interfaces:**
- Consumes: `core.models.*`
- Produces: `python manage.py import_seed --data-dir data` management command and `run_import(data_dir: str) -> dict` helper returning `{table: {"inserted": int, "rejected": int, "reasons": dict}}`.

- [ ] **Step 1: Write the failing importer test in `tests/test_import.py`**
```python
import pytest
from core.management.commands.import_seed import run_import
from core.models import Client, Staff, Course, Learner, Enrolment, Attempt

@pytest.mark.django_db
def test_import_seed_and_idempotency():
    stats1 = run_import("data")
    assert stats1["clients"]["inserted"] == 7
    assert stats1["staff"]["inserted"] == 19
    assert stats1["courses"]["inserted"] == 22
    assert stats1["learners"]["rejected"] == 2337
    assert stats1["attempts"]["rejected"] > 0
    count_learners = Learner.objects.count()
    count_attempts = Attempt.objects.count()
    # Second run must not duplicate rows
    stats2 = run_import("data")
    assert Learner.objects.count() == count_learners
    assert Attempt.objects.count() == count_attempts
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.management.commands.import_seed'`

- [ ] **Step 3: Implement `core/management/commands/import_seed.py` using `bulk_create(update_conflicts=True)` / `ignore_conflicts=True` in batches of 5,000 and printing accepted/rejected counts and reasons**

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add core/management tests/test_import.py
git commit -m "feat(import): add idempotent CSV seed importer with rejection reporting"
```

---

### Task 3: Module 2 — Sign-in, Session Auth, and Server-Side RBAC

**Files:**
- Create: `core/auth.py`
- Create: `core/views_auth.py`
- Create: `core/templates/base.html`
- Create: `core/templates/login.html`
- Modify: `brightpath/urls.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `Staff`, `Learner` models.
- Produces: session keys `user_role` (`administrator`, `instructor`, `learner`), `user_id` (`staff_id` or `learner_id`), `require_role(*roles)` decorator returning HTTP 403 on role mismatch, and `/login/`, `/logout/` views.

- [ ] **Step 1: Write the failing auth and RBAC tests in `tests/test_auth.py`**
```python
import pytest
from core.models import Client, Staff, Learner

@pytest.mark.django_db
def test_signin_roles_and_rbac(client):
    cl = Client.objects.create(client_id="CL01", name="Northwind", seats=100)
    Staff.objects.create(staff_id="S001", full_name="Admin", email="admin@bp.example", role="administrator", password_hash="password123")
    Staff.objects.create(staff_id="S003", full_name="Left Admin", email="left@bp.example", role="administrator", left_on="2026-03-31", password_hash="password123")
    Staff.objects.create(staff_id="S007", full_name="Inst", email="inst@bp.example", role="instructor", password_hash="password123")
    Learner.objects.create(learner_id="1001", full_name="Active Learner", email="l1@bp.example", client=cl, department="IT", account_status="active", password_hash="password123")
    Learner.objects.create(learner_id="1002", full_name="Deactivated", email="l2@bp.example", client=cl, department="IT", account_status="deactivated", password_hash="password123")

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
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_auth.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `core/auth.py`, `core/views_auth.py`, `base.html`, and `login.html`**

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add core/auth.py core/views_auth.py core/templates brightpath/urls.py tests/test_auth.py
git commit -m "feat(auth): implement role sign-in, deactivated/left blocks, and 403 RBAC"
```

---

### Task 4: Module 3 — People Management (Administrators)

**Files:**
- Create: `core/views_admin.py`
- Create: `core/templates/admin/home.html`
- Create: `core/templates/admin/cohort_staff.html`
- Modify: `brightpath/urls.py`
- Test: `tests/test_people.py`

**Interfaces:**
- Consumes: `require_role("administrator")`, `Client`, `Staff`, `Learner`, `Course`, `CourseStaff`.
- Produces: `/admin-portal/` (learner list scoped by `staff.client_id`, create learner form, deactivate learner endpoint, enrol learner endpoint) and `/admin-portal/cohorts/<course_id>/staff/` (assign/unassign instructor with full history).

- [ ] **Step 1: Write the failing people management tests in `tests/test_people.py`**
```python
import pytest
from core.models import Client, Staff, Learner, Course, CourseStaff

@pytest.mark.django_db
def test_admin_create_deactivate_and_client_scoping(client):
    cl1 = Client.objects.create(client_id="CL01", name="C1", seats=100)
    cl2 = Client.objects.create(client_id="CL02", name="C2", seats=100)
    Staff.objects.create(staff_id="S004", full_name="Client Admin", email="s4@bp.example", role="administrator", client=cl2, password_hash="password123")
    Learner.objects.create(learner_id="L1", full_name="CL1 Learner", email="l1@c1.example", client=cl1, department="Ops", account_status="active")

    client.post("/login/", {"username": "S004", "password": "password123"})
    resp = client.get("/admin-portal/")
    assert b"CL1 Learner" not in resp.content

    # Create learner under CL02 and then deactivate
    client.post("/admin-portal/learners/create/", {
        "full_name": "New Learner",
        "email": "new@c2.example",
        "client_id": "CL02",
        "department": "Finance",
        "password": "password123",
    })
    nl = Learner.objects.get(email="new@c2.example")
    assert nl.account_status == "active"
    client.post(f"/admin-portal/learners/{nl.learner_id}/deactivate/")
    nl.refresh_from_db()
    assert nl.account_status == "deactivated"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_people.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `core/views_admin.py` and templates (`admin/home.html`, `admin/cohort_staff.html`)**

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_people.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add core/views_admin.py core/templates/admin brightpath/urls.py tests/test_people.py
git commit -m "feat(people): add learner creation, deactivation, client scoping, and cohort staff history"
```

---

### Task 5: Module 4 & Module 5 — Courses, Pages, Quizzes & Assignments (Instructors & Learners)

**Files:**
- Create: `core/views_instructor.py`
- Create: `core/views_learner.py`
- Create: `core/templates/instructor/home.html`
- Create: `core/templates/instructor/course_edit.html`
- Create: `core/templates/instructor/grade_attempts.html`
- Create: `core/templates/learner/home.html`
- Create: `core/templates/learner/course_detail.html`
- Create: `core/templates/learner/take_assessment.html`
- Modify: `brightpath/urls.py`
- Test: `tests/test_courses_assessments.py`

**Interfaces:**
- Consumes: `Course`, `CoursePage`, `CourseStaff`, `Assessment`, `QuizQuestion`, `Attempt`, `Enrolment`.
- Produces: Instructor course creation (draft $\rightarrow$ publish), page creation with text/image/PDF upload, assigned-cohort edit check (403 if not assigned), MCQ quiz builder + auto-grading on learner submit, hand-graded assignment submission + instructor grading, and highest-score retake tracking.

- [ ] **Step 1: Write the failing course & assessment tests in `tests/test_courses_assessments.py`**
```python
import pytest
from core.models import Client, Staff, Course, CourseStaff, Assessment, QuizQuestion, Learner, Enrolment, Attempt

@pytest.mark.django_db
def test_course_draft_visibility_quiz_autograde_and_retake_highest_score(client):
    cl = Client.objects.create(client_id="CL01", name="C1", seats=100)
    inst1 = Staff.objects.create(staff_id="S007", full_name="Inst 1", email="i1@bp.example", role="instructor", password_hash="password123")
    inst2 = Staff.objects.create(staff_id="S008", full_name="Inst 2", email="i2@bp.example", role="instructor", password_hash="password123")
    learner = Learner.objects.create(learner_id="L100", full_name="Learner", email="l@bp.example", client=cl, department="IT", account_status="active", password_hash="password123")

    # Inst 1 creates draft course
    client.post("/login/", {"username": "S007", "password": "password123"})
    client.post("/instructor/courses/create/", {
        "course_id": "python-101-2026-10",
        "title": "Python 101",
        "category": "Data",
        "description": "Intro",
        "cohort": "Oct 2026",
        "starts_on": "2026-10-01",
        "ends_on": "2026-12-01",
    })
    course = Course.objects.get(course_id="python-101-2026-10")
    assert course.status == "draft"

    # Unassigned instructor S008 gets 403 trying to edit python-101-2026-10
    client.post("/login/", {"username": "S008", "password": "password123"})
    assert client.post(f"/instructor/courses/{course.course_id}/publish/").status_code == 403

    # Learner cannot see draft course
    client.post("/login/", {"username": "L100", "password": "password123"})
    assert b"Python 101" not in client.get("/learner/").content

    # Inst 1 publishes course & adds a 1-question quiz
    client.post("/login/", {"username": "S007", "password": "password123"})
    client.post(f"/instructor/courses/{course.course_id}/publish/")
    client.post(f"/instructor/courses/{course.course_id}/assessments/create/", {
        "title": "Quiz 1",
        "type": "Quiz",
        "due_on": "2026-11-01",
        "weight_pct": 100,
        "status": "published",
        "q1_prompt": "What is 2+2?",
        "q1_opt_a": "3",
        "q1_opt_b": "4",
        "q1_opt_c": "5",
        "q1_opt_d": "6",
        "q1_correct": "B",
    })
    quiz = Assessment.objects.get(course=course, title="Quiz 1")
    q = quiz.questions.first()

    # Learner enrols, takes quiz twice (first wrong = 0, second right = 100); both attempts kept, highest score = 100
    client.post("/login/", {"username": "L100", "password": "password123"})
    client.post(f"/learner/courses/{course.course_id}/enrol/")
    client.post(f"/learner/assessments/{quiz.assessment_id}/submit/", {f"q_{q.id}": "A"})
    client.post(f"/learner/assessments/{quiz.assessment_id}/submit/", {f"q_{q.id}": "B"})
    attempts = Attempt.objects.filter(assessment=quiz, learner=learner).order_by("id")
    assert attempts.count() == 2
    assert [a.score for a in attempts] == [0.0, 100.0]
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_courses_assessments.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `core/views_instructor.py`, `core/views_learner.py`, and templates for courses, pages, quizzes, and assignments**

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_courses_assessments.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add core/views_instructor.py core/views_learner.py core/templates/instructor core/templates/learner brightpath/urls.py tests/test_courses_assessments.py
git commit -m "feat(courses,assessments): add course pages, draft/publish, MCQ auto-grading, hand grading, and retakes"
```

---

### Task 6: Module 6 & Module 7 — Enrolments, Withdrawals, Retake Runs & Sub-2-Second Reports

**Files:**
- Create: `core/views_reports.py`
- Create: `core/templates/instructor/reports.html`
- Create: `core/templates/admin/reports.html`
- Modify: `core/views_admin.py`
- Modify: `core/views_learner.py`
- Modify: `brightpath/urls.py`
- Test: `tests/test_enrolment_and_reports.py`

**Interfaces:**
- Consumes: `Enrolment`, `Attempt`, `Learner`, `Course`, `Client`, `CourseStaff`.
- Produces: learner self-enrol (`enrolled_by='self'`), admin enrol (`enrolled_by=staff_id`), withdrawal (`withdrawn_on=today`, `outcome='Withdrawn'`), re-enrolment preserving both runs, `/instructor/reports/` (+ CSV), and `/admin-portal/reports/` (+ CSV).

- [ ] **Step 1: Write the failing enrolment and report tests in `tests/test_enrolment_and_reports.py`**
```python
import pytest
from core.models import Client, Staff, Course, CourseStaff, Learner, Enrolment

@pytest.mark.django_db
def test_enrolment_withdrawal_reenrolment_and_reports(client):
    cl = Client.objects.create(client_id="CL01", name="Northwind", seats=100)
    admin = Staff.objects.create(staff_id="S001", full_name="Admin", email="a@bp.example", role="administrator", password_hash="password123")
    inst = Staff.objects.create(staff_id="S007", full_name="Inst", email="i@bp.example", role="instructor", password_hash="password123")
    course = Course.objects.create(course_id="c1-2026-02", title="Course 1", category="Data", cohort="Feb 2026", starts_on="2026-02-01", ends_on="2026-06-01", status="published")
    CourseStaff.objects.create(course=course, staff=inst, role="lead", assigned_on="2026-02-01")
    learner = Learner.objects.create(learner_id="L1", full_name="Learner 1", email="l1@bp.example", client=cl, department="Sales", account_status="active", password_hash="password123")

    # Admin enrols learner
    client.post("/login/", {"username": "S001", "password": "password123"})
    client.post("/admin-portal/enrol/", {"learner_id": "L1", "course_id": "c1-2026-02"})
    e1 = Enrolment.objects.get(learner=learner, course=course)
    assert e1.enrolled_by == "S001"

    # Learner withdraws and then re-enrols; both runs kept
    client.post("/login/", {"username": "L1", "password": "password123"})
    client.post(f"/learner/enrolments/{e1.enrolment_id}/withdraw/")
    e1.refresh_from_db()
    assert e1.outcome == "Withdrawn" and e1.withdrawn_on is not None

    client.post(f"/learner/courses/{course.course_id}/enrol/")
    runs = Enrolment.objects.filter(learner=learner, course=course).order_by("id")
    assert runs.count() == 2
    assert runs[1].enrolled_by == "self"

    # Reports and CSV downloads work
    assert client.get("/admin-portal/reports/").status_code == 403  # still logged in as learner
    client.post("/login/", {"username": "S001", "password": "password123"})
    r_adm = client.get("/admin-portal/reports/")
    assert r_adm.status_code == 200 and b"Northwind" in r_adm.content
    r_csv = client.get("/admin-portal/reports/csv/")
    assert r_csv.status_code == 200 and "text/csv" in r_csv["Content-Type"]
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_enrolment_and_reports.py -v`
Expected: FAIL

- [ ] **Step 3: Implement enrolment/withdrawal/re-enrolment endpoints and `core/views_reports.py` using SQL `GROUP BY` aggregations + streaming/fast CSV generation**

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_enrolment_and_reports.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add core/views_reports.py core/views_admin.py core/views_learner.py core/templates/instructor/reports.html core/templates/admin/reports.html brightpath/urls.py tests/test_enrolment_and_reports.py
git commit -m "feat(enrolment,reports): add enrolment history, withdrawals, and sub-2s SQL reports with CSV export"
```
