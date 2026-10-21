from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from core import views_auth

urlpatterns = [
    path("", views_auth.index_view, name="index"),
    path("login/", views_auth.login_view, name="login"),
    path("logout/", views_auth.logout_view, name="logout"),
    path("admin-portal/", views_auth.admin_home_placeholder, name="admin_home"),
    path("instructor/", views_auth.instructor_home_placeholder, name="instructor_home"),
    path("learner/", views_auth.learner_home_placeholder, name="learner_home"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
