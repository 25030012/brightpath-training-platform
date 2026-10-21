from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from core.auth import verify_password
from core.models import Staff, Learner, Course

ROLE_HOME = {
    "administrator": "/admin-portal/",
    "instructor": "/instructor/",
    "learner": "/learner/",
}


def healthz_view(request):
    return JsonResponse({"status": "ok", "courses": Course.objects.count()})


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
                error = f"Staff account {staff.staff_id} ({staff.full_name}) left on {staff.left_on} and cannot sign in."
            elif not verify_password(password, staff.password_hash):
                error = "Invalid username or password."
            else:
                request.session.flush()
                request.session["user_role"] = staff.role
                request.session["user_id"] = staff.staff_id
                request.session["user_name"] = staff.full_name
                request.session["client_id"] = staff.client_id or ""
                messages.success(request, f"Welcome back, {staff.full_name} ({staff.role}).")
                return redirect(ROLE_HOME[staff.role])
        else:
            learner = Learner.objects.filter(
                Q(learner_id__iexact=username) | Q(email__iexact=username)
            ).first()
            if learner:
                if learner.account_status != "active":
                    error = f"Learner account {learner.learner_id} ({learner.full_name}) is deactivated and cannot sign in."
                elif not verify_password(password, learner.password_hash):
                    error = "Invalid username or password."
                else:
                    request.session.flush()
                    request.session["user_role"] = "learner"
                    request.session["user_id"] = learner.learner_id
                    request.session["user_name"] = learner.full_name
                    request.session["client_id"] = learner.client_id
                    messages.success(request, f"Welcome back, {learner.full_name}.")
                    return redirect("/learner/")
            else:
                error = "Invalid username or password."

    return render(request, "login.html", {"error": error})


def logout_view(request):
    request.session.flush()
    return redirect("/login/")
