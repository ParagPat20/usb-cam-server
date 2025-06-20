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

relay = None
webcam = None
cap = None
pcs = {}

def initialize_camera():
    global cap
    try:
        # Try V4L2 first (Linux)
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        except:
            cap = cv2.VideoCapture(0)  # Fallback to default backend
        
        if cap.isOpened():
            # Set resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
            # Set frame rate
            cap.set(cv2.CAP_PROP_FPS, 30)
            # Set buffer size
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print("Successfully opened camera at index 0")
            return True
    except Exception as e:
        print(f"Error opening camera: {str(e)}")
        if cap is not None:
            cap.release()
    print("Failed to open camera at index 0")
    return False

def frame_grabber():
    global latest_frame, frame_grabber_running
    while frame_grabber_running:
        if cap is not None and cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                with frame_lock:
                    latest_frame = frame.copy()
        time.sleep(0.01)  # Small sleep to avoid 100% CPU

# Start the frame grabber thread after camera initialization
if not initialize_camera():
    print("Warning: No camera available. The application will not be able to stream video.")
else:
    grabber_thread = threading.Thread(target=frame_grabber, daemon=True)
    grabber_thread.start()

class WebcamTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._retry_count = 0
        self._max_retries = 3

    async def recv(self):
        global latest_frame
        # Always use the latest frame from the grabber thread
        for _ in range(self._max_retries):
            with frame_lock:
                frame = None if latest_frame is None else latest_frame.copy()
            if frame is not None:
                # Optionally, check for stability and save if stable
                # if detect_stability(frame):
                #     save_queue.put(frame.copy())
                # Convert BGR to RGBA for streaming
                frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
                frame_rgba = frame_rgba.astype('uint8')  # Ensure correct dtype
                pts = time.time() * 1000000
                new_frame = av.VideoFrame.from_ndarray(frame_rgba, format='rgba')
                new_frame.pts = int(pts)
                new_frame.time_base = Fraction(1,1000000)
                return new_frame
            await asyncio.sleep(0.01)  # Wait for a frame to become available
        print("No frame available after retries")
        return None

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

async def on_shutdown(app):
    global frame_grabber_running
    # close peer connections
    coros = [pc.close() for pc in pcs.values()]
    await asyncio.gather(*coros)
    pcs.clear()
    if cap is not None:
        cap.release()  # Release the webcam
    frame_grabber_running = False
    # Optionally join the thread if needed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam server")
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port for HTTP server (default: 8080)")
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument("--cert-file", help="SSL certificate file (optional)")
    parser.add_argument("--key-file", help="SSL key file (optional)")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

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

