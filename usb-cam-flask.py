from flask import Flask, Response
import cv2

app = Flask(__name__)

def generate_frames():
    cap = cv2.VideoCapture(0)
    # Set lower resolution for better performance
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    # Set buffer size to minimum to reduce latency
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    while True:
        success, frame = cap.read()
        if not success:
            break
            
        # Reduce JPEG quality for faster encoding/transmission
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return '''
    <html>
    <head>
        <title>Live Stream from Raspberry Pi USB Camera</title>
        <style>
            body {
                margin: 0;
                padding: 0;
                width: 100vw;
                height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                background-color: #f0f0f0;
                font-family: Arial, sans-serif;
            }
            h2 {
                margin: 20px 0;
                color: #333;
            }
            .video-container {
                width: 100%;
                max-width: 1280px;
                height: auto;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            img {
                width: 100%;
                height: auto;
                max-height: 90vh;
                object-fit: contain;
            }
        </style>
    </head>
    <body>
        <div class="video-container" id="videoContainer">
            <img src="/video_feed" id="videoStream">
        </div>
        <button id="fullscreenBtn" style="position: fixed; top: 20px; right: 20px; z-index: 10; padding: 10px 20px; font-size: 16px;">Full Screen</button>
        <script>
            const videoContainer = document.getElementById('videoContainer');
            const fullscreenBtn = document.getElementById('fullscreenBtn');
            fullscreenBtn.addEventListener('click', () => {
                if (!document.fullscreenElement) {
                    videoContainer.requestFullscreen();
                } else {
                    document.exitFullscreen();
                }
            });
            document.addEventListener('fullscreenchange', () => {
                if (document.fullscreenElement) {
                    fullscreenBtn.textContent = 'Exit Full Screen';
                } else {
                    fullscreenBtn.textContent = 'Full Screen';
                }
            });
        </script>
    </body>
    </html>
    '''

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, threaded=True)

