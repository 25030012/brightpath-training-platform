from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from core import views_auth, views_admin, views_instructor, views_learner, views_reports

urlpatterns = [
    path("", views_auth.index_view, name="index"),
    path("login/", views_auth.login_view, name="login"),
    path("logout/", views_auth.logout_view, name="logout"),
    # Administrator
    path("admin-portal/", views_admin.admin_home, name="admin_home"),
    path("admin-portal/learners/create/", views_admin.create_learner, name="create_learner"),
    path("admin-portal/learners/<str:learner_id>/deactivate/", views_admin.deactivate_learner, name="deactivate_learner"),
    path("admin-portal/enrol/", views_admin.admin_enrol_learner, name="admin_enrol_learner"),
    path("admin-portal/cohorts/<str:course_id>/staff/", views_admin.cohort_staff_view, name="cohort_staff"),
    path("admin-portal/cohorts/<str:course_id>/staff/assign/", views_admin.assign_cohort_staff, name="assign_cohort_staff"),
    path("admin-portal/cohorts/<str:course_id>/staff/<int:assignment_id>/unassign/", views_admin.unassign_cohort_staff, name="unassign_cohort_staff"),
    path("admin-portal/reports/", views_reports.admin_reports, name="admin_reports"),
    path("admin-portal/reports/csv/", views_reports.admin_reports_csv, name="admin_reports_csv"),
    # Instructor
    path("instructor/", views_instructor.instructor_home, name="instructor_home"),
    path("instructor/courses/create/", views_instructor.create_course, name="create_course"),
    path("instructor/courses/<str:course_id>/edit/", views_instructor.course_edit_view, name="course_edit"),
    path("instructor/courses/<str:course_id>/publish/", views_instructor.publish_course, name="publish_course"),
    path("instructor/courses/<str:course_id>/pages/create/", views_instructor.create_course_page, name="create_course_page"),
    path("instructor/courses/<str:course_id>/assessments/create/", views_instructor.create_assessment, name="create_assessment"),
    path("instructor/assessments/<str:assessment_id>/publish/", views_instructor.publish_assessment, name="publish_assessment"),
    path("instructor/attempts/<str:attempt_id>/grade/", views_instructor.grade_attempt, name="grade_attempt"),
    path("instructor/reports/", views_reports.instructor_reports, name="instructor_reports"),
    path("instructor/reports/csv/", views_reports.instructor_reports_csv, name="instructor_reports_csv"),
    # Learner
    path("learner/", views_learner.learner_home, name="learner_home"),
    path("learner/courses/<str:course_id>/", views_learner.learner_course_detail, name="learner_course_detail"),
    path("learner/courses/<str:course_id>/enrol/", views_learner.learner_enrol, name="learner_enrol"),
    path("learner/enrolments/<str:enrolment_id>/withdraw/", views_learner.learner_withdraw, name="learner_withdraw"),
    path("learner/assessments/<str:assessment_id>/submit/", views_learner.learner_submit_assessment, name="learner_submit_assessment"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
