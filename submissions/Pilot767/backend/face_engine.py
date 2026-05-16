import logging
import threading
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from config import EMBEDDINGS_DIR, MAX_FACES_PER_FRAME, MODELS_DIR, SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)

DET_MODEL = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
REC_MODEL = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

MODEL_URLS = {
    DET_MODEL: "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    REC_MODEL: "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


class FaceEngine:
    """Face detection + recognition via OpenCV Zoo (YuNet + SFace ONNX)."""

    def __init__(self) -> None:
        self._detector: cv2.FaceDetectorYN | None = None
        self._recognizer: cv2.FaceRecognizerSF | None = None
        self._embeddings: dict[int, np.ndarray] = {}
        self._lock = threading.Lock()

    def _ensure_models(self) -> None:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        for path, url in MODEL_URLS.items():
            if not path.exists():
                logger.info("Downloading model %s ...", path.name)
                urllib.request.urlretrieve(url, path)

    def _ensure_app(self) -> None:
        if self._detector is not None:
            return
        self._ensure_models()
        self._detector = cv2.FaceDetectorYN.create(str(DET_MODEL), "", (320, 320), 0.6, 0.3, 5000)
        self._recognizer = cv2.FaceRecognizerSF.create(str(REC_MODEL), "")
        logger.info("OpenCV face models loaded")

    def load_embedding(self, person_id: int, embedding_path: str | Path) -> None:
        path = Path(embedding_path)
        if path.exists():
            arr = np.load(path)
            with self._lock:
                self._embeddings[person_id] = arr

    def unload_person(self, person_id: int) -> None:
        with self._lock:
            self._embeddings.pop(person_id, None)

    def reload_all(self, entries: list[tuple[int, str | Path]]) -> None:
        with self._lock:
            self._embeddings.clear()
            for person_id, emb_path in entries:
                path = Path(emb_path)
                if path.exists():
                    self._embeddings[person_id] = np.load(path)

    def _largest_face_feature(self, img: np.ndarray) -> np.ndarray | None:
        self._ensure_app()
        assert self._detector is not None and self._recognizer is not None

        h, w = img.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(img)
        if faces is None or len(faces) == 0:
            return None

        best = max(faces, key=lambda f: f[2] * f[3])
        aligned = self._recognizer.alignCrop(img, best)
        feature = self._recognizer.feature(aligned)
        return feature.flatten().astype(np.float32)

    def extract_from_image_path(self, image_path: str | Path) -> np.ndarray | None:
        with self._lock:
            img = cv2.imread(str(image_path))
            if img is None:
                return None
            return self._largest_face_feature(img)

    def extract_from_frame(self, frame: np.ndarray) -> np.ndarray | None:
        with self._lock:
            return self._largest_face_feature(frame)

    def extract_features_for_all_faces(self, frame: np.ndarray) -> list[np.ndarray]:
        """Kadrdagi har bir aniqlangan yuz uchun embedding (katta yuzdan boshlab)."""
        with self._lock:
            self._ensure_app()
            assert self._detector is not None and self._recognizer is not None

            h, w = frame.shape[:2]
            self._detector.setInputSize((w, h))
            _, faces = self._detector.detect(frame)
            if faces is None or len(faces) == 0:
                return []

            rows = sorted(
                list(faces),
                key=lambda f: float(f[2]) * float(f[3]),
                reverse=True,
            )[: max(1, MAX_FACES_PER_FRAME)]

            out: list[np.ndarray] = []
            for row in rows:
                try:
                    aligned = self._recognizer.alignCrop(frame, row)
                    feature = self._recognizer.feature(aligned)
                    out.append(feature.flatten().astype(np.float32))
                except Exception as exc:
                    logger.debug("Face feature skipped: %s", exc)
                    continue
            return out

    def save_embedding(self, person_id: int, embedding: np.ndarray) -> Path:
        EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        path = EMBEDDINGS_DIR / f"{person_id}.npy"
        np.save(path, embedding)
        with self._lock:
            self._embeddings[person_id] = embedding
        return path

    def match(self, probe: np.ndarray) -> tuple[int | None, float]:
        with self._lock:
            self._ensure_app()
            assert self._recognizer is not None
            if not self._embeddings:
                return None, 0.0

            best_id = None
            best_score = -1.0
            probe_mat = probe.reshape(1, -1).astype(np.float32)

            for person_id, ref in self._embeddings.items():
                ref_mat = ref.reshape(1, -1).astype(np.float32)
                score = self._recognizer.match(
                    probe_mat,
                    ref_mat,
                    cv2.FaceRecognizerSF_FR_COSINE,
                )
                if score > best_score:
                    best_score = float(score)
                    best_id = person_id

            if best_score >= SIMILARITY_THRESHOLD:
                return best_id, best_score
            return None, best_score
