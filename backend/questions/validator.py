from rapidfuzz import fuzz


def validate_questions(
    questions
):

    filtered = []

    for q in questions:

        duplicate = False

        for existing in filtered:

            score = (

                fuzz.ratio(
                    q,
                    existing
                )
            )

            if score > 85:

                duplicate=True

                break

        if not duplicate:

            filtered.append(
                q
            )

    return filtered