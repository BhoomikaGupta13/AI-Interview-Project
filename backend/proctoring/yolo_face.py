from ultralytics import YOLO


class FaceDetector:

    def __init__(self):

        self.model = YOLO("backend/proctoring/yolov8n-face.pt")

    def detect(self, img):

        result = self.model(img, verbose=False)[0]

        count = 0

        for box in result.boxes:

            if float(box.conf[0]) > 0.5:
                count += 1

        return count


detector = FaceDetector()
