import csv
import io
import time
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from core.auth import require_role, get_current_staff
from core.models import Course, CourseStaff, Attempt


def _fetch_admin_report_data(client_id_filter: str = ""):
    where_clause = ""
    params = []
    if client_id_filter:
        where_clause = "WHERE c.client_id = %s"
        params.append(client_id_filter)

    with connection.cursor() as cur:
        # 1. Completion by Client
        cur.execute(
            f"""
            SELECT
                c.client_id,
                c.name,
                c.seats,
                c.contract_end,
                COUNT(DISTINCT l.learner_id) AS total_learners,
                COUNT(e.enrolment_id) AS total_enrolments,
                SUM(CASE WHEN e.outcome IN ('Pass', 'Distinction') THEN 1 ELSE 0 END) AS completed_count,
                SUM(CASE WHEN e.outcome = 'Distinction' THEN 1 ELSE 0 END) AS distinction_count,
                SUM(CASE WHEN e.outcome = 'Withdrawn' THEN 1 ELSE 0 END) AS withdrawn_count,
                SUM(CASE WHEN e.outcome = 'Fail' THEN 1 ELSE 0 END) AS fail_count
            FROM core_client c
            LEFT JOIN core_learner l ON l.client_id = c.client_id
            LEFT JOIN core_enrolment e ON e.learner_id = l.learner_id
            {where_clause}
            GROUP BY c.client_id, c.name, c.seats, c.contract_end
            ORDER BY c.client_id
            """,
            params,
        )
        client_rows = []
        for r in cur.fetchall():
            tot_e = r[5] or 0
            comp = r[6] or 0
            rate = round((comp / tot_e) * 100.0, 1) if tot_e else 0.0
            client_rows.append(
                {
                    "client_id": r[0],
                    "client_name": r[1],
                    "seats": r[2],
                    "contract_end": r[3] or "Active",
                    "total_learners": r[4] or 0,
                    "total_enrolments": tot_e,
                    "completed_count": comp,
                    "distinction_count": r[7] or 0,
                    "withdrawn_count": r[8] or 0,
                    "fail_count": r[9] or 0,
                    "completion_rate": rate,
                }
            )

        # 2. Completion by Client & Department
        cur.execute(
            f"""
            SELECT
                c.client_id,
                c.name,
                l.department,
                COUNT(DISTINCT l.learner_id) AS total_learners,
                COUNT(e.enrolment_id) AS total_enrolments,
                SUM(CASE WHEN e.outcome IN ('Pass', 'Distinction') THEN 1 ELSE 0 END) AS completed_count,
                SUM(CASE WHEN e.outcome = 'Withdrawn' THEN 1 ELSE 0 END) AS withdrawn_count,
                SUM(CASE WHEN e.outcome = 'Fail' THEN 1 ELSE 0 END) AS fail_count
            FROM core_learner l
            JOIN core_client c ON c.client_id = l.client_id
            LEFT JOIN core_enrolment e ON e.learner_id = l.learner_id
            {where_clause}
            GROUP BY c.client_id, c.name, l.department
            ORDER BY c.client_id, l.department
            """,
            params,
        )
        dept_rows = []
        for r in cur.fetchall():
            tot_e = r[4] or 0
            comp = r[5] or 0
            rate = round((comp / tot_e) * 100.0, 1) if tot_e else 0.0
            dept_rows.append(
                {
                    "client_id": r[0],
                    "client_name": r[1],
                    "department": r[2],
                    "total_learners": r[3] or 0,
                    "total_enrolments": tot_e,
                    "completed_count": comp,
                    "withdrawn_count": r[6] or 0,
                    "fail_count": r[7] or 0,
                    "completion_rate": rate,
                }
            )

    return client_rows, dept_rows


@require_role("administrator")
def admin_reports(request):
    t0 = time.perf_counter()
    staff = get_current_staff(request)
    client_rows, dept_rows = _fetch_admin_report_data(staff.client_id or "")
    total_attempts = Attempt.objects.count()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    return render(
        request,
        "admin/reports.html",
        {
            "staff": staff,
            "client_rows": client_rows,
            "dept_rows": dept_rows,
            "total_attempts": total_attempts,
            "elapsed_ms": elapsed_ms,
        },
    )


@require_role("administrator")
def admin_reports_csv(request):
    staff = get_current_staff(request)
    _, dept_rows = _fetch_admin_report_data(staff.client_id or "")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "client_id",
            "client_name",
            "department",
            "total_learners",
            "total_enrolments",
            "completed_count",
            "withdrawn_count",
            "fail_count",
            "completion_rate_pct",
        ]
    )
    for r in dept_rows:
        writer.writerow(
            [
                r["client_id"],
                r["client_name"],
                r["department"],
                r["total_learners"],
                r["total_enrolments"],
                r["completed_count"],
                r["withdrawn_count"],
                r["fail_count"],
                r["completion_rate"],
            ]
        )
    resp = HttpResponse(buf.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="admin_completion_report.csv"'
    return resp


def _fetch_instructor_cohort_rows(course_ids, course_filter="", q="", limit=250):
    if not course_ids:
        return [], 0
    target_ids = [c for c in course_ids if not course_filter or c == course_filter]
    if not target_ids:
        return [], 0

    placeholders = ", ".join(["%s"] * len(target_ids))
    params = list(target_ids)
    extra_where = ""
    if q:
        extra_where = "AND (l.learner_id LIKE %s OR l.full_name LIKE %s OR l.department LIKE %s)"
        like_q = f"%{q}%"
        params.extend([like_q, like_q, like_q])

    with connection.cursor() as cur:
        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM core_enrolment e
            JOIN core_learner l ON l.learner_id = e.learner_id
            WHERE e.course_id IN ({placeholders}) {extra_where}
            """,
            params,
        )
        total_matching = cur.fetchone()[0] or 0

        limit_clause = f"LIMIT {int(limit)}" if limit else ""
        cur.execute(
            f"""
            SELECT
                e.enrolment_id,
                e.course_id,
                c.title,
                c.cohort,
                l.learner_id,
                l.full_name,
                l.client_id,
                l.department,
                e.enrolled_on,
                e.enrolled_by,
                e.outcome,
                e.withdrawn_on,
                COALESCE(SUM(ab.att_cnt), 0) AS attempt_count,
                ROUND(AVG(ab.best_score), 1) AS avg_score,
                MAX(ab.best_score) AS max_score
            FROM core_enrolment e
            JOIN core_learner l ON l.learner_id = e.learner_id
            JOIN core_course c ON c.course_id = e.course_id
            LEFT JOIN (
                SELECT
                    learner_id,
                    course_id,
                    assessment_id,
                    COUNT(attempt_id) AS att_cnt,
                    MAX(score) AS best_score
                FROM core_attempt
                WHERE course_id IN ({placeholders})
                GROUP BY learner_id, course_id, assessment_id
            ) ab ON ab.learner_id = e.learner_id AND ab.course_id = e.course_id
            WHERE e.course_id IN ({placeholders}) {extra_where}
            GROUP BY
                e.enrolment_id, e.course_id, c.title, c.cohort,
                l.learner_id, l.full_name, l.client_id, l.department,
                e.enrolled_on, e.enrolled_by, e.outcome, e.withdrawn_on
            ORDER BY e.course_id, e.enrolled_on DESC, l.learner_id
            {limit_clause}
            """,
            list(target_ids) + params,
        )
        rows = [
            {
                "enrolment_id": r[0],
                "course_id": r[1],
                "course_title": r[2],
                "cohort": r[3],
                "learner_id": r[4],
                "full_name": r[5],
                "client_id": r[6],
                "department": r[7],
                "enrolled_on": r[8],
                "enrolled_by": r[9],
                "outcome": r[10],
                "withdrawn_on": r[11] or "",
                "attempt_count": r[12] or 0,
                "avg_score": r[13] if r[13] is not None else "—",
                "max_score": r[14] if r[14] is not None else "—",
            }
            for r in cur.fetchall()
        ]
    return rows, total_matching


@require_role("instructor")
def instructor_reports(request):
    t0 = time.perf_counter()
    staff = get_current_staff(request)
    assigned_course_ids = list(
        CourseStaff.objects.filter(staff=staff, unassigned_on="").values_list(
            "course_id", flat=True
        )
    )
    my_courses = Course.objects.filter(course_id__in=assigned_course_ids).order_by(
        "course_id"
    )
    course_filter = (request.GET.get("course_id") or "").strip()
    q = (request.GET.get("q") or "").strip()

    rows, total_matching = _fetch_instructor_cohort_rows(
        assigned_course_ids, course_filter=course_filter, q=q, limit=250
    )
    total_attempts = Attempt.objects.count()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    return render(
        request,
        "instructor/reports.html",
        {
            "staff": staff,
            "my_courses": my_courses,
            "rows": rows,
            "total_matching": total_matching,
            "total_attempts": total_attempts,
            "course_filter": course_filter,
            "q": q,
            "elapsed_ms": elapsed_ms,
        },
    )


@require_role("instructor")
def instructor_reports_csv(request):
    staff = get_current_staff(request)
    assigned_course_ids = list(
        CourseStaff.objects.filter(staff=staff, unassigned_on="").values_list(
            "course_id", flat=True
        )
    )
    course_filter = (request.GET.get("course_id") or "").strip()
    q = (request.GET.get("q") or "").strip()
    rows, _ = _fetch_instructor_cohort_rows(
        assigned_course_ids, course_filter=course_filter, q=q, limit=None
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "enrolment_id",
            "course_id",
            "course_title",
            "cohort",
            "learner_id",
            "full_name",
            "client_id",
            "department",
            "enrolled_on",
            "enrolled_by",
            "outcome",
            "withdrawn_on",
            "attempt_count",
            "avg_score",
            "max_score",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["enrolment_id"],
                r["course_id"],
                r["course_title"],
                r["cohort"],
                r["learner_id"],
                r["full_name"],
                r["client_id"],
                r["department"],
                r["enrolled_on"],
                r["enrolled_by"],
                r["outcome"],
                r["withdrawn_on"],
                r["attempt_count"],
                r["avg_score"],
                r["max_score"],
            ]
        )
    resp = HttpResponse(buf.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="instructor_cohort_results.csv"'
    return resp
