def can_start(
    session
):

    if session[
        "attempt_used"
    ]:

        return False

    return True


def start_attempt(
    session
):

    session[
        "attempt_used"
    ] = True

    session[
        "status"
    ] = "IN_PROGRESS"

    return session