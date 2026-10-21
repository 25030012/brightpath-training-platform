from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from core import views_auth, views_admin

urlpatterns = [
    path("", views_auth.index_view, name="index"),
    path("login/", views_auth.login_view, name="login"),
    path("logout/", views_auth.logout_view, name="logout"),
    path("admin-portal/", views_admin.admin_home, name="admin_home"),
    path("admin-portal/learners/create/", views_admin.create_learner, name="create_learner"),
    path("admin-portal/learners/<str:learner_id>/deactivate/", views_admin.deactivate_learner, name="deactivate_learner"),
    path("admin-portal/enrol/", views_admin.admin_enrol_learner, name="admin_enrol_learner"),
    path("admin-portal/cohorts/<str:course_id>/staff/", views_admin.cohort_staff_view, name="cohort_staff"),
    path("admin-portal/cohorts/<str:course_id>/staff/assign/", views_admin.assign_cohort_staff, name="assign_cohort_staff"),
    path("admin-portal/cohorts/<str:course_id>/staff/<int:assignment_id>/unassign/", views_admin.unassign_cohort_staff, name="unassign_cohort_staff"),
    path("instructor/", views_auth.instructor_home_placeholder, name="instructor_home"),
    path("learner/", views_auth.learner_home_placeholder, name="learner_home"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
