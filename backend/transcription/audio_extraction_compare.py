from pathlib import Path
import ffmpeg

from faster_whisper import WhisperModel


class AudioExtractionTester:

    def __init__(self):

        print("Loading Whisper...")

        self.model = WhisperModel("small", device="cpu", compute_type="int8")

        print("Whisper Ready")

    def extract_standard(self, video_path, output_path):

        (
            ffmpeg.input(str(video_path))
            .output(str(output_path), ac=1, ar=16000, acodec="pcm_s16le", vn=None)
            .overwrite_output()
            .run(quiet=True)
        )

    def extract_high_quality(self, video_path, output_path):

        (
            ffmpeg.input(str(video_path))
            .output(str(output_path), ac=2, ar=48000, acodec="pcm_s24le", vn=None)
            .overwrite_output()
            .run(quiet=True)
        )

    def transcribe(self, wav_path):

        segments, info = self.model.transcribe(
            str(wav_path),
            beam_size=5,
            language="en",
            condition_on_previous_text=False,
            temperature=0.0,
            vad_filter=False,
        )

        text = []

        for seg in segments:

            t = seg.text.strip()

            if t:

                text.append(t)

        return " ".join(text)


if __name__ == "__main__":

    import json, re

    tester = AudioExtractionTester()

    session = input("Enter session id: ").strip()

    folder = Path("storage/recordings") / session

    if not folder.exists():
        print("Session not found")
        exit()

    session_file = Path("storage/sessions") / f"{session}.json"

    question_map = {}

    if session_file.exists():

        data = json.loads(session_file.read_text(encoding="utf8"))

        for i, q in enumerate(data.get("questions", []), 1):

            question_map[f"q{i}"] = q

    output = Path("audio_test_outputs") / session

    output.mkdir(parents=True, exist_ok=True)

    videos = sorted(
        folder.glob("q*.webm"), key=lambda x: int(re.findall(r"\d+", x.stem)[0])
    )

    final = []

    for video in videos:

        q = video.stem

        print("\nProcessing", q)

        s_audio = output / f"{q}_standard.wav"
        h_audio = output / f"{q}_hq.wav"

        tester.extract_standard(video, s_audio)

        tester.extract_high_quality(video, h_audio)

        s_text = tester.transcribe(s_audio)

        h_text = tester.transcribe(h_audio)

        (output / f"{q}_standard.txt").write_text(s_text, encoding="utf8")

        (output / f"{q}_hq.txt").write_text(h_text, encoding="utf8")

        final.append({"question": question_map.get(q, q), "Answer": h_text})

    (output / "combined_answers.json").write_text(
        json.dumps(final, indent=4), encoding="utf8"
    )

    print("\nDone")
    print(output)


# python backend/transcription/audio_extraction_compare.py
