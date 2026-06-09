# backend/transcription/config.py
# Adapted from your working standalone config — paths changed to match
# the project's storage/ folder layout.

VIDEO_FOLDER      = "storage/recordings"
AUDIO_FOLDER      = "storage/audio"
TRANSCRIPT_FOLDER = "storage/transcripts"

# ── Model (same as your working version) ─────────────────────────────────────
# large-v3 works fine IF you have time/GPU.
# On CPU swap to "small" for faster results (~10x speedup, still good quality).
WHISPER_MODEL = "small"   # change to "small" for faster CPU transcription

DEVICE       = "cpu"   # "cuda" if you have a GPU
COMPUTE_TYPE = "int8"  # correct for CPU; use "float16" for CUDA

BEAM_SIZE = 5   # fine for large-v3; increase to 8-10 if still hallucinating (slower)

# Interviews are expected in English. Pinning the language avoids wrong-language
# hallucinations when the audio is quiet or short.
TRANSCRIPTION_LANGUAGE = "en"

# Audio enhancement before transcription. Keeps the raw extracted qN.wav, then
# creates qN_enhanced.wav for Whisper with speech-focused filtering.
ENHANCE_AUDIO_BEFORE_TRANSCRIPTION = True
ENHANCED_AUDIO_SAMPLE_RATE = 16000
ENHANCED_AUDIO_FILTER = (
    "highpass=f=80,"
    "lowpass=f=7600,"
    "afftdn=nf=-25,"
    "dynaudnorm=f=150:g=15,"
    "loudnorm=I=-18:TP=-1.5:LRA=11"
)

# Keep the full extracted audio for Whisper. WebRTC VAD can over-trim interview
# answers and produce empty/too-short files, so silence removal is optional.
REMOVE_SILENCE_BEFORE_TRANSCRIPTION = False

MIN_AUDIO_SIZE_MB = 0    # 0 = no lower bound (short answers are fine)
MAX_AUDIO_SIZE_MB = 500
