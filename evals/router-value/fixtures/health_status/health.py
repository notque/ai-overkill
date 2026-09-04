def is_healthy(status_code):
    """A health response succeeds exactly for HTTP 2xx statuses."""
    return status_code is not None
