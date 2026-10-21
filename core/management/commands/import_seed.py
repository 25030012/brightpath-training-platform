import csv
import os
from collections import Counter
from django.core.management.base import BaseCommand
from django.db import transaction
from core.auth import hash_password
from core.models import (
    Client,
    Staff,
    Course,
    CourseStaff,
    Assessment,
    Learner,
    Enrolment,
    Attempt,
)


def _read_csv(data_dir: str, name: str):
    path = os.path.join(data_dir, f"{name}.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_import(data_dir: str = "data", stdout=None) -> dict:
    stats = {}
    default_pw_hash = hash_password("password123")

    def record(table: str, inserted: int, reasons: Counter):
        stats[table] = {
            "inserted": inserted,
            "rejected": sum(reasons.values()),
            "reasons": dict(reasons),
        }
        if stdout:
            stdout.write(
                f"[{table}.csv] Imported: {inserted} | Rejected: {sum(reasons.values())}"
            )
            for reason, count in reasons.items():
                stdout.write(f"   - {reason}: {count}")

    with transaction.atomic():
        # 1. clients.csv
        client_rows = _read_csv(data_dir, "clients")
        client_reasons = Counter()
        client_objs = []
        valid_clients = set()
        for r in client_rows:
            cid = r["client_id"].strip()
            if not cid or not r["name"].strip():
                client_reasons["missing client_id or name"] += 1
                continue
            valid_clients.add(cid)
            client_objs.append(
                Client(
                    client_id=cid,
                    name=r["name"].strip(),
                    industry=r["industry"].strip(),
                    email_domain=r["email_domain"].strip(),
                    contract_start=r["contract_start"].strip(),
                    contract_end=r["contract_end"].strip(),
                    seats=int(r["seats"] or 0),
                )
            )
        Client.objects.bulk_create(client_objs, ignore_conflicts=True)
        record("clients", len(client_objs), client_reasons)

        # 2. staff.csv
        staff_rows = _read_csv(data_dir, "staff")
        staff_reasons = Counter()
        staff_objs = []
        valid_staff = set()
        for r in staff_rows:
            sid = r["staff_id"].strip()
            cid = r["client_id"].strip()
            if not sid or not r["email"].strip():
                staff_reasons["missing staff_id or email"] += 1
                continue
            if cid and cid not in valid_clients:
                staff_reasons["invalid client_id"] += 1
                continue
            valid_staff.add(sid)
            staff_objs.append(
                Staff(
                    staff_id=sid,
                    full_name=r["full_name"].strip(),
                    email=r["email"].strip(),
                    role=r["role"].strip(),
                    client_id=cid or None,
                    specialism=r["specialism"].strip(),
                    joined_on=r["joined_on"].strip(),
                    left_on=r["left_on"].strip(),
                    password_hash=default_pw_hash,
                )
            )
        Staff.objects.bulk_create(staff_objs, ignore_conflicts=True)
        Staff.objects.filter(password_hash="password123").update(password_hash=default_pw_hash)
        record("staff", len(staff_objs), staff_reasons)

        # 3. courses.csv
        course_rows = _read_csv(data_dir, "courses")
        course_reasons = Counter()
        course_objs = []
        valid_courses = set()
        for r in course_rows:
            coid = r["course_id"].strip()
            if not coid or not r["title"].strip():
                course_reasons["missing course_id or title"] += 1
                continue
            valid_courses.add(coid)
            course_objs.append(
                Course(
                    course_id=coid,
                    title=r["title"].strip(),
                    category=r["category"].strip(),
                    description=r["description"].strip(),
                    cohort=r["cohort"].strip(),
                    starts_on=r["starts_on"].strip(),
                    ends_on=r["ends_on"].strip(),
                    length_days=int(r["length_days"] or 0),
                    status="published",
                )
            )
        Course.objects.bulk_create(course_objs, ignore_conflicts=True)
        record("courses", len(course_objs), course_reasons)

        # 4. course_staff.csv
        cs_rows = _read_csv(data_dir, "course_staff")
        cs_reasons = Counter()
        cs_objs = []
        for r in cs_rows:
            coid = r["course_id"].strip()
            sid = r["staff_id"].strip()
            if coid not in valid_courses or sid not in valid_staff:
                cs_reasons["unknown course_id or staff_id"] += 1
                continue
            cs_objs.append(
                CourseStaff(
                    course_id=coid,
                    staff_id=sid,
                    role=r["role"].strip(),
                    assigned_on=r["assigned_on"].strip(),
                    unassigned_on=r["unassigned_on"].strip(),
                )
            )
        CourseStaff.objects.bulk_create(cs_objs, ignore_conflicts=True)
        record("course_staff", len(cs_objs), cs_reasons)

        # 5. assessments.csv
        as_rows = _read_csv(data_dir, "assessments")
        as_reasons = Counter()
        as_objs = []
        valid_assessments = set()
        for r in as_rows:
            aid = r["assessment_id"].strip()
            coid = r["course_id"].strip()
            auid = r["author_id"].strip()
            if not aid or coid not in valid_courses:
                as_reasons["invalid assessment_id or course_id"] += 1
                continue
            valid_assessments.add(aid)
            as_objs.append(
                Assessment(
                    assessment_id=aid,
                    course_id=coid,
                    type=r["type"].strip(),
                    title=r["title"].strip(),
                    due_on=r["due_on"].strip(),
                    weight_pct=float(r["weight_pct"] or 0.0),
                    author_id=auid if auid in valid_staff else None,
                    status=r["status"].strip() or "published",
                    published_on=r["published_on"].strip(),
                )
            )
        Assessment.objects.bulk_create(as_objs, ignore_conflicts=True)
        record("assessments", len(as_objs), as_reasons)

        # 6. learners.csv
        learner_rows = _read_csv(data_dir, "learners")
        learner_reasons = Counter()
        learner_objs = []
        valid_learners = set()
        for r in learner_rows:
            lid = r["learner_id"].strip()
            cid = r["client_id"].strip()
            dept = r["department"].strip()
            created_on = r["account_created_on"].strip()
            if not cid or cid not in valid_clients or not dept:
                learner_reasons["missing client_id or department"] += 1
                continue
            if not created_on:
                learner_reasons["missing account_created_on"] += 1
                continue
            valid_learners.add(lid)
            learner_objs.append(
                Learner(
                    learner_id=lid,
                    full_name=r["full_name"].strip(),
                    email=r["email"].strip(),
                    client_id=cid,
                    department=dept,
                    account_created_on=created_on,
                    created_by=r["created_by"].strip(),
                    account_status=r["account_status"].strip() or "active",
                    password_hash=default_pw_hash,
                )
            )
        Learner.objects.bulk_create(learner_objs, batch_size=5000, ignore_conflicts=True)
        Learner.objects.filter(password_hash="password123").update(password_hash=default_pw_hash)
        record("learners", len(learner_objs), learner_reasons)

        # 7. enrolments.csv
        enrol_rows = _read_csv(data_dir, "enrolments")
        enrol_reasons = Counter()
        enrol_objs = []
        valid_enrolment_pairs = set()
        for r in enrol_rows:
            eid = r["enrolment_id"].strip()
            lid = r["learner_id"].strip()
            coid = r["course_id"].strip()
            enrolled_on = r["enrolled_on"].strip()
            withdrawn_on = r["withdrawn_on"].strip()
            outcome = r["outcome"].strip()
            if lid not in valid_learners or coid not in valid_courses:
                enrol_reasons["rejected or unknown learner_id/course_id"] += 1
                continue
            if not enrolled_on:
                enrol_reasons["missing enrolled_on date"] += 1
                continue
            if (outcome == "Withdrawn") != bool(withdrawn_on):
                enrol_reasons["outcome/withdrawn_on mismatch"] += 1
                continue
            valid_enrolment_pairs.add((lid, coid))
            enrol_objs.append(
                Enrolment(
                    enrolment_id=eid,
                    learner_id=lid,
                    course_id=coid,
                    enrolled_on=enrolled_on,
                    withdrawn_on=withdrawn_on,
                    outcome=outcome,
                    previous_attempts=int(r["previous_attempts"] or 0),
                    activity_clicks=int(r["activity_clicks"] or 0),
                    enrolled_by=r["enrolled_by"].strip() or "self",
                )
            )
        Enrolment.objects.bulk_create(enrol_objs, batch_size=5000, ignore_conflicts=True)
        record("enrolments", len(enrol_objs), enrol_reasons)

        # 8. attempts.csv
        attempt_rows = _read_csv(data_dir, "attempts")
        attempt_reasons = Counter()
        attempt_objs = []
        for r in attempt_rows:
            atid = r["attempt_id"].strip()
            aid = r["assessment_id"].strip()
            lid = r["learner_id"].strip()
            coid = r["course_id"].strip()
            score_str = r["score"].strip()
            if (lid, coid) not in valid_enrolment_pairs or aid not in valid_assessments:
                attempt_reasons["learner/enrolment rejected or unknown assessment"] += 1
                continue
            if not score_str:
                attempt_reasons["missing score"] += 1
                continue
            attempt_objs.append(
                Attempt(
                    attempt_id=atid,
                    assessment_id=aid,
                    learner_id=lid,
                    course_id=coid,
                    submitted_on=r["submitted_on"].strip(),
                    score=float(score_str),
                    graded_by=r["graded_by"].strip(),
                )
            )
        Attempt.objects.bulk_create(attempt_objs, batch_size=5000, ignore_conflicts=True)
        record("attempts", len(attempt_objs), attempt_reasons)

    return stats


class Command(BaseCommand):
    help = "Idempotently import all 8 BrightPath seed CSVs and print rejection summary."

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", default="data", help="Directory containing CSV files")

    def handle(self, *args, **options):
        data_dir = options["data_dir"]
        self.stdout.write("=== BrightPath Seed Data Import ===")
        run_import(data_dir=data_dir, stdout=self.stdout)
        self.stdout.write("=== Import Complete ===")
