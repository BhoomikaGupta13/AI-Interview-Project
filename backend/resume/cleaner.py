import re


def clean_resume(text):

    text = re.sub(r"\n+", "\n", text)

    text = re.sub(r"\s+", " ", text)

    text = text.strip()

    return text
