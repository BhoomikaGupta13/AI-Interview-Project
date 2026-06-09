import fitz


MAX_MB = 10


def validate_resume(
    uploaded_file
):

    if not uploaded_file:

        raise Exception(
            "No file uploaded"
        )

    if not (
        uploaded_file.name
        .endswith(".pdf")
    ):

        raise Exception(
            "PDF only"
        )

    size = (
        uploaded_file.size
        / 1024
        / 1024
    )

    if size > MAX_MB:

        raise Exception(
            "File too large"
        )

    try:

        pdf = fitz.open(

            stream=
            uploaded_file.read(),

            filetype="pdf"
        )

        pdf.close()

    except:

        raise Exception(
            "Corrupted PDF"
        )

    uploaded_file.seek(0)

    return True