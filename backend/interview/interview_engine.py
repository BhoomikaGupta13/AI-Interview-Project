from datetime import datetime

from backend.interview.expiry_manager import (
    check_expiry
)

from backend.interview.attempt_lock import (
    can_start,
    start_attempt
)


def initialize_interview(
    session
):

    if not check_expiry(
        session
    ):

        session[
            "status"
        ]="EXPIRED"

        raise Exception(
            "Interview expired"
        )

    if not can_start(
        session
    ):

        raise Exception(
            "Attempt already used"
        )

    session = start_attempt(
        session
    )

    session[
        "started_at"
    ]=datetime.now().isoformat()

    return session