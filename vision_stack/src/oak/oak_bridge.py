"""
OAK-D Lite bridge for RGB frames and depth queries.

Provides RGB frames to perception and depth queries to targeting.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple
import threading
from queue import Queue

import numpy as np

logger = logging.getLogger(__name__)

# Try to import DepthAI, but allow running without it for testing
try:
    import depthai as dai
    DEPTHAI_AVAILABLE = True
except ImportError:
    DEPTHAI_AVAILABLE = False
    logger.warning("DepthAI not available - running in stub mode")


@dataclass
class OakConfig:
    """OAK-D Lite configuration."""
    rgb_width: int = 1920
    rgb_height: int = 1080
    rgb_fps: int = 30
    depth_width: int = 640
    depth_height: int = 400
    depth_enabled: bool = True
    # Camera intrinsics (calibrate for actual camera)
    fx: float = 1000.0
    fy: float = 1000.0
    cx: float = 960.0
    cy: float = 540.0


class OakBridge:
    """
    Bridge to OAK-D Lite camera.
    
    Provides:
    - RGB frames at configured FPS
    - Depth queries at arbitrary pixel locations
    - ROI depth median for more robust measurements
    """

    def __init__(self, config: OakConfig):
        """
        Initialize OAK-D bridge.
        
        Args:
            config: Camera configuration
        """
        self.config = config
        self._running = False
        self._rgb_frame: Optional[np.ndarray] = None
        self._depth_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._frame_queue: Queue = Queue(maxsize=2)
        self._pipeline: Optional["dai.Pipeline"] = None
        self._device: Optional["dai.Device"] = None
        
        logger.info(f"OakBridge initialized: {config.rgb_width}x{config.rgb_height}@{config.rgb_fps}fps")

    def _create_pipeline(self) -> "dai.Pipeline":
        """Create DepthAI pipeline for RGB and depth."""
        if not DEPTHAI_AVAILABLE:
            raise RuntimeError("DepthAI not available")

        pipeline = dai.Pipeline()

        # RGB Camera
        cam_rgb = pipeline.create(dai.node.ColorCamera)
        cam_rgb.setPreviewSize(self.config.rgb_width, self.config.rgb_height)
        cam_rgb.setInterleaved(False)
        cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        cam_rgb.setFps(self.config.rgb_fps)

        # RGB output
        xout_rgb = pipeline.create(dai.node.XLinkOut)
        xout_rgb.setStreamName("rgb")
        cam_rgb.preview.link(xout_rgb.input)

        if self.config.depth_enabled:
            # Mono cameras for stereo depth
            mono_left = pipeline.create(dai.node.MonoCamera)
            mono_right = pipeline.create(dai.node.MonoCamera)
            mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
            mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
            mono_left.setBoardSocket(dai.CameraBoardSocket.LEFT)
            mono_right.setBoardSocket(dai.CameraBoardSocket.RIGHT)

            # Stereo depth
            stereo = pipeline.create(dai.node.StereoDepth)
            stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
            stereo.setDepthAlign(dai.CameraBoardSocket.RGB)
            stereo.setOutputSize(self.config.depth_width, self.config.depth_height)

            mono_left.out.link(stereo.left)
            mono_right.out.link(stereo.right)

            # Depth output
            xout_depth = pipeline.create(dai.node.XLinkOut)
            xout_depth.setStreamName("depth")
            stereo.depth.link(xout_depth.input)

        return pipeline

    def start(self) -> None:
        """Start the OAK-D pipeline."""
        if self._running:
            return

        if DEPTHAI_AVAILABLE:
            self._pipeline = self._create_pipeline()
            self._device = dai.Device(self._pipeline)
            self._running = True
            
            # Start capture thread
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            logger.info("OAK-D pipeline started")
        else:
            self._running = True
            logger.info("OAK-D running in stub mode (no hardware)")

    def stop(self) -> None:
        """Stop the OAK-D pipeline."""
        self._running = False
        if self._device:
            self._device.close()
            self._device = None
        logger.info("OAK-D pipeline stopped")

    def _capture_loop(self) -> None:
        """Continuously capture frames from OAK-D."""
        if not self._device:
            return

        rgb_queue = self._device.getOutputQueue("rgb", maxSize=2, blocking=False)
        depth_queue = None
        if self.config.depth_enabled:
            depth_queue = self._device.getOutputQueue("depth", maxSize=2, blocking=False)

        while self._running:
            try:
                # Get RGB frame
                rgb_data = rgb_queue.tryGet()
                if rgb_data:
                    with self._frame_lock:
                        self._rgb_frame = rgb_data.getCvFrame()

                # Get depth frame
                if depth_queue:
                    depth_data = depth_queue.tryGet()
                    if depth_data:
                        with self._frame_lock:
                            self._depth_frame = depth_data.getFrame()

                time.sleep(0.001)  # Small sleep to prevent busy-waiting
            except Exception as e:
                logger.error(f"Capture error: {e}")
                time.sleep(0.1)

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get the latest RGB frame.
        
        Returns:
            BGR numpy array or None if no frame available
        """
        with self._frame_lock:
            if self._rgb_frame is not None:
                return self._rgb_frame.copy()
        
        # Stub mode: return black frame
        if not DEPTHAI_AVAILABLE and self._running:
            return np.zeros((self.config.rgb_height, self.config.rgb_width, 3), dtype=np.uint8)
        
        return None

    def get_depth_frame(self) -> Optional[np.ndarray]:
        """
        Get the latest depth frame.
        
        Returns:
            Depth numpy array (uint16, mm) or None
        """
        with self._frame_lock:
            if self._depth_frame is not None:
                return self._depth_frame.copy()
        return None

    def query_depth(self, u: int, v: int) -> Optional[float]:
        """
        Query depth at a specific pixel location.
        
        Args:
            u: Pixel x coordinate (in RGB frame coordinates)
            v: Pixel y coordinate (in RGB frame coordinates)
            
        Returns:
            Depth in meters, or None if invalid
        """
        depth_frame = self.get_depth_frame()
        if depth_frame is None:
            return None

        # Scale RGB coordinates to depth frame coordinates
        scale_x = self.config.depth_width / self.config.rgb_width
        scale_y = self.config.depth_height / self.config.rgb_height
        
        depth_u = int(u * scale_x)
        depth_v = int(v * scale_y)

        # Bounds check
        if not (0 <= depth_u < self.config.depth_width and 
                0 <= depth_v < self.config.depth_height):
            return None

        # Get depth value (in mm) and convert to meters
        depth_mm = depth_frame[depth_v, depth_u]
        if depth_mm == 0:
            return None

        return depth_mm / 1000.0

    def query_depth_roi(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        percentile: float = 50.0
    ) -> Optional[float]:
        """
        Query depth over a region of interest using percentile.
        
        More robust than single-pixel query.
        
        Args:
            x1, y1, x2, y2: ROI in RGB frame coordinates
            percentile: Percentile to use (50 = median)
            
        Returns:
            Depth in meters, or None if invalid
        """
        depth_frame = self.get_depth_frame()
        if depth_frame is None:
            return None

        # Scale to depth coordinates
        scale_x = self.config.depth_width / self.config.rgb_width
        scale_y = self.config.depth_height / self.config.rgb_height

        d_x1 = int(x1 * scale_x)
        d_y1 = int(y1 * scale_y)
        d_x2 = int(x2 * scale_x)
        d_y2 = int(y2 * scale_y)

        # Clamp to valid range
        d_x1 = max(0, min(d_x1, self.config.depth_width - 1))
        d_x2 = max(0, min(d_x2, self.config.depth_width))
        d_y1 = max(0, min(d_y1, self.config.depth_height - 1))
        d_y2 = max(0, min(d_y2, self.config.depth_height))

        if d_x2 <= d_x1 or d_y2 <= d_y1:
            return None

        # Extract ROI and compute percentile
        roi = depth_frame[d_y1:d_y2, d_x1:d_x2]
        valid_depths = roi[roi > 0]
        
        if len(valid_depths) == 0:
            return None

        depth_mm = np.percentile(valid_depths, percentile)
        return depth_mm / 1000.0

    @property
    def intrinsics(self) -> Tuple[float, float, float, float]:
        """Return camera intrinsics (fx, fy, cx, cy)."""
        return (self.config.fx, self.config.fy, self.config.cx, self.config.cy)

    @property
    def is_running(self) -> bool:
        return self._running
