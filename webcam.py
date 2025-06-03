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
from aiortc.contrib.media import MediaPlayer, MediaRelay, MediaStreamTrack
from aiortc.rtcrtpsender import RTCRtpSender
from datetime import datetime

ROOT = os.path.dirname(__file__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Connection tracking
connection_stats = {}

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

# Initialize camera at startup
if not initialize_camera():
    print("Warning: No camera available. The application will not be able to stream video.")

class WebcamTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._retry_count = 0
        self._max_retries = 3

    async def recv(self):
        if cap is None or not cap.isOpened():
            print("Camera not available")
            return None
            
        try:
            ret, frame = cap.read()
            if not ret or frame is None:
                self._retry_count += 1
                if self._retry_count >= self._max_retries:
                    print("Failed to read frame from camera after multiple attempts")
                    return None
                print(f"Retrying frame capture (attempt {self._retry_count})")
                await asyncio.sleep(0.1)  # Small delay before retry
                return await self.recv()

            self._retry_count = 0  # Reset retry count on successful capture
            # Convert BGR to RGBA
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            
            pts = time.time() * 1000000
            new_frame = av.VideoFrame.from_ndarray(frame, format='rgba')
            new_frame.pts = int(pts)
            new_frame.time_base = Fraction(1,1000000)
            return new_frame
        except Exception as e:
            print(f"Error in WebcamTrack.recv: {str(e)}")
            return None

async def index(request):
    content = open(os.path.join(ROOT, "client.html"), "r").read()
    return web.Response(content_type="text/html", text=content)

async def webrtc(request):
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
                        await pc.restartIce()
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
                    await pc.restartIce()
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
                    "iceServers": [{"urls": server.urls, "username": getattr(server, "username", None), "credential": getattr(server, "credential", None)} for server in configuration.iceServers],
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
    # close peer connections
    coros = [pc.close() for pc in pcs.values()]
    await asyncio.gather(*coros)
    pcs.clear()
    if cap is not None:
        cap.release()  # Release the webcam

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam server")
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port for HTTP server (default: 8080)")
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Create a basic SSL context even without certificates
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    app = web.Application()
    
    # Setup CORS
    cors = cors_setup(app, defaults={
        "*": ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    
    # Add routes
    app.router.add_get("/", index)
    app.router.add_post("/webrtc", webrtc)
    app.router.add_get("/diagnostics", get_diagnostics)  # New diagnostics endpoint
    
    # Configure CORS for all routes
    for route in list(app.router.routes()):
        cors.add(route)
    
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)

