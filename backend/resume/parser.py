import fitz


def extract_text(
    resume_path
):

    document = fitz.open(
        resume_path
    )

    text = []

    for page in document:

        page_text = (
            page.get_text()
        )

        text.append(
            page_text
        )

    document.close()

    return "\n".join(
        text
    )