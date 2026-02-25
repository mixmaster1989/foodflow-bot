def get_user_display_name(user) -> str:
    """
    Returns the most human-readable name for a user.
    Priority: First Name + Last Name -> @Username -> ID
    """
    first = getattr(user, 'first_name', None) or ""
    last = getattr(user, 'last_name', None) or ""
    full_name = f"{first} {last}".strip()

    if full_name:
        return full_name

    username = getattr(user, 'username', None)
    if username:
        return f"@{username}"

    return f"id:{getattr(user, 'id', 'unknown')}"

def get_user_display_long(user) -> str:
    """
    Returns a long format: First Last (@username) or ID.
    Used in lists and detailed views.
    """
    name = get_user_display_name(user)
    username = getattr(user, 'username', None)

    if username and not name.startswith("@"):
        return f"{name} (@{username})"

    return name
