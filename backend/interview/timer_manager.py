import time


def countdown(

    seconds,

    placeholder,

    label

):

    for i in range(

        seconds,

        0,

        -1

    ):

        placeholder.write(

            f"{label}: {i}s"

        )

        time.sleep(1)

    placeholder.empty()