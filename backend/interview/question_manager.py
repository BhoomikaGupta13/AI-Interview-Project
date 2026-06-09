def get_question(
    session,
    index
):

    questions = session[
        "questions"
    ]

    if index >= len(
        questions
    ):

        return None

    return questions[
        index
    ]