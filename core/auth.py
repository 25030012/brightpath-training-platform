from functools import wraps
import hmac
from django.contrib.auth.hashers import make_password, check_password
from django.shortcuts import render
from core.models import Staff, Learner


def hash_password(raw_password: str) -> str:
    return make_password(raw_password)


def verify_password(raw_password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_"):
        return check_password(raw_password, stored_hash)
    return hmac.compare_digest(stored_hash, raw_password)


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
                return render(
                    request,
                    "403.html",
                    {
                        "required_roles": ", ".join(allowed_roles),
                        "current_role": role or "unauthenticated",
                    },
                    status=403,
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
