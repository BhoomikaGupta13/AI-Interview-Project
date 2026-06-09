from streamlit_webrtc import webrtc_streamer
from pathlib import Path

import av
import fractions


RECORD_DIR = Path(
    "storage/recordings"
)

RECORD_DIR.mkdir(

    parents=True,

    exist_ok=True

)


class VideoRecorder:

    def __init__(

        self,

        session_id,

        question_no

    ):

        self.session=session_id

        self.question=question_no

        self.container=None

        self.video_stream=None

        self.audio_stream=None

        self.closed=False

    def start(self):

        folder=(

            RECORD_DIR/

            self.session

        )

        folder.mkdir(

            exist_ok=True

        )

        path=(

            folder/

            f"q{self.question}.webm"

        )

        self.container=av.open(

            str(path),

            mode="w"

        )

        self.video_stream=(

            self.container.add_stream(

                "vp8",

                rate=30

            )

        )

        self.video_stream.width=640

        self.video_stream.height=480

        self.video_stream.pix_fmt="yuv420p"

        self.video_stream.time_base=(

            fractions.Fraction(

                1,

                30

            )

        )

        self.audio_stream=(

            self.container.add_stream(

                "opus",

                rate=48000

            )

        )

        self.closed=False

    def write_video(

        self,

        frame

    ):

        if (

            self.closed

            or

            self.container is None

        ):

            return

        try:

            packets=(

                self.video_stream.encode(

                    frame

                )

            )

            for p in packets:

                self.container.mux(

                    p

                )

        except:

            pass

    def write_audio(

        self,

        frame

    ):

        if (

            self.closed

            or

            self.container is None

        ):

            return

        try:

            packets=(

                self.audio_stream.encode(

                    frame

                )

            )

            for p in packets:

                self.container.mux(

                    p

                )

        except:

            pass

    def stop(self):

        if self.closed:

            return

        try:

            if self.video_stream:

                packets=(

                    self.video_stream.encode(

                        None

                    )

                )

                for p in packets:

                    self.container.mux(

                        p

                    )

        except:

            pass

        try:

            if self.audio_stream:

                packets=(

                    self.audio_stream.encode(

                        None

                    )

                )

                for p in packets:

                    self.container.mux(

                        p

                    )

        except:

            pass

        try:

            if self.container:

                self.container.close()

        except:

            pass

        self.closed=True


def initialize_camera():

    ctx=webrtc_streamer(

        key="persistent_camera",

        rtc_configuration={

            "iceServers":[

                {

                    "urls":[

                        "stun:stun.l.google.com:19302"

                    ]

                }

            ]

        },

        media_stream_constraints={

            "video":True,

            "audio":True

        },

        async_processing=True

    )

    return ctx