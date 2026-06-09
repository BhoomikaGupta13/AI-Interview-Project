import uuid
import json
from pathlib import Path
from datetime import datetime
from datetime import timedelta


SESSION_DIR = Path(
    "storage/sessions"
)

SESSION_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def create_session(

    candidate_profile,

    questions
):

    session_id = str(
        uuid.uuid4()
    )

    expiry = (

        datetime.now()

        +

        timedelta(
            hours=48
        )

    )

    session = {

        "session_id":
        session_id,

        "created_at":

        datetime.now()
        .isoformat(),

        "expires_at":

        expiry
        .isoformat(),

        "status":

        "NOT_STARTED",

        "attempt_used":

        False,

        "questions":

        questions,

        "candidate":

        candidate_profile

    }

    file_path = (

        SESSION_DIR

        /

        f"{session_id}.json"
    )

    with open(

        file_path,

        "w",

        encoding="utf8"

    ) as file:

        json.dump(

            session,

            file,

            indent=4
        )

    return session