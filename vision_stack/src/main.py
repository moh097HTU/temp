"""
Main entry point for running vision stack components.
"""

import argparse
import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Drone Vision Stack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Components:
  perception     - YOLO detection + tracking
  targeting      - Target lock and error computation  
  control        - Control mapping and safety
  mavlink        - MAVLink bridge to FC/QGC
  video          - Video streaming to GCS
  gpio           - ESP32 GPIO battery bridge
  all            - Run all components (bench mode)

Examples:
  python -m src.main perception --config-dir configs
  python -m src.main all --mode bench_px4_v1_16
        """
    )
    
    parser.add_argument(
        "component",
        choices=["perception", "targeting", "control", "mavlink", "video", "gpio", "all"],
        help="Component to run"
    )
    parser.add_argument(
        "--config-dir",
        default="configs",
        help="Configuration directory"
    )
    parser.add_argument(
        "--mode",
        default="bench_px4_v1_16",
        help="Mode configuration (bench_px4_v1_16 or flight)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--gcs-ip",
        default=None,
        help="Override GCS IP address"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    logger = logging.getLogger("main")
    logger.info(f"Starting component: {args.component}")
    logger.info(f"Config dir: {args.config_dir}")
    logger.info(f"Mode: {args.mode}")
    
    # Environment setup
    os.environ["GCS_IP"] = args.gcs_ip or os.environ.get("GCS_IP", "192.168.1.100")
    os.environ["MODE"] = args.mode
    
    try:
        if args.component == "perception":
            from .perception import PerceptionNode, load_perception_config
            config = load_perception_config(
                os.path.join(args.config_dir, "camera.yaml"),
                os.path.join(args.config_dir, "perception.yaml"),
                os.path.join(args.config_dir, "tracker.yaml"),
            )
            node = PerceptionNode(config)
            node.start()
            
        elif args.component == "targeting":
            from .targeting import TargetingNode, load_targeting_config
            config = load_targeting_config(
                os.path.join(args.config_dir, "targeting.yaml"),
                os.path.join(args.config_dir, "camera.yaml"),
            )
            node = TargetingNode(config)
            node.start()
            
        elif args.component == "control":
            from .control import ControlNode, load_control_config
            config = load_control_config(
                os.path.join(args.config_dir, "control.yaml"),
                os.path.join(args.config_dir, "modes", f"{args.mode}.yaml"),
            )
            node = ControlNode(config)
            node.start()
            
        elif args.component == "mavlink":
            from .mavlink import MavlinkBridge, load_mavlink_config
            config = load_mavlink_config(
                os.path.join(args.config_dir, "mavlink.yaml"),
                os.path.join(args.config_dir, "modes", f"{args.mode}.yaml"),
            )
            bridge = MavlinkBridge(config)
            bridge.start()
            
        elif args.component == "video":
            from .video import VideoStreamerNode, load_video_config
            config = load_video_config(
                os.path.join(args.config_dir, "video.yaml")
            )
            if args.gcs_ip:
                config.gcs_ip = args.gcs_ip
            node = VideoStreamerNode(config)
            node.start()
            
        elif args.component == "gpio":
            from .esp32 import Esp32GpioBridge, load_esp32_config
            config = load_esp32_config(
                os.path.join(args.config_dir, "esp32_gpio.yaml")
            )
            bridge = Esp32GpioBridge(config)
            bridge.start()
            
        elif args.component == "all":
            run_all_components(args)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


def run_all_components(args):
    """Run all components in separate threads."""
    import threading
    import signal
    
    logger = logging.getLogger("main")
    logger.info("Starting all components in bench mode...")
    
    # Import all components
    from .perception import PerceptionNode, load_perception_config
    from .targeting import TargetingNode, load_targeting_config
    from .control import ControlNode, load_control_config
    from .mavlink import MavlinkBridge, load_mavlink_config
    from .video import VideoStreamerNode, load_video_config
    from .esp32 import Esp32GpioBridge, load_esp32_config
    
    config_dir = args.config_dir
    mode = args.mode
    
    # Load configs
    perception_config = load_perception_config(
        os.path.join(config_dir, "camera.yaml"),
        os.path.join(config_dir, "perception.yaml"),
        os.path.join(config_dir, "tracker.yaml"),
    )
    targeting_config = load_targeting_config(
        os.path.join(config_dir, "targeting.yaml"),
        os.path.join(config_dir, "camera.yaml"),
    )
    control_config = load_control_config(
        os.path.join(config_dir, "control.yaml"),
        os.path.join(config_dir, "modes", f"{mode}.yaml"),
    )
    mavlink_config = load_mavlink_config(
        os.path.join(config_dir, "mavlink.yaml"),
        os.path.join(config_dir, "modes", f"{mode}.yaml"),
    )
    video_config = load_video_config(
        os.path.join(config_dir, "video.yaml")
    )
    gpio_config = load_esp32_config(
        os.path.join(config_dir, "esp32_gpio.yaml")
    )
    
    # Create nodes
    nodes = [
        ("perception", PerceptionNode(perception_config)),
        ("targeting", TargetingNode(targeting_config)),
        ("control", ControlNode(control_config)),
        ("mavlink", MavlinkBridge(mavlink_config)),
        ("video", VideoStreamerNode(video_config)),
        ("gpio", Esp32GpioBridge(gpio_config)),
    ]
    
    threads = []
    stop_event = threading.Event()
    
    def run_node(name, node):
        try:
            logger.info(f"Starting {name}...")
            node.start()
        except Exception as e:
            logger.error(f"{name} error: {e}")
    
    # Start all nodes in threads
    for name, node in nodes:
        t = threading.Thread(target=run_node, args=(name, node), daemon=True)
        t.start()
        threads.append(t)
    
    # Wait for interrupt
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal...")
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("All components started. Press Ctrl+C to stop.")
    
    # Wait
    while not stop_event.is_set():
        stop_event.wait(timeout=1.0)
    
    # Stop all nodes
    logger.info("Stopping all components...")
    for name, node in nodes:
        try:
            node.stop()
        except:
            pass


if __name__ == "__main__":
    main()
