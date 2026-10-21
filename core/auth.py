def auth_context(request):
    return {
        "current_role": request.session.get("user_role"),
        "current_user_id": request.session.get("user_id"),
        "current_user_name": request.session.get("user_name"),
    }
