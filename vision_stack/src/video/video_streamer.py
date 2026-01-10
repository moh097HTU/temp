"""
Video streamer using GStreamer.

Streams video from OAK-D to GCS via UDP RTP.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import yaml

logger = logging.getLogger(__name__)

# Try to import GStreamer
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib
    Gst.init(None)
    GST_AVAILABLE = True
except (ImportError, ValueError):
    GST_AVAILABLE = False
    logger.warning("GStreamer not available - running in stub mode")


@dataclass  
class VideoConfig:
    """Video streamer configuration."""
    gcs_ip: str = "192.168.1.100"
    port: int = 5600
    width: int = 1280  # Downscale from 1920 for bandwidth
    height: int = 720
    fps: int = 30
    bitrate: int = 2000  # kbps
    encoder: str = "x264"  # x264 or nvenc (Jetson)


def load_video_config(video_yaml: str) -> VideoConfig:
    """Load configuration from YAML file."""
    with open(video_yaml, 'r') as f:
        cfg = yaml.safe_load(f)

    stream_cfg = cfg.get('stream', {})
    
    return VideoConfig(
        gcs_ip=stream_cfg.get('gcs_ip', "192.168.1.100"),
        port=stream_cfg.get('port', 5600),
        width=stream_cfg.get('width', 1280),
        height=stream_cfg.get('height', 720),
        fps=stream_cfg.get('fps', 30),
        bitrate=stream_cfg.get('bitrate_kbps', 2000),
        encoder=stream_cfg.get('encoder', 'x264'),
    )


class VideoStreamer:
    """
    Streams video to GCS via UDP RTP using GStreamer.
    
    Pipeline:
    appsrc → videoconvert → scale → encoder → RTP → UDP
    """

    def __init__(self, config: VideoConfig):
        """
        Initialize video streamer.
        
        Args:
            config: Video configuration
        """
        self.config = config
        
        self._pipeline: Optional["Gst.Pipeline"] = None
        self._appsrc = None
        self._running = False
        self._frame_count = 0
        
        if GST_AVAILABLE:
            self._create_pipeline()
        
        logger.info(f"VideoStreamer initialized (target: {config.gcs_ip}:{config.port})")

    def _create_pipeline(self) -> None:
        """Create GStreamer pipeline."""
        # Choose encoder based on platform
        if self.config.encoder == "nvenc":
            # NVIDIA hardware encoder (Jetson) - requires nvvidconv for NVMM memory
            pipeline_str = """
                appsrc name=source is-live=true block=true format=time do-timestamp=true
                    caps=video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1 !
                queue max-size-buffers=4 leaky=downstream !
                videoconvert !
                nvvidconv !
                video/x-raw(memory:NVMM),format=NV12 !
                nvv4l2h264enc bitrate={bitrate} iframeinterval=30 insert-sps-pps=true preset-level=1 control-rate=1 !
                h264parse !
                rtph264pay pt=96 config-interval=1 !
                udpsink host={host} port={port} sync=false async=false
            """.format(
                width=self.config.width,
                height=self.config.height,
                fps=self.config.fps,
                bitrate=self.config.bitrate * 1000,
                host=self.config.gcs_ip,
                port=self.config.port
            )
        else:
            # Software x264 encoder (non-Jetson)
            pipeline_str = """
                appsrc name=source is-live=true format=time do-timestamp=true !
                video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1 !
                videoconvert !
                video/x-raw,format=I420 !
                x264enc tune=zerolatency bitrate={bitrate} speed-preset=ultrafast !
                rtph264pay config-interval=1 pt=96 !
                udpsink host={host} port={port} sync=false
            """.format(
                width=self.config.width,
                height=self.config.height,
                fps=self.config.fps,
                bitrate=self.config.bitrate,
                host=self.config.gcs_ip,
                port=self.config.port
            )

        try:
            self._pipeline = Gst.parse_launch(pipeline_str)
            self._appsrc = self._pipeline.get_by_name("source")
            
            # Configure appsrc
            self._appsrc.set_property("format", Gst.Format.TIME)
            
            logger.info("GStreamer pipeline created")
            
        except Exception as e:
            logger.error(f"Failed to create GStreamer pipeline: {e}")
            self._pipeline = None

    def start(self) -> bool:
        """
        Start the video stream.
        
        Returns:
            True if started successfully
        """
        if not GST_AVAILABLE or not self._pipeline:
            logger.warning("GStreamer not available - stub mode")
            self._running = True
            return True

        try:
            ret = self._pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to start GStreamer pipeline")
                return False
            
            self._running = True
            logger.info("Video stream started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            return False

    def stop(self) -> None:
        """Stop the video stream."""
        self._running = False
        
        if self._pipeline:
            try:
                self._pipeline.set_state(Gst.State.NULL)
                logger.info("Video stream stopped")
            except Exception as e:
                logger.error(f"Failed to stop stream: {e}")

    def push_frame(self, frame: np.ndarray) -> bool:
        """
        Push a frame to the stream.
        
        Args:
            frame: BGR numpy array (H, W, 3)
            
        Returns:
            True if pushed successfully
        """
        if not self._running:
            return False
        
        if not GST_AVAILABLE or not self._appsrc:
            # Stub mode - just count frames
            self._frame_count += 1
            return True

        try:
            # Resize if needed
            if frame.shape[1] != self.config.width or frame.shape[0] != self.config.height:
                import cv2
                frame = cv2.resize(frame, (self.config.width, self.config.height))
            
            # Create GStreamer buffer
            data = frame.tobytes()
            buf = Gst.Buffer.new_allocate(None, len(data), None)
            buf.fill(0, data)
            
            # Set timestamp
            duration = int(1e9 / self.config.fps)  # ns
            buf.pts = self._frame_count * duration
            buf.duration = duration
            
            # Push to appsrc
            ret = self._appsrc.emit("push-buffer", buf)
            
            self._frame_count += 1
            return ret == Gst.FlowReturn.OK
            
        except Exception as e:
            logger.error(f"Failed to push frame: {e}")
            return False

    @property
    def frame_count(self) -> int:
        """Get number of frames pushed."""
        return self._frame_count

    @property
    def is_running(self) -> bool:
        """Check if stream is running."""
        return self._running


class VideoStreamerNode:
    """
    Video streamer node that integrates with OAK bridge.
    
    Gets frames from OAK, draws detection overlays, and pushes to GStreamer stream.
    """

    def __init__(self, config: VideoConfig, oak_bridge=None):
        """
        Initialize video streamer node.
        
        Args:
            config: Video configuration
            oak_bridge: Optional OAK bridge to get frames from
        """
        self.config = config
        self._streamer = VideoStreamer(config)
        self._oak = oak_bridge
        self._running = False
        self._latest_tracks = []
        
        # Subscribe to tracks from perception
        try:
            from ..common.bus import ZmqSubscriber, BusPorts
            self._track_sub = ZmqSubscriber(BusPorts.sub_endpoint(BusPorts.PERCEPTION))
            self._track_sub.subscribe("tracks")
            logger.info("VideoStreamerNode subscribed to tracks")
        except Exception as e:
            logger.warning(f"Could not subscribe to tracks: {e}")
            self._track_sub = None
        
        logger.info("VideoStreamerNode initialized")

    def start(self) -> None:
        """Start video streaming."""
        logger.info("Starting video streamer node...")
        
        if not self._streamer.start():
            logger.error("Failed to start video stream")
            return
        
        self._running = True
        
        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("Video streamer interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop video streaming."""
        self._running = False
        self._streamer.stop()
        if self._track_sub:
            self._track_sub.close()
        logger.info("Video streamer node stopped")

    def _draw_tracks(self, frame: np.ndarray) -> np.ndarray:
        """Draw bounding boxes on frame."""
        try:
            import cv2
        except ImportError:
            logger.warning("OpenCV not available for drawing")
            return frame
        
        if len(self._latest_tracks) > 0:
            logger.debug(f"Drawing {len(self._latest_tracks)} tracks on frame")
        
        for track in self._latest_tracks:
            try:
                # Get bounding box
                x1, y1, x2, y2 = int(track.x1), int(track.y1), int(track.x2), int(track.y2)
                track_id = track.track_id
                class_name = track.class_name
                confidence = track.confidence
                
                # Color based on track ID
                colors = [
                    (0, 255, 0),    # Green
                    (255, 0, 0),    # Blue  
                    (0, 0, 255),    # Red
                    (255, 255, 0),  # Cyan
                    (255, 0, 255),  # Magenta
                    (0, 255, 255),  # Yellow
                ]
                color = colors[track_id % len(colors)]
                
                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Draw label
                label = f"#{track_id} {class_name} {confidence:.2f}"
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(frame, (x1, y1 - label_size[1] - 10), (x1 + label_size[0], y1), color, -1)
                cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            except Exception as e:
                logger.error(f"Error drawing track: {e}")
        
        return frame

    def _run_loop(self) -> None:
        """Main processing loop."""
        target_period = 1.0 / self.config.fps
        frame_count = 0
        last_track_log = time.time()
        
        while self._running:
            loop_start = time.time()
            
            # Check for new tracks (non-blocking)
            if self._track_sub:
                try:
                    result = self._track_sub.receive(timeout_ms=1)
                    if result:
                        # receive() returns (topic, message) tuple
                        topic, msg = result
                        
                        # msg is a dict with 'tracks' key (from TrackList dataclass)
                        if isinstance(msg, dict) and 'tracks' in msg:
                            raw_tracks = msg['tracks']
                            # Convert dicts to track-like objects
                            self._latest_tracks = [type('Track', (), t) for t in raw_tracks]
                            
                            # Log every 2 seconds
                            if time.time() - last_track_log > 2.0:
                                logger.info(f"[VIDEO] Received {len(self._latest_tracks)} tracks")
                                last_track_log = time.time()
                        elif hasattr(msg, 'tracks'):
                            # Direct TrackList object
                            self._latest_tracks = msg.tracks
                            if time.time() - last_track_log > 2.0:
                                logger.info(f"[VIDEO] Received {len(self._latest_tracks)} tracks (obj)")
                                last_track_log = time.time()
                        else:
                            logger.warning(f"[VIDEO] Unknown msg format: {type(msg)}")
                except Exception as e:
                    logger.error(f"[VIDEO] Track receive error: {e}")
            else:
                if frame_count == 0:
                    logger.warning("[VIDEO] No track subscriber available!")
            
            # Get frame
            frame = None
            if self._oak:
                frame = self._oak.get_frame()
            
            if frame is not None:
                # Draw detection overlays
                frame = self._draw_tracks(frame)
                self._streamer.push_frame(frame)
                frame_count += 1
            
            # Rate limiting
            elapsed = time.time() - loop_start
            if elapsed < target_period:
                time.sleep(target_period - elapsed)


def main():
    """Run video streamer standalone."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Video Streamer")
    parser.add_argument("--config-dir", default="configs", help="Config directory")
    parser.add_argument("--gcs-ip", default="192.168.1.100", help="GCS IP address")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = load_video_config(
        os.path.join(args.config_dir, "video.yaml")
    )
    
    # Override GCS IP if provided
    if args.gcs_ip:
        config.gcs_ip = args.gcs_ip

    node = VideoStreamerNode(config)
    node.start()


if __name__ == "__main__":
    main()
