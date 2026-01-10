"""
Targeting node - orchestrates lock management and error computation.

Subscribes to tracks from perception, receives commands from QGC,
and publishes lock state and errors to control.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import yaml

from ..common.types import (
    TrackList, LockState, Errors, UserCommand, CommandType,
    CameraIntrinsics
)
from ..common.bus import ZmqPublisher, ZmqSubscriber, BusPorts
from ..oak import OakBridge
from .lock_manager import LockManager, LockConfig
from .errors import ErrorComputer, ErrorConfig

logger = logging.getLogger(__name__)


@dataclass
class TargetingConfig:
    """Targeting node configuration."""
    lock: LockConfig
    error: ErrorConfig
    intrinsics: CameraIntrinsics
    update_rate_hz: float = 30.0


def load_targeting_config(
    targeting_yaml: str,
    camera_yaml: str
) -> TargetingConfig:
    """Load configuration from YAML files."""
    with open(targeting_yaml, 'r') as f:
        targeting_cfg = yaml.safe_load(f)
    with open(camera_yaml, 'r') as f:
        camera_cfg = yaml.safe_load(f)

    cam = camera_cfg.get('camera', {})
    intrinsics = cam.get('intrinsics', {})

    return TargetingConfig(
        lock=LockConfig(
            lock_timeout_ms=targeting_cfg.get('lock', {}).get('lock_timeout_ms', 500.0),
            reacquire_timeout_ms=targeting_cfg.get('lock', {}).get('reacquire_timeout_ms', 2000.0),
            iou_threshold=targeting_cfg.get('lock', {}).get('iou_threshold', 0.3),
            max_pixel_distance=targeting_cfg.get('lock', {}).get('max_pixel_distance', 100.0),
        ),
        error=ErrorConfig(
            desired_range_m=targeting_cfg.get('error', {}).get('desired_range_m', 10.0),
            min_range_m=targeting_cfg.get('error', {}).get('min_range_m', 3.0),
            max_range_m=targeting_cfg.get('error', {}).get('max_range_m', 50.0),
        ),
        intrinsics=CameraIntrinsics(
            fx=intrinsics.get('fx', 1000.0),
            fy=intrinsics.get('fy', 1000.0),
            cx=intrinsics.get('cx', 960.0),
            cy=intrinsics.get('cy', 540.0),
            width=cam.get('rgb', {}).get('width', 1920),
            height=cam.get('rgb', {}).get('height', 1080),
        ),
        update_rate_hz=targeting_cfg.get('update_rate_hz', 30.0),
    )


class TargetingNode:
    """
    Targeting node.
    
    Subscribes to:
    - tracks from perception
    - qgc_cmds from mavlink bridge
    
    Publishes:
    - lock_state
    - errors
    """

    def __init__(self, config: TargetingConfig, oak_bridge: Optional[OakBridge] = None):
        """
        Initialize targeting node.
        
        Args:
            config: Targeting configuration
            oak_bridge: Optional OAK bridge for depth queries (can be shared)
        """
        self.config = config
        
        # Components
        self._lock_manager = LockManager(config.lock)
        self._error_computer = ErrorComputer(config.intrinsics, config.error)
        self._oak = oak_bridge  # May be None if depth comes from another source
        
        # ZMQ
        self._publisher = ZmqPublisher(BusPorts.pub_endpoint(BusPorts.TARGETING))
        self._track_sub = ZmqSubscriber(BusPorts.sub_endpoint(BusPorts.PERCEPTION))
        self._cmd_sub = ZmqSubscriber(BusPorts.sub_endpoint(BusPorts.MAVLINK))
        
        self._track_sub.subscribe("tracks")
        self._cmd_sub.subscribe("qgc_cmds")
        
        # State
        self._running = False
        self._tracking_enabled = False
        self._current_tracks: Optional[TrackList] = None
        self._min_depth = config.error.min_range_m
        self._max_depth = config.error.max_range_m
        
        logger.info("TargetingNode initialized")

    def start(self) -> None:
        """Start targeting node."""
        logger.info("Starting targeting node...")
        self._running = True
        
        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("Targeting node interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop targeting node."""
        self._running = False
        self._publisher.close()
        self._track_sub.close()
        self._cmd_sub.close()
        logger.info("Targeting node stopped")

    def _run_loop(self) -> None:
        """Main processing loop."""
        target_period = 1.0 / self.config.update_rate_hz
        
        while self._running:
            loop_start = time.time()
            
            # Process incoming commands
            self._process_commands()
            
            # Process incoming tracks
            self._process_tracks()
            
            # If we have tracks and tracking is enabled, compute errors
            if self._tracking_enabled and self._current_tracks:
                self._compute_and_publish()
            
            # Rate limiting
            elapsed = time.time() - loop_start
            if elapsed < target_period:
                time.sleep(target_period - elapsed)

    def _process_commands(self) -> None:
        """Process incoming QGC commands."""
        while True:
            result = self._cmd_sub.receive(timeout_ms=0)
            if result is None:
                break
            
            topic, msg = result
            if isinstance(msg, dict):
                self._handle_command(msg)
            elif isinstance(msg, UserCommand):
                self._handle_user_command(msg)

    def _handle_command(self, msg: dict) -> None:
        """Handle command dict from ZMQ."""
        cmd_type = msg.get('cmd_type')
        logger.info(f"[TARGETING] Received command: {cmd_type}")
        
        if cmd_type == 'START_TRACKING':
            self._tracking_enabled = True
            logger.info("[TARGETING] Tracking ENABLED")
        elif cmd_type == 'STOP_TRACKING':
            self._tracking_enabled = False
            self._lock_manager.clear_lock()
            logger.info("[TARGETING] Tracking DISABLED")
        elif cmd_type == 'SELECT_TARGET_ID':
            track_id = msg.get('track_id')
            logger.info(f"[TARGETING] Select target by ID: {track_id}")
            if track_id and self._current_tracks:
                self._lock_manager.select_by_id(track_id, self._current_tracks.tracks)
                logger.info(f"[TARGETING] Lock state: {self._lock_manager.get_lock_state()}")
        elif cmd_type == 'SELECT_TARGET_PIXEL':
            u, v = msg.get('pixel_u'), msg.get('pixel_v')
            logger.info(f"[TARGETING] Select target by pixel: ({u}, {v})")
            if u is not None and v is not None and self._current_tracks:
                self._lock_manager.select_by_pixel(u, v, self._current_tracks.tracks)
                logger.info(f"[TARGETING] Lock state: {self._lock_manager.get_lock_state()}")
        elif cmd_type == 'SET_DEPTH_RANGE':
            self._min_depth = msg.get('min_depth', self._min_depth)
            self._max_depth = msg.get('max_depth', self._max_depth)
            logger.info(f"[TARGETING] Depth range set: {self._min_depth} - {self._max_depth} m")
        elif cmd_type == 'CLEAR_LOCK':
            self._lock_manager.clear_lock()
            logger.info("[TARGETING] Lock CLEARED")

    def _handle_user_command(self, cmd: UserCommand) -> None:
        """Handle UserCommand dataclass."""
        if cmd.cmd_type == CommandType.START_TRACKING:
            self._tracking_enabled = True
        elif cmd.cmd_type == CommandType.STOP_TRACKING:
            self._tracking_enabled = False
            self._lock_manager.clear_lock()
        elif cmd.cmd_type == CommandType.SELECT_TARGET_ID:
            if cmd.track_id and self._current_tracks:
                self._lock_manager.select_by_id(cmd.track_id, self._current_tracks.tracks)
        elif cmd.cmd_type == CommandType.SELECT_TARGET_PIXEL:
            if cmd.pixel_u is not None and cmd.pixel_v is not None and self._current_tracks:
                self._lock_manager.select_by_pixel(
                    cmd.pixel_u, cmd.pixel_v, self._current_tracks.tracks
                )
        elif cmd.cmd_type == CommandType.SET_DEPTH_RANGE:
            if cmd.min_depth is not None:
                self._min_depth = cmd.min_depth
            if cmd.max_depth is not None:
                self._max_depth = cmd.max_depth
        elif cmd.cmd_type == CommandType.CLEAR_LOCK:
            self._lock_manager.clear_lock()

    def _process_tracks(self) -> None:
        """Process incoming track lists."""
        while True:
            result = self._track_sub.receive(timeout_ms=0)
            if result is None:
                break
            
            topic, msg = result
            if isinstance(msg, TrackList):
                self._current_tracks = msg
            elif isinstance(msg, dict) and 'tracks' in msg:
                # Reconstruct from dict
                from ..common.types import Track, BoundingBox
                tracks = []
                for t in msg.get('tracks', []):
                    bbox = t.get('bbox', {})
                    tracks.append(Track(
                        track_id=t.get('track_id', 0),
                        bbox=BoundingBox(
                            x1=bbox.get('x1', 0),
                            y1=bbox.get('y1', 0),
                            x2=bbox.get('x2', 0),
                            y2=bbox.get('y2', 0)
                        ),
                        class_id=t.get('class_id', 0),
                        label=t.get('label', 'unknown'),
                        confidence=t.get('confidence', 0.0),
                        timestamp=t.get('timestamp', time.time())
                    ))
                self._current_tracks = TrackList(
                    tracks=tracks,
                    frame_id=msg.get('frame_id', 0),
                    timestamp=msg.get('timestamp', time.time())
                )

    def _compute_and_publish(self) -> None:
        """Compute lock state and errors, then publish."""
        if not self._current_tracks:
            return

        # Update lock state
        lock_state = self._lock_manager.update(self._current_tracks.tracks)
        
        # Publish lock state
        self._publisher.publish("lock_state", lock_state)
        
        # Get locked track
        locked_track = self._lock_manager.get_locked_track(self._current_tracks.tracks)
        
        # Query depth if we have OAK bridge and a locked track
        depth_m = None
        if self._oak and locked_track:
            bbox = locked_track.bbox
            depth_m = self._oak.query_depth_roi(
                int(bbox.x1), int(bbox.y1),
                int(bbox.x2), int(bbox.y2)
            )
        
        # Compute errors
        errors = self._error_computer.compute(
            track=locked_track,
            depth_m=depth_m,
            lock_valid=lock_state.is_valid
        )
        
        # Publish errors
        self._publisher.publish("errors", errors)


def main():
    """Run targeting node standalone."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Targeting Node")
    parser.add_argument("--config-dir", default="configs", help="Config directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = load_targeting_config(
        os.path.join(args.config_dir, "targeting.yaml"),
        os.path.join(args.config_dir, "camera.yaml"),
    )

    node = TargetingNode(config)
    node.start()


if __name__ == "__main__":
    main()
