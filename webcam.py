import argparse
import asyncio
import json
import logging
import os
import platform
import ssl
import uuid
import time
import av
import cv2
from fractions import Fraction
from aiohttp import web
from aiohttp_cors import setup as cors_setup, ResourceOptions, CorsViewMixin
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, RTCIceCandidate
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc.mediastreams import MediaStreamTrack
from aiortc.rtcrtpsender import RTCRtpSender
from datetime import datetime
import threading

ROOT = os.path.dirname(__file__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Connection tracking
connection_stats = {}

# Frame grabber thread globals
latest_frame = None
frame_lock = threading.Lock()
frame_grabber_running = True

# Recording globals
recording_running = True
recording_thread = None
current_recording = None
recording_lock = threading.Lock()

class ConnectionDiagnostics:
    def __init__(self, pc_id):
        self.pc_id = pc_id
        self.start_time = datetime.now()
        self.ice_candidates = []
        self.connection_attempts = 0
        self.last_state = None
        self.last_ice_state = None
        self.last_signaling_state = None
        self.errors = []

    def log_state_change(self, state_type, new_state):
        timestamp = datetime.now()
        if state_type == "connection":
            self.last_state = new_state
        elif state_type == "ice":
            self.last_ice_state = new_state
        elif state_type == "signaling":
            self.last_signaling_state = new_state
        
        logger.info(f"PC {self.pc_id} - {state_type} state changed to {new_state} at {timestamp}")

    def log_error(self, error):
        self.errors.append({
            "timestamp": datetime.now(),
            "error": str(error)
        })
        logger.error(f"PC {self.pc_id} - Error: {error}")

    def get_stats(self):
        return {
            "pc_id": self.pc_id,
            "uptime": (datetime.now() - self.start_time).total_seconds(),
            "connection_attempts": self.connection_attempts,
            "current_states": {
                "connection": self.last_state,
                "ice": self.last_ice_state,
                "signaling": self.last_signaling_state
            },
            "ice_candidates": len(self.ice_candidates),
            "errors": self.errors
        }

class VideoRecorder:
    def __init__(self, filename, fps=30, width=960, height=540, preferred_codec="auto"):
        self.filename = filename
        self.fps = fps
        self.width = width
        self.height = height
        
        # Try different codecs based on platform with better error handling
        self.fourcc = None
        if platform.system() == "Windows":
            # Define codec preferences based on user choice
            if preferred_codec == "auto":
                codecs_to_try = [
                    ('mp4v', 'mp4v'),
                    ('XVID', 'avi'),  # Fallback to AVI with XVID
                    ('MJPG', 'avi'),  # Another AVI option
                    ('H264', 'mp4')   # Last resort H264
                ]
            elif preferred_codec == "mp4v":
                codecs_to_try = [('mp4v', 'mp4v')]
            elif preferred_codec == "xvid":
                codecs_to_try = [('XVID', 'avi'), ('mp4v', 'mp4v')]
            elif preferred_codec == "mjpg":
                codecs_to_try = [('MJPG', 'avi'), ('mp4v', 'mp4v')]
            elif preferred_codec == "h264":
                codecs_to_try = [('H264', 'mp4'), ('mp4v', 'mp4v')]
            else:
                codecs_to_try = [('mp4v', 'mp4v')]
            
            for codec_name, extension in codecs_to_try:
                try:
                    test_filename = f"test.{extension}"
                    test_fourcc = cv2.VideoWriter_fourcc(*codec_name)
                    test_writer = cv2.VideoWriter(test_filename, test_fourcc, fps, (width, height))
                    if test_writer.isOpened():
                        test_writer.release()
                        if os.path.exists(test_filename):
                            os.remove(test_filename)
                        self.fourcc = test_fourcc
                        # Update filename extension if needed
                        if extension != 'mp4':
                            base_name = os.path.splitext(filename)[0]
                            self.filename = f"{base_name}.{extension}"
                        logger.info(f"Using codec: {codec_name} for recording")
                        break
                    else:
                        test_writer.release()
                except Exception as e:
                    logger.debug(f"Codec {codec_name} failed: {e}")
                    continue
            
            if self.fourcc is None:
                # Ultimate fallback - use default
                self.fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                logger.warning("All codecs failed, using default mp4v")
        else:
            # Linux/Mac - use MP4V
            self.fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        self.out = None
        self.frame_count = 0
        self.start_time = time.time()
        
    def start(self):
        try:
            self.out = cv2.VideoWriter(self.filename, self.fourcc, self.fps, (self.width, self.height))
            if not self.out.isOpened():
                logger.error(f"Failed to open video writer for {self.filename}")
                return False
            logger.info(f"Started recording: {self.filename}")
            return True
        except Exception as e:
            logger.error(f"Error starting recording {self.filename}: {e}")
            return False
    
    def write_frame(self, frame):
        if self.out and self.out.isOpened():
            try:
                # Resize frame if needed
                if frame.shape[1] != self.width or frame.shape[0] != self.height:
                    frame = cv2.resize(frame, (self.width, self.height))
                self.out.write(frame)
                self.frame_count += 1
                return True
            except Exception as e:
                logger.error(f"Error writing frame to {self.filename}: {e}")
                return False
        return False
    
    def stop(self):
        if self.out:
            try:
                self.out.release()
                duration = time.time() - self.start_time
                logger.info(f"Stopped recording: {self.filename} (Duration: {duration:.2f}s, Frames: {self.frame_count})")
                return True
            except Exception as e:
                logger.error(f"Error stopping recording {self.filename}: {e}")
                return False
        return False

def recording_worker():
    global current_recording, recording_running, preferred_codec
    
    # Create video directory if it doesn't exist
    video_dir = os.path.join(ROOT, "video")
    os.makedirs(video_dir, exist_ok=True)
    
    while recording_running:
        try:
            # Create new recording file with timestamp in video folder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Default to mp4, but VideoRecorder will adjust extension if needed
            filename = os.path.join(video_dir, f"recording_{timestamp}.mp4")
            
            # Start new recording
            with recording_lock:
                if current_recording:
                    current_recording.stop()
                # Pass the preferred codec from command line args
                current_recording = VideoRecorder(filename, preferred_codec=preferred_codec)
                if not current_recording.start():
                    logger.error("Failed to start new recording")
                    continue
            
            # Record for 1 minute (60 seconds)
            start_time = time.time()
            while recording_running and (time.time() - start_time) < 60:
                with frame_lock:
                    frame = None if latest_frame is None else latest_frame.copy()
                
                if frame is not None:
                    with recording_lock:
                        if current_recording:
                            current_recording.write_frame(frame)
                
                time.sleep(0.033)  # ~30 FPS

            
            # Stop current recording
            with recording_lock:
                if current_recording:
                    current_recording.stop()
                    current_recording = None
                    
        except Exception as e:
            logger.error(f"Error in recording worker: {e}")
            time.sleep(1)  # Wait before retrying

relay = None
webcam = None
cap = None
pcs = {}

def initialize_camera():
    global cap
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)  # Explicitly use V4L2 backend
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))  # Force MJPG for high FPS
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print("✅ Camera initialized: 640x480 MJPG @30 FPS")
            return True
        else:
            print("❌ Failed to open camera.")
            return False
    except Exception as e:
        print(f"❌ Error initializing camera: {e}")
        if cap is not None:
            cap.release()
        return False

def frame_grabber():
    global latest_frame, frame_grabber_running
    frame_count = 0
    t0 = time.time()
    while frame_grabber_running:
        if cap is not None and cap.isOpened():
            # Flush stale frames
            cap.grab()
            success, frame = cap.retrieve()
            if success and frame is not None:
                with frame_lock:
                    latest_frame = frame.copy()
                frame_count += 1

            # Show real FPS every 5 seconds
            if time.time() - t0 >= 5:
                fps = frame_count / (time.time() - t0)
                print(f"[FrameGrabber] Real FPS: {fps:.1f}")
                frame_count = 0
                t0 = time.time()
        time.sleep(0.001)

# Start the frame grabber thread after camera initialization
if not initialize_camera():
    print("Warning: No camera available. The application will not be able to stream video.")
else:
    grabber_thread = threading.Thread(target=frame_grabber, daemon=True)
    grabber_thread.start()
    
    # Start the recording thread only if recording is enabled
    if recording_running:
        recording_thread = threading.Thread(target=recording_worker, daemon=True)
        recording_thread.start()
        logger.info("Recording thread started - will create 1-minute video files with timestamps")
    else:
        logger.info("Recording disabled - no recording thread started")

class WebcamTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._retry_count = 0
        self._max_retries = 3

    async def recv(self):
        global latest_frame
        while True:
            with frame_lock:
                frame = None if latest_frame is None else latest_frame.copy()
            if frame is not None:
                frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
                frame_rgba = frame_rgba.astype('uint8')
                pts = time.time() * 1000000
                new_frame = av.VideoFrame.from_ndarray(frame_rgba, format='rgba')
                new_frame.pts = int(pts)
                new_frame.time_base = Fraction(1, 1000000)
                return new_frame
            await asyncio.sleep(0.005)  # Slight delay while waiting


async def index(request):
    content = open(os.path.join(ROOT, "client.html"), "r").read()
    return web.Response(content_type="text/html", text=content)

async def webrtc(request):
    if request.method == "GET":
        # Handle GET request
        return web.Response(
            content_type="application/json",
            text=json.dumps({"status": "ready"}, ensure_ascii=False)
        )
    
    params = await request.json()
    if params["type"] == "request":
        # Configure STUN/TURN servers with TURN support
        configuration = RTCConfiguration(
            iceServers=[
                RTCIceServer(
                    urls=[
                        "stun:stun.l.google.com:19302",
                        "stun:stun1.l.google.com:19302",
                        "stun:stun2.l.google.com:19302",
                        "stun:stun3.l.google.com:19302",
                        "stun:stun4.l.google.com:19302"
                    ]
                ),
                RTCIceServer(
                    urls=[
                        "turn:openrelay.metered.ca:80",
                        "turn:openrelay.metered.ca:443",
                        "turn:openrelay.metered.ca:443?transport=tcp"
                    ],
                    username="openrelayproject",
                    credential="openrelayproject"
                ),
                RTCIceServer(
                    urls=[
                        "turn:numb.viagenie.ca",
                        "stun:numb.viagenie.ca"
                    ],
                    username="webrtc@live.com",
                    credential="muazkh"
                ),
                # Add more reliable TURN servers
                RTCIceServer(
                    urls=[
                        "turn:turn.anyfirewall.com:443?transport=tcp",
                        "turn:turn.anyfirewall.com:443?transport=udp"
                    ],
                    username="webrtc",
                    credential="webrtc"
                ),
                RTCIceServer(
                    urls=[
                        "turn:turn.bistri.com:80",
                        "turn:turn.bistri.com:443"
                    ],
                    username="homeo",
                    credential="homeo"
                )
            ]
        )
        
        pc = RTCPeerConnection(configuration)
        pc_id = "PeerConnection(%s)" % uuid.uuid4()
        pcs[pc_id] = pc
        
        # Initialize diagnostics
        diag = ConnectionDiagnostics(pc_id)
        connection_stats[pc_id] = diag

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            diag.log_state_change("connection", pc.connectionState)
            logger.info(f"Connection state changed to: {pc.connectionState}")
            if pc.connectionState == "failed":
                diag.connection_attempts += 1
                logger.warning(f"Connection failed (attempt {diag.connection_attempts})")
                # Log current ICE and signaling states
                logger.warning(f"Current ICE state: {pc.iceConnectionState}")
                logger.warning(f"Current signaling state: {pc.signalingState}")
                if diag.connection_attempts < 3:  # Try up to 3 times
                    try:
                        logger.info("Attempting to restart ICE...")
                        # Create new offer to restart ICE
                        offer = await pc.createOffer()
                        await pc.setLocalDescription(offer)
                    except Exception as e:
                        diag.log_error(f"Failed to restart ICE: {e}")
                        await pc.close()
                else:
                    logger.error("Max connection attempts reached")
                    await pc.close()

        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            diag.log_state_change("ice", pc.iceConnectionState)
            logger.info(f"ICE connection state changed to: {pc.iceConnectionState}")
            if pc.iceConnectionState == "disconnected":
                logger.warning("ICE disconnected, attempting to restart...")
                try:
                    # Create new offer to restart ICE
                    offer = await pc.createOffer()
                    await pc.setLocalDescription(offer)
                except Exception as e:
                    diag.log_error(f"Failed to restart ICE: {e}")

        @pc.on("icegatheringstatechange")
        async def on_icegatheringstatechange():
            diag.log_state_change("ice", pc.iceGatheringState)
            logger.info(f"ICE gathering state changed to: {pc.iceGatheringState}")

        @pc.on("signalingstatechange")
        async def on_signalingstatechange():
            diag.log_state_change("signaling", pc.signalingState)

        @pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                diag.ice_candidates.append({
                    "timestamp": datetime.now(),
                    "candidate": str(candidate)
                })
                logger.info(f"New ICE candidate: {candidate}")

        webcam = WebcamTrack()
        pc.addTrack(webcam)
        
        try:
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)

            # Wait for ICE gathering to complete with timeout
            try:
                async with asyncio.timeout(10):  # 10 second timeout
                    while True:
                        if pc.iceGatheringState == "complete":
                            break
                        await asyncio.sleep(0.1)
            except asyncio.TimeoutError:
                logger.warning("ICE gathering timed out, proceeding with available candidates")

            return web.Response(
                content_type="application/json",
                text=json.dumps({
                    "sdp": pc.localDescription.sdp,
                    "type": pc.localDescription.type,
                    "id": pc_id,
                    "iceServers": [{"urls": server.urls, "username": getattr(server, "username", None), "credential": getattr(server, "credential", None)} for server in (configuration.iceServers or [])],
                    "diagnostics": diag.get_stats()
                }, ensure_ascii=False)
            )
        except Exception as e:
            diag.log_error(f"Error creating offer: {e}")
            raise
    elif params["type"] == "answer":
        pc = pcs[params["id"]]

        if not pc:
            return web.Response(
                content_type="application/json",
                text=json.dumps({"error": "Peer connection not found"}, ensure_ascii=False)
            )
            
        await pc.setRemoteDescription(RTCSessionDescription(sdp=params["sdp"], type=params["type"]))

        return web.Response(
            content_type="application/json",
            text=json.dumps({"status": "success"}, ensure_ascii=False)
        )
    
    # Default response for unhandled cases
    return web.Response(
        content_type="application/json",
        text=json.dumps({"error": "Invalid request type"}, ensure_ascii=False),
        status=400
    )

async def get_diagnostics(request):
    """Endpoint to get connection diagnostics"""
    pc_id = request.query.get('id')
    if pc_id and pc_id in connection_stats:
        return web.Response(
            content_type="application/json",
            text=json.dumps(connection_stats[pc_id].get_stats(), ensure_ascii=False)
        )
    return web.Response(
        content_type="application/json",
        text=json.dumps({"error": "Connection not found"}, ensure_ascii=False),
        status=404
    )

async def recording_status(request):
    """Endpoint to get recording status and control recording"""
    global recording_running, current_recording, recording_thread
    
    if request.method == "GET":
        # Get recording status
        status = {
            "recording_enabled": recording_running,
            "currently_recording": current_recording is not None,
            "current_file": current_recording.filename if current_recording else None,
            "frame_count": current_recording.frame_count if current_recording else 0
        }
        return web.Response(
            content_type="application/json",
            text=json.dumps(status, ensure_ascii=False)
        )
    
    elif request.method == "POST":
        # Control recording
        try:
            data = await request.json()
            action = data.get("action")
            
            if action == "start" and not recording_running:
                recording_running = True
                # Start recording thread if not already running
                if not recording_thread or not recording_thread.is_alive():
                    recording_thread = threading.Thread(target=recording_worker, daemon=True)
                    recording_thread.start()
                return web.Response(
                    content_type="application/json",
                    text=json.dumps({"status": "Recording started"}, ensure_ascii=False)
                )
            
            elif action == "stop" and recording_running:
                recording_running = False
                with recording_lock:
                    if current_recording:
                        current_recording.stop()
                        current_recording = None
                return web.Response(
                    content_type="application/json",
                    text=json.dumps({"status": "Recording stopped"}, ensure_ascii=False)
                )
            
            else:
                return web.Response(
                    content_type="application/json",
                    text=json.dumps({"error": "Invalid action or already in requested state"}, ensure_ascii=False),
                    status=400
                )
                
        except Exception as e:
            return web.Response(
                content_type="application/json",
                text=json.dumps({"error": str(e)}, ensure_ascii=False),
                status=500
            )

async def on_shutdown(app):
    global frame_grabber_running, recording_running, current_recording
    # close peer connections
    coros = [pc.close() for pc in pcs.values()]
    await asyncio.gather(*coros)
    pcs.clear()
    if cap is not None:
        cap.release()  # Release the webcam
    frame_grabber_running = False
    
    # Stop recording
    recording_running = False
    with recording_lock:
        if current_recording:
            current_recording.stop()
            current_recording = None
    
    # Wait for threads to finish (with timeout)
    if recording_thread and recording_thread.is_alive():
        recording_thread.join(timeout=5.0)
    
    logger.info("Shutdown complete - all threads stopped")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam server")
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port for HTTP server (default: 8080)")
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument("--cert-file", help="SSL certificate file (optional)")
    parser.add_argument("--key-file", help="SSL key file (optional)")
    parser.add_argument("--no-recording", action="store_true", help="Disable video recording")
    parser.add_argument("--codec", default="auto", choices=["auto", "mp4v", "xvid", "mjpg", "h264"], 
                       help="Preferred video codec for recording (default: auto)")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Disable recording if requested
    if args.no_recording:
        recording_running = False
        logger.info("Video recording disabled by command line argument")
    
    # Store preferred codec for use in VideoRecorder
    preferred_codec = args.codec

    app = web.Application()
    
    # Setup CORS with more permissive settings
    cors = cors_setup(app, defaults={
        "*": ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        )
    })
    
    # Add routes
    app.router.add_get("/", index)
    app.router.add_get("/webrtc", webrtc)
    app.router.add_post("/webrtc", webrtc)
    app.router.add_get("/diagnostics", get_diagnostics)
    app.router.add_get("/recording_status", recording_status)
    app.router.add_post("/recording_status", recording_status)
    
    # Configure CORS for all routes
    for route in list(app.router.routes()):
        cors.add(route)
    
    app.on_shutdown.append(on_shutdown)

    # Configure SSL if certificates are provided
    ssl_context = None
    if args.cert_file and args.key_file:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(args.cert_file, args.key_file)

    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)

