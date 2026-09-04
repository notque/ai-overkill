def create_user(users, email):
    """Add a user; reject an exact duplicate email with ValueError."""
    if any(user["email"] == email for user in users):
        raise ValueError("duplicate email")
    user = {"id": len(users) + 1, "email": email}
    users.append(user)
    return user


def list_users(users):
    return list(users)
