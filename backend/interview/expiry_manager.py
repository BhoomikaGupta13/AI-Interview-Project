from datetime import datetime


def check_expiry(
    session
):

    expiry = (

        datetime.fromisoformat(

            session[
                "expires_at"
            ]
        )
    )

    if datetime.now() > expiry:

        return False

    return True