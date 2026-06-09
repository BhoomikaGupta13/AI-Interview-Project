def build_blueprint(profile):

    skills = len(
        profile.get(
            "skills",
            []
        )
    )

    projects = len(
        profile.get(
            "projects",
            []
        )
    )

    patents = len(
        profile.get(
            "patents",
            []
        )
    )

    research = len(
        profile.get(
            "research_publications",
            []
        )
    )

    achievements = len(
        profile.get(
            "achievements",
            []
        )
    )

    blueprint = {

        "skill_questions":

        min(
            skills,
            4
        ),

        "project_questions":

        min(
            projects*2,
            4
        ),

        "experience_questions":

        2,

        "research_questions":

        min(
            research,
            1
        ),

        "patent_questions":

        min(
            patents,
            1
        ),

        "achievement_questions":

        min(
            achievements,
            1
        )

    }

    return blueprint