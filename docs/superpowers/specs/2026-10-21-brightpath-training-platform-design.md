# BrightPath Training Platform — Design Spec

## 1. Intent & Why
BrightPath runs corporate training cohorts across corporate clients (`clients.csv`), staff (`staff.csv`), courses (`courses.csv`, `course_staff.csv`), assessments (`assessments.csv`), learners (`learners.csv`), enrolments (`enrolments.csv`), and attempts (`attempts.csv`). This platform replaces their spreadsheets with a role-based web application for Administrators, Instructors, and Learners.

## 2. Tech Stack & Startup Constraint
- **Framework**: Django 5.x (Python 3) + PostgreSQL + HTMX + Tailwind CSS (via CDN).
- **One-Command Startup (`./start.sh`)**:
  - Creates/activates `.venv` and installs dependencies (`django`, `psycopg[binary]`, `pytest`, `pytest-django`).
  - Ensures a local PostgreSQL server is running (starts a local cluster in `.pgdata` via `pg_ctl` if port 5432 is not already accepting connections) and ensures database `brightpath` exists.
  - Runs `python manage.py migrate`.
  - Runs `python manage.py import_seed --data-dir data` (idempotent; skips already-imported records).
  - Starts the HTTP server on `http://127.0.0.1:8000`.

## 3. Domain & Module Decisions (from Interview)
1. **Module 1 — Import (`python manage.py import_seed`)**:
   - Loads all 8 CSVs in dependency order: `clients`, `staff`, `courses`, `course_staff`, `assessments`, `learners`, `enrolments`, `attempts`.
   - **Rejection Rules**:
     - `learners.csv`: Reject rows missing `client_id` or `department` (2,310 `self-signup` rows without client/department) or missing `account_created_on` (30 rows, 3 overlap = 2,337 rejected learners).
     - `enrolments.csv`: Reject rows whose `learner_id` was rejected, rows missing `enrolled_on` (45 rows), or rows where `outcome == 'Withdrawn'` lacks `withdrawn_on` (or vice versa, 102 rows).
     - `attempts.csv`: Reject rows whose `learner_id` was rejected or who lack a valid enrolment in `course_id`, or rows with blank `score` (173 rows).
     - Valid historical quirks are **kept**: staff with `left_on` set, expired client contract (`CL05`), unstaffed cohort (`cyber-security-awareness-2026-10`), assessments with blank `author_id`, and auto-graded quiz attempts with blank `graded_by`.
   - **Idempotency & Output**: Uses bulk/upsert logic keyed by CSV primary keys (`client_id`, `staff_id`, `course_id`, `assessment_id`, `learner_id`, `enrolment_id`, `attempt_id`, plus `(course_id, staff_id, assigned_on)` for `course_staff`). Prints exact counts of imported vs. rejected rows per file and grouped rejection reasons.
2. **Module 2 — Sign-in & Roles**:
   - Imported staff and learners can sign in using **either their email or their ID (`staff_id` / `learner_id`)** as username and default password `password123` (stored via a deterministic fast check or standard Django password hash; bulk-imported users share a pre-computed PBKDF2 hash of `password123` for fast import).
   - Staff with `left_on` set (not empty) and learners with `account_status == 'deactivated'` are refused sign-in with an explicit error message.
   - Each role redirects to its dedicated home page:
     - Administrator $\rightarrow$ `/admin-portal/`
     - Instructor $\rightarrow$ `/instructor/`
     - Learner $\rightarrow$ `/learner/`
   - Server-side role decorators return HTTP `403 Forbidden` when any user requests another role's URL directly.
3. **Module 3 — People**:
   - Administrators can create a new learner (assigning `full_name`, `email`, `password`, `client`, `department`, `created_by=current_staff`, `account_status='active'`) and deactivate active learners (`account_status='deactivated'`). Nothing is ever deleted.
   - Client-scoped administrators (`staff.client_id` is set, e.g. `S004` for `CL02`, `S005` for `CL03`) only see and can only create/manage learners belonging to their `client_id`.
   - Administrators can assign an instructor to a cohort (`CourseStaff` record with `assigned_on=today`) and unassign them (`unassigned_on=today`), keeping full assignment history visible on the cohort.
4. **Module 4 — Courses**:
   - Courses (`Course` model representing a cohort, with `status` defaulting to `'published'` for imported cohorts and `'draft'` for newly created courses) have ordered content pages (`CoursePage`: `title`, `body_text`, optional uploaded `image` and `pdf_file`).
   - Instructors can create a new course cohort (starts as `draft`), add/edit pages with text, images, and PDFs, and publish it (`status='published'`).
   - Learners never see draft courses or draft assessments.
   - Instructors can only edit courses/cohorts where they have an active `CourseStaff` assignment (`unassigned_on` is null); other cohorts return `403 Forbidden` on edit actions.
5. **Module 5 — Quizzes & Assignments**:
   - Instructors can add a multiple-choice `Quiz` (with `QuizQuestion` and 4 options + `correct_option`) or a hand-marked `Assignment` to a cohort they teach, and publish it.
   - Learners submit quiz answers (auto-graded immediately on submission, recording `score` 0–100 and `graded_by=''`) or assignment text submissions (`score=None` until graded by instructor, who sets `score` and `graded_by=instructor.staff_id`).
   - **Retake Rule**: Every submission creates a new `Attempt` row and is never overwritten. Learners can submit retakes on quizzes/assignments, and the platform uses the **highest score** across attempts as the learner's effective score for that assessment.
6. **Module 6 — Enrolment**:
   - Learners can enrol themselves (`enrolled_by='self'`) in any published cohort, or an Administrator can enrol a learner (`enrolled_by=admin.staff_id`). The UI displays who enrolled them.
   - Withdrawing from an enrolment sets `withdrawn_on=today` and `outcome='Withdrawn'` while preserving the enrolment record.
   - A learner who previously took a course (whether withdrawn, failed, or passed, or in another cohort of the same course) can enrol again (creating a new `Enrolment` run with `previous_attempts` incremented), and all runs are visible in their history.
7. **Module 7 — Progress & Reports**:
   - **Instructor Report (`/instructor/reports/`)**: Shows every learner's results (enrolment status, attempts count, weighted/average score, outcome) for the instructor's assigned cohorts, opens in `< 2 seconds` with all imported attempts loaded (using SQL aggregation in PostgreSQL), and downloads as CSV (`/instructor/reports/csv/`).
   - **Administrator Report (`/admin-portal/reports/`)**: Shows completion breakdown by client and by department (total enrolments, completed/passed/distinction, withdrawn, fail, completion rate %), scoped to the admin's client if `client_id` is set, opens in `< 2 seconds` via SQL `GROUP BY`, and downloads as CSV (`/admin-portal/reports/csv/`).
