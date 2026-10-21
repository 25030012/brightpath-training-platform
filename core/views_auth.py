from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from core.auth import require_role
from core.models import Staff, Learner

ROLE_HOME = {
    "administrator": "/admin-portal/",
    "instructor": "/instructor/",
    "learner": "/learner/",
}


def index_view(request):
    role = request.session.get("user_role")
    if role in ROLE_HOME:
        return redirect(ROLE_HOME[role])
    return redirect("/login/")


def login_view(request):
    error = None
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        staff = Staff.objects.filter(
            Q(staff_id__iexact=username) | Q(email__iexact=username)
        ).first()
        if staff:
            if not staff.is_active_staff:
                error = f"Account {staff.staff_id} ({staff.full_name}) has left on {staff.left_on} and cannot sign in."
            elif staff.password_hash != password:
                error = "Invalid username or password."
            else:
                request.session["user_role"] = staff.role
                request.session["user_id"] = staff.staff_id
                request.session["user_name"] = staff.full_name
                request.session["client_id"] = staff.client_id or ""
                return redirect(ROLE_HOME[staff.role])
        else:
            learner = Learner.objects.filter(
                Q(learner_id__iexact=username) | Q(email__iexact=username)
            ).first()
            if learner:
                if learner.account_status != "active":
                    error = f"Learner account {learner.learner_id} ({learner.full_name}) is deactivated and cannot sign in."
                elif learner.password_hash != password:
                    error = "Invalid username or password."
                else:
                    request.session["user_role"] = "learner"
                    request.session["user_id"] = learner.learner_id
                    request.session["user_name"] = learner.full_name
                    request.session["client_id"] = learner.client_id
                    return redirect("/learner/")
            else:
                error = "Invalid username or password."

    return render(request, "login.html", {"error": error})


def logout_view(request):
    request.session.flush()
    return redirect("/login/")


@require_role("administrator")
def admin_home_placeholder(request):
    return HttpResponse("Admin Portal")


@require_role("instructor")
def instructor_home_placeholder(request):
    return HttpResponse("Instructor Portal")


@require_role("learner")
def learner_home_placeholder(request):
    return HttpResponse("Learner Portal")
