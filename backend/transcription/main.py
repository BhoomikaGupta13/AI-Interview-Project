import json
import os
import re
import time
import traceback
import wave
from pathlib import Path

import ffmpeg
from faster_whisper import WhisperModel

from .config import *

try:
    import webrtcvad
except ImportError:
    webrtcvad = None


Path(AUDIO_FOLDER).mkdir(parents=True, exist_ok=True)
Path(TRANSCRIPT_FOLDER).mkdir(parents=True, exist_ok=True)


class InterviewPipeline:
    def __init__(self):
        print("Loading Whisper...")

        self.model = WhisperModel(
            WHISPER_MODEL,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
        )
        self.vad = webrtcvad.Vad(2) if webrtcvad is not None else None

        print("Model Loaded")

    def _session_audio_dir(self, session_id: str | None) -> Path:
        folder = Path(AUDIO_FOLDER)
        if session_id:
            folder = folder / session_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _session_transcript_dir(self, session_id: str | None) -> Path:
        folder = Path(TRANSCRIPT_FOLDER)
        if session_id:
            folder = folder / session_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _load_proctoring(self, session_id: str) -> dict:
        path = Path("storage/proctoring") / f"{session_id}.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"error": f"Invalid proctoring JSON: {path}"}

    def validate_video(self, video_path):
        video_path = Path(video_path)
        allowed = [".mp4", ".mov", ".mkv", ".webm"]

        if video_path.suffix.lower() not in allowed:
            raise Exception(f"Unsupported format: {video_path.suffix}")

        size = video_path.stat().st_size
        size_mb = size / (1024 * 1024)

        if size_mb > MAX_AUDIO_SIZE_MB:
            raise Exception(f"Video too large: {round(size_mb, 2)} MB")

        if size < 512:
            raise Exception(
                "Recording file is empty. Make sure FastAPI server.py was running "
                "and browser camera/microphone permissions were allowed."
            )

        print("Validation Passed:", video_path)

    def wait_for_recordings(
        self,
        folder: Path,
        expected_count: int | None = None,
        stable_checks: int = 2,
        delay: float = 1.0,
    ):
        """
        Wait briefly for the browser's final MediaRecorder chunk upload to finish.
        This avoids starting ffmpeg while q*.webm is still being appended.
        """
        stable_count = 0
        previous_sizes = None

        for _ in range(12):
            files = sorted(folder.glob("q*.webm"))
            sizes = {file.name: file.stat().st_size for file in files}

            has_expected_files = expected_count is None or len(files) >= expected_count
            if sizes and has_expected_files and sizes == previous_sizes:
                stable_count += 1
                if stable_count >= stable_checks:
                    return
            else:
                stable_count = 0

            previous_sizes = sizes
            time.sleep(delay)

    def extract_audio(self, video_path, session_id: str | None = None):
        video_path = Path(video_path)
        audio_path = self._session_audio_dir(session_id) / f"{video_path.stem}.wav"
        stale_clean_path = audio_path.with_name(f"{audio_path.stem}_clean.wav")
        if not REMOVE_SILENCE_BEFORE_TRANSCRIPTION and stale_clean_path.exists():
            stale_clean_path.unlink()

        try:
            (
                ffmpeg
                .input(str(video_path))
                .output(
                    str(audio_path),
                    ac=1,
                    ar=16000,
                    acodec="pcm_s16le",
                    vn=None,
                )
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else str(exc)
            raise Exception(f"ffmpeg audio extraction failed for {video_path}:\n{stderr}") from exc

        if not audio_path.exists() or audio_path.stat().st_size < 512:
            raise Exception(f"Audio extraction produced an empty file: {audio_path}")

        print("Audio Extracted:", audio_path)
        return str(audio_path)

    def enhance_audio(self, wav_path):
        wav_path = Path(wav_path)
        enhanced_path = wav_path.with_name(f"{wav_path.stem}_enhanced.wav")

        try:
            (
                ffmpeg
                .input(str(wav_path))
                .output(
                    str(enhanced_path),
                    ac=1,
                    ar=ENHANCED_AUDIO_SAMPLE_RATE,
                    acodec="pcm_s16le",
                    af=ENHANCED_AUDIO_FILTER,
                )
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else str(exc)
            print(f"Audio enhancement failed; using raw WAV.\n{stderr}")
            return str(wav_path)

        if not enhanced_path.exists() or enhanced_path.stat().st_size < 512:
            print("Enhanced WAV is empty; using raw WAV")
            return str(wav_path)

        print("Audio Enhanced:", enhanced_path)
        return str(enhanced_path)

    def prepare_audio_for_transcription(self, audio_path):
        prepared = self.enhance_audio(audio_path) if ENHANCE_AUDIO_BEFORE_TRANSCRIPTION else audio_path
        if REMOVE_SILENCE_BEFORE_TRANSCRIPTION:
            prepared = self.remove_silence(prepared)
        return prepared

    def remove_silence(self, wav_path):
        wav_path = Path(wav_path)

        if self.vad is None:
            print("WebRTC VAD is unavailable; using original WAV")
            return str(wav_path)

        with wave.open(str(wav_path), "rb") as wave_file:
            frames = wave_file.readframes(wave_file.getnframes())
            sample_rate = wave_file.getframerate()
            channels = wave_file.getnchannels()
            sample_width = wave_file.getsampwidth()

        if channels != 1 or sample_width != 2 or sample_rate not in [8000, 16000, 32000, 48000]:
            print("WAV format is not VAD-compatible; using original WAV")
            return str(wav_path)

        frame_duration = 30
        frame_size = int(sample_rate * frame_duration / 1000 * sample_width)
        voiced = []

        for i in range(0, len(frames), frame_size):
            chunk = frames[i:i + frame_size]
            if len(chunk) < frame_size:
                break
            if self.vad.is_speech(chunk, sample_rate):
                voiced.append(chunk)

        if not voiced:
            print("No voiced frames found; using original WAV")
            return str(wav_path)

        cleaned = wav_path.with_name(f"{wav_path.stem}_clean.wav")
        with wave.open(str(cleaned), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(sample_width)
            out.setframerate(sample_rate)
            out.writeframes(b"".join(voiced))

        print("Silence Removed:", cleaned)
        if not cleaned.exists() or cleaned.stat().st_size < 512:
            print("Cleaned WAV is empty; using original WAV")
            return str(wav_path)

        return str(cleaned)

    def transcribe(self, audio_path):
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=BEAM_SIZE,
            word_timestamps=True,
            language=TRANSCRIPTION_LANGUAGE,
            condition_on_previous_text=False,
            temperature=0.0,
            vad_filter=False,
        )

        transcript = []
        full_text = []

        for seg in segments:
            text = seg.text.strip()
            data = {
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": text,
            }
            transcript.append(data)
            if text:
                full_text.append(text)

        return transcript, " ".join(full_text), info.language

    def save(
        self,
        transcript,
        full_text,
        language,
        name,
        session_id: str | None = None,
        metadata: dict | None = None,
    ):
        transcript_dir = self._session_transcript_dir(session_id)
        txt_path = transcript_dir / f"{name}.txt"
        json_path = transcript_dir / f"{name}.json"

        txt_path.write_text(full_text, encoding="utf8")

        structured = {
            "session_id": session_id,
            "question": name,
            "language": language,
            "full_text": full_text,
            "transcript": transcript,
        }
        if metadata:
            structured.update(metadata)

        json_path.write_text(
            json.dumps(structured, indent=4),
            encoding="utf8",
        )

        print("Saved Successfully:", json_path)
        return str(txt_path), str(json_path)

    def process(self, video_path):
        self.validate_video(video_path)
        audio = self.extract_audio(video_path)
        prepared = self.prepare_audio_for_transcription(audio)
        structured, text, lang = self.transcribe(prepared)
        name = Path(video_path).stem
        txt_path, json_path = self.save(
            structured,
            text,
            lang,
            name,
            metadata={
                "video_path": str(video_path),
                "audio_path": audio,
                "transcription_audio_path": prepared,
            },
        )
        print("\nDone")
        return {
            "status": "success",
            "full_text": text,
            "language": lang,
            "txt_path": txt_path,
            "json_path": json_path,
            "audio_path": audio,
            "transcription_audio_path": prepared,
        }

    def process_session(self, session_id: str) -> list:
        """
        Convert storage/recordings/<session_id>/q*.webm into:
          storage/audio/<session_id>/q*.wav
          storage/audio/<session_id>/q*_clean.wav
          storage/transcripts/<session_id>/q*.txt
          storage/transcripts/<session_id>/q*.json
          storage/transcripts/<session_id>/summary.txt
          storage/transcripts/<session_id>/manifest.json
        """
        folder = Path(VIDEO_FOLDER) / session_id
        transcript_dir = self._session_transcript_dir(session_id)
        session_path = Path("storage/sessions") / f"{session_id}.json"

        if not session_path.exists():
            raise FileNotFoundError(f"Session file not found: {session_path}")

        session = json.loads(session_path.read_text(encoding="utf-8"))
        questions = session.get("questions", [])
        folder.mkdir(parents=True, exist_ok=True)
        expected_count = (
            len(questions) if session.get("status") == "COMPLETED" else None
        )
        self.wait_for_recordings(folder, expected_count=expected_count)

        def q_num(path: Path):
            match = re.fullmatch(r"q(\d+)\.webm", path.name, re.IGNORECASE)
            return int(match.group(1)) if match else 0

        webm_files = sorted(folder.glob("q*.webm"), key=q_num)

        results = []
        proctoring = self._load_proctoring(session_id)
        proctor_flags = proctoring.get("flags", [])

        for video_path in webm_files:
            q_no = q_num(video_path)
            print(f"\nProcessing {video_path.name}")

            try:
                self.validate_video(video_path)

                audio = self.extract_audio(video_path, session_id=session_id)
                prepared = self.prepare_audio_for_transcription(audio)
                structured, full_text, language = self.transcribe(prepared)
                question_flags = [
                    flag for flag in proctor_flags
                    if str(flag.get("question")) == str(q_no)
                ]

                txt_path, json_path = self.save(
                    structured,
                    full_text,
                    language,
                    name=f"q{q_no}",
                    session_id=session_id,
                    metadata={
                        "question_no": q_no,
                        "video_path": str(video_path),
                        "audio_path": audio,
                        "transcription_audio_path": prepared,
                        "proctor_flags": question_flags,
                    },
                )

                results.append({
                    "question_no": q_no,
                    "status": "success",
                    "full_text": full_text,
                    "language": language,
                    "video_path": str(video_path),
                    "audio_path": audio,
                    "transcription_audio_path": prepared,
                    "proctor_flags": question_flags,
                    "txt_path": txt_path,
                    "json_path": json_path,
                })

            except Exception:
                err = traceback.format_exc()
                print(f"ERROR on {video_path.name}:\n{err}")
                results.append({
                    "question_no": q_no,
                    "status": "error",
                    "video_path": str(video_path),
                    "error": err,
                })

        summary_path = transcript_dir / "summary.txt"
        with summary_path.open("w", encoding="utf-8") as f:
            f.write(f"Session: {session_id}\n{'=' * 60}\n")
            if proctoring:
                f.write(
                    "\nProctoring:\n"
                    f"  Fullscreen warnings: {proctoring.get('fullscreen_warnings', 0)}\n"
                    f"  Tab warnings: {proctoring.get('tab_warnings', 0)}\n"
                    f"  Face flags: {proctoring.get('face_warnings', 0)}\n"
                    f"  Locked: {proctoring.get('locked', False)}\n"
                )
            for result in results:
                q_no = result["question_no"]
                if result["status"] == "success":
                    f.write(f"\nQ{q_no}:\n{result['full_text']}\n")
                    if result.get("proctor_flags"):
                        f.write(f"[PROCTOR FLAGS] {json.dumps(result['proctor_flags'])}\n")
                else:
                    f.write(f"\nQ{q_no}: [ERROR]\n{result.get('error', '')}\n")

        manifest = {
            "session_id": session_id,
            "recording_dir": str(folder),
            "audio_dir": str(self._session_audio_dir(session_id)),
            "transcript_dir": str(transcript_dir),
            "summary_path": str(summary_path),
            "proctoring": proctoring,
            "results": results,
        }
        manifest_path = transcript_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=4), encoding="utf-8")

        answers_by_question = {
            item["question_no"]: item.get("full_text", "")
            for item in results
            if item.get("status") == "success"
        }
        combined_answers = [
            {
                "question": question,
                "Answer": answers_by_question.get(question_no, ""),
            }
            for question_no, question in enumerate(questions, start=1)
        ]
        (transcript_dir / "combined_answers.json").write_text(
            json.dumps(combined_answers, indent=4),
            encoding="utf-8",
        )

        ok = sum(1 for result in results if result["status"] == "success")
        print(f"\nSession {session_id} done: {ok}/{len(results)} transcribed.")
        return results


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    pipeline = InterviewPipeline()
    if len(sys.argv) == 2:
        results = pipeline.process_session(sys.argv[1])
        for result in results:
            q_no = result["question_no"]
            if result["status"] == "success":
                print(f"\nQ{q_no}: {result['full_text'][:200]}")
            else:
                print(f"\nQ{q_no}: ERROR - {result['error'][:300]}")
    elif len(sys.argv) == 3 and sys.argv[1] == "--file":
        pipeline.process(sys.argv[2])
    else:
        print(
            "Usage:\n"
            "  python -m backend.transcription.main <session_id>\n"
            "  python -m backend.transcription.main --file <video.webm>"
        )
