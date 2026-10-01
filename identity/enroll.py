# enroll.py
import getpass
import time
import numpy as np

from cameramgmt.camera   import Camera
from identity.detector   import FaceDetector
from identity.database   import FaceDatabase

from config   import FEED_URL, NUM_SAMPLES

MIN_FACE_SIZE    = 80
MAX_SIMILAR      = 0.85
INTER_CAPTURE_MS = 100

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    return float(np.dot(a, b))

def is_diverse_enough(new_emb: np.ndarray, captured: list[np.ndarray]) -> bool:
    return all(cosine_sim(new_emb, e) < MAX_SIMILAR for e in captured)

def main():
    username = input("Enter username: ").strip()
    password = getpass.getpass("Enter password: ")
    samples_input = input(f"Samples to capture [{NUM_SAMPLES}]: ").strip()
    num_samples = int(samples_input) if samples_input else NUM_SAMPLES

    camera   = Camera(FEED_URL)
    detector = FaceDetector(gpu=False)
    db       = FaceDatabase()

    camera.start()

    print("Waiting for camera feed …")
    while camera.read() is None:
        time.sleep(0.05)
    print("Camera ready. Stand in front of the camera …")

    captured: list[np.ndarray] = []
    last_time = 0.0

    while len(captured) < num_samples:
        frame = camera.read()
        if frame is None:
            continue

        now = time.time()
        if (now - last_time) < (INTER_CAPTURE_MS / 1000.0):
            continue
        last_time = now

        faces = detector.detect(frame)

        if not faces:
            print("No face detected.")
            continue

        if len(faces) > 1:
            print(f"Warning: {len(faces)} faces detected — using largest.")
        face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))

        # if len(faces) != 1:
        #     print("Make sure exactly ONE face is visible.")
        #     continue 
        # face = faces[0]
        x1, y1, x2, y2 = face.bbox.astype(int)

        if (x2 - x1) < MIN_FACE_SIZE:
            print("Move closer to the camera.")
            continue

        emb = face.embedding.astype("float32")

        if not is_diverse_enough(emb, captured):
            print("Hold still / vary pose slightly.")
            continue

        captured.append(emb)
        db.add_embedding(emb, username, password)
        print(f"Captured embedding {len(captured)}/{num_samples}")

    camera.stop()
    print("Enrollment complete.")


if __name__ == "__main__":
    main()