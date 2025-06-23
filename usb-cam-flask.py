import time, cv2
from flask import Flask, Response

app = Flask(__name__)

def generate_frames():
    # Force V4L2 backend & MJPG compression
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)      # 640×480 keeps USB happy
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        raise RuntimeError("❌ Could not open camera")

    # Simple FPS monitor
    frames = 0
    t0 = time.time()

    while True:
        # Flush buffer so we always take the *latest* frame
        cap.grab()                 # skip any queued frames
        success, frame = cap.retrieve()
        if not success:
            break

        frames += 1
        if frames == 120:          # every 4 s @30 fps
            print(f"🔥 real FPS = {frames/(time.time()-t0):.1f}")
            t0, frames = time.time(), 0

        _, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
               buf.tobytes() + b"\r\n")

@app.route("/")
def index():
    return "<img src='/video_feed'>"

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    # Use threaded=False; Flask’s threaded server can starve the grab loop
    app.run(host="0.0.0.0", port=8080, threaded=False)
