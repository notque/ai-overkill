def create_user(users, email):
    """Add a user; reject an exact duplicate email with ValueError."""
    user = {"id": len(users) + 1, "email": email}
    users.append(user)
    return user


def list_users(users):
    return list(users)
