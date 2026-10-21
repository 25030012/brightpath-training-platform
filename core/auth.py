from functools import wraps
from django.http import HttpResponseForbidden
from core.models import Staff, Learner


def auth_context(request):
    return {
        "current_role": request.session.get("user_role"),
        "current_user_id": request.session.get("user_id"),
        "current_user_name": request.session.get("user_name"),
        "current_client_id": request.session.get("client_id"),
    }


def require_role(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            role = request.session.get("user_role")
            if not role or role not in allowed_roles:
                return HttpResponseForbidden(
                    "403 Forbidden: Your role does not have access to this page."
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def get_current_staff(request) -> Staff:
    return Staff.objects.select_related("client").get(
        staff_id=request.session["user_id"]
    )


def get_current_learner(request) -> Learner:
    return Learner.objects.select_related("client").get(
        learner_id=request.session["user_id"]
    )
