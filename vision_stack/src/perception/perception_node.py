"""
Perception node - orchestrates detection and tracking.

Receives RGB frames from OAK bridge, runs YOLO detection,
tracks objects, and publishes track list to ZMQ bus.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import yaml

from ..common.types import TrackList
from ..common.bus import ZmqPublisher, BusPorts
from ..oak import OakBridge, OakConfig
from .detector import YoloDetector, DetectorConfig
from .tracker import ByteTrackTracker, TrackerConfig

logger = logging.getLogger(__name__)


@dataclass
class PerceptionConfig:
    """Perception node configuration."""
    # Camera
    camera: OakConfig
    # Detection
    detector: DetectorConfig
    # Tracking
    tracker: TrackerConfig
    # Node settings
    target_fps: float = 30.0
    publish_rate_hz: float = 30.0


def load_perception_config(
    camera_yaml: str,
    perception_yaml: str,
    tracker_yaml: str
) -> PerceptionConfig:
    """Load configuration from YAML files."""
    with open(camera_yaml, 'r') as f:
        camera_cfg = yaml.safe_load(f)
    with open(perception_yaml, 'r') as f:
        perception_cfg = yaml.safe_load(f)
    with open(tracker_yaml, 'r') as f:
        tracker_cfg = yaml.safe_load(f)

    return PerceptionConfig(
        camera=OakConfig(
            rgb_width=camera_cfg.get('camera', {}).get('rgb', {}).get('width', 1920),
            rgb_height=camera_cfg.get('camera', {}).get('rgb', {}).get('height', 1080),
            rgb_fps=camera_cfg.get('camera', {}).get('rgb', {}).get('fps', 30),
            depth_width=camera_cfg.get('camera', {}).get('depth', {}).get('width', 640),
            depth_height=camera_cfg.get('camera', {}).get('depth', {}).get('height', 400),
            depth_enabled=camera_cfg.get('camera', {}).get('depth', {}).get('enabled', True),
            fx=camera_cfg.get('camera', {}).get('intrinsics', {}).get('fx', 1000.0),
            fy=camera_cfg.get('camera', {}).get('intrinsics', {}).get('fy', 1000.0),
            cx=camera_cfg.get('camera', {}).get('intrinsics', {}).get('cx', 960.0),
            cy=camera_cfg.get('camera', {}).get('intrinsics', {}).get('cy', 540.0),
        ),
        detector=DetectorConfig(
            model_path=perception_cfg.get('detector', {}).get('model_path', 'yolov8n.pt'),
            confidence_threshold=perception_cfg.get('detector', {}).get('confidence_threshold', 0.5),
            iou_threshold=perception_cfg.get('detector', {}).get('iou_threshold', 0.45),
            max_detections=perception_cfg.get('detector', {}).get('max_detections', 100),
            device=perception_cfg.get('detector', {}).get('device', '0'),
            filter_classes=perception_cfg.get('detector', {}).get('filter_classes'),
            class_names=perception_cfg.get('detector', {}).get('class_names'),
        ),
        tracker=TrackerConfig(
            max_age=tracker_cfg.get('tracker', {}).get('max_age', 30),
            min_hits=tracker_cfg.get('tracker', {}).get('min_hits', 3),
            iou_threshold=tracker_cfg.get('tracker', {}).get('iou_threshold', 0.3),
        ),
        target_fps=perception_cfg.get('target_fps', 30.0),
    )


class PerceptionNode:
    """
    Main perception node.
    
    Pipeline: OAK → RGB frame → YOLO → Detections → Tracker → Tracks → ZMQ
    """

    def __init__(self, config: PerceptionConfig):
        """
        Initialize perception node.
        
        Args:
            config: Perception configuration
        """
        self.config = config
        
        # Initialize components
        self._oak = OakBridge(config.camera)
        self._detector = YoloDetector(config.detector)
        self._tracker = ByteTrackTracker(config.tracker)
        
        # ZMQ publisher
        self._publisher = ZmqPublisher(BusPorts.pub_endpoint(BusPorts.PERCEPTION))
        
        # State
        self._running = False
        self._frame_count = 0
        
        logger.info("PerceptionNode initialized")

    def start(self) -> None:
        """Start perception pipeline."""
        logger.info("Starting perception node...")
        self._oak.start()
        self._running = True
        
        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("Perception node interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop perception pipeline."""
        self._running = False
        self._oak.stop()
        self._publisher.close()
        logger.info("Perception node stopped")

    def _run_loop(self) -> None:
        """Main processing loop."""
        target_period = 1.0 / self.config.target_fps
        last_detection_log = time.time()
        
        while self._running:
            loop_start = time.time()
            
            # Get frame from OAK
            frame = self._oak.get_frame()
            if frame is None:
                time.sleep(0.001)
                continue

            # Run detection
            detections = self._detector.detect(frame)
            
            # Debug: log detection count every 2 seconds
            if time.time() - last_detection_log > 2.0:
                logger.info(f"[PERCEPTION] Frame {self._frame_count}: {len(detections)} detections")
                last_detection_log = time.time()
            
            # Run tracking
            tracks = self._tracker.update(detections, frame)
            
            # Create track list message
            track_list = TrackList(
                tracks=tracks,
                frame_id=self._frame_count,
                timestamp=time.time()
            )
            
            # Publish to ZMQ
            self._publisher.publish("tracks", track_list)
            
            self._frame_count += 1
            
            # Rate limiting
            elapsed = time.time() - loop_start
            if elapsed < target_period:
                time.sleep(target_period - elapsed)

            # Periodic logging
            if self._frame_count % 100 == 0:
                fps = 1.0 / max(elapsed, 0.001)
                logger.debug(f"Frame {self._frame_count}: {len(tracks)} tracks, {fps:.1f} FPS")


def main():
    """Run perception node standalone."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Perception Node")
    parser.add_argument("--config-dir", default="configs", help="Config directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = load_perception_config(
        os.path.join(args.config_dir, "camera.yaml"),
        os.path.join(args.config_dir, "perception.yaml"),
        os.path.join(args.config_dir, "tracker.yaml"),
    )

    node = PerceptionNode(config)
    node.start()


if __name__ == "__main__":
    main()
