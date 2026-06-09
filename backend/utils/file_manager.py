from pathlib import Path
import uuid


RESUME_DIR = Path(
    "storage/resumes"
)

RESUME_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def save_resume(
    uploaded_file
):

    extension = (
        uploaded_file.name
        .split(".")[-1]
    )

    file_id = (
        str(uuid.uuid4())
    )

    filename = (
        f"{file_id}.{extension}"
    )

    path = (
        RESUME_DIR /
        filename
    )

    with open(
        path,
        "wb"
    ) as file:

        file.write(
            uploaded_file.getbuffer()
        )

    return str(path)