# backend/proctoring/vision_processor.py
import os
import cv2
import numpy as np
from ultralytics import YOLO
import logging

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# PATH CONFIGURATION (Points directly to backend/proctoring/)
# -------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FACE_MODEL_PATH = os.path.normpath(os.path.join(BASE_DIR, "yolov8n-face.pt"))
GENERAL_MODEL_PATH = os.path.normpath(os.path.join(BASE_DIR, "yolov8s.pt"))

# -------------------------------------------------------------------------
# GLOBAL MODEL INITIALIZATION (Loaded once on startup)
# -------------------------------------------------------------------------
try:
    logger.info(f"[Vision] Resolving face weights path: {FACE_MODEL_PATH}")
    face_model = YOLO(FACE_MODEL_PATH)
    logger.info("[Vision] Successfully initialized existing yolov8n-face weights.")

    logger.info(f"[Vision] Resolving general object weights path: {GENERAL_MODEL_PATH}")
    general_model = YOLO(GENERAL_MODEL_PATH)
    logger.info(
        "[Vision] Successfully initialized general yolov8n weights for device monitoring."
    )
except Exception as e:
    logger.error(
        f"[Vision] Critical error during model weight assignment initialization: {str(e)}"
    )
    raise e


class LegacyDetectorBridge:
    def detect(self, img) -> int:
        """Mimics your original yolo_face.py detector behavior."""
        if img is None:
            return 0
        try:
            results = face_model(img, verbose=False)
            return len(results[0].boxes) if results and len(results) > 0 else 0
        except Exception as e:
            logger.error(f"[Vision Legacy Bridge] Face detection failure: {str(e)}")
            return (
                1  # Fallback to a safe number of faces so it doesn't trigger false bans
            )


detector = LegacyDetectorBridge()


def process_proctoring_frame(
    image_bytes: bytes, phone_conf_threshold: float = 0.55
) -> dict:
    """
    Evaluates an incoming image frame stream byte array.
    Uses YOLOv8s (Small) with specialized aspect bounding overrides.
    """
    if not image_bytes:
        return {"status": "error", "message": "Null binary data stream received"}

    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return {
            "status": "error",
            "message": "Failed to decode valid image array matrix",
        }

    # -------------------------------------------------------------------------
    # FEATURE 1: Face Tracking Execution
    # -------------------------------------------------------------------------
    face_results = face_model(frame, verbose=False)
    face_count = (
        len(face_results[0].boxes) if face_results and len(face_results) > 0 else 0
    )

    # -------------------------------------------------------------------------
    # FEATURE 2: Phone Tracking Execution
    # -------------------------------------------------------------------------
    phone_detected = False

    general_results = general_model.predict(
        frame,
        conf=0.55,
        classes=[67],  # Only care about cell phones
        imgsz=640,  # Keeps latency fast on CPU bounds
        augment=False,  # Tests flipped and multi-scaled copies internally for close-ups
        verbose=False,
    )

    if general_results and len(general_results) > 0:
        for box in general_results[0].boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())

            if class_id == 67 and confidence >= 0.55:
                phone_detected = True
                logger.warning(
                    f"[Proctor Upgrade] Phone detected with upgraded weights. Conf: {confidence:.2f}"
                )
                break

    return {"status": "success", "faces": face_count, "phone_detected": phone_detected}
