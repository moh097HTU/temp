"""
MAVLink bridge - main interface to flight controller and QGC.

Handles:
- UDP connection to MAVProxy
- Receiving QGC commands
- Sending setpoints to FC
- Injecting custom telemetry
"""

import logging
import time
import threading
from dataclasses import dataclass
from typing import Optional

import yaml

from ..common.types import Setpoint, BatteryState, UserCommand
from ..common.bus import ZmqPublisher, ZmqSubscriber, BusPorts
from .offboard_session import OffboardSession, OffboardConfig
from .user_commands import UserCommandParser
from .custom_telemetry import CustomTelemetrySender
from .telemetry import TelemetryReceiver, TelemetryConfig
from .failsafe import FailsafeManager, FailsafeConfig, FailsafeState

logger = logging.getLogger(__name__)

# Try to import pymavlink
try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False
    logger.warning("pymavlink not available - running in stub mode")


@dataclass
class MavlinkConfig:
    """MAVLink bridge configuration."""
    # Connection
    udp_host: str = "127.0.0.1"
    udp_port: int = 14551  # MAVProxy output port
    
    # Offboard
    offboard: OffboardConfig = None
    
    # Telemetry
    telemetry: TelemetryConfig = None
    
    # Failsafe
    failsafe: FailsafeConfig = None
    
    # Rates
    receive_rate_hz: float = 100.0  # MAVLink receive rate
    command_publish_rate_hz: float = 30.0

    def __post_init__(self):
        if self.offboard is None:
            self.offboard = OffboardConfig()
        if self.telemetry is None:
            self.telemetry = TelemetryConfig()
        if self.failsafe is None:
            self.failsafe = FailsafeConfig()


def load_mavlink_config(mavlink_yaml: str, mode_yaml: str) -> MavlinkConfig:
    """Load configuration from YAML files."""
    with open(mavlink_yaml, 'r') as f:
        mav_cfg = yaml.safe_load(f)
    with open(mode_yaml, 'r') as f:
        mode_cfg = yaml.safe_load(f)

    conn = mav_cfg.get('connection', {})
    offboard_cfg = mode_cfg.get('offboard', {})
    safety_cfg = mode_cfg.get('safety', {})

    return MavlinkConfig(
        udp_host=conn.get('host', '127.0.0.1'),
        udp_port=conn.get('port', 14551),
        offboard=OffboardConfig(
            setpoint_rate_hz=offboard_cfg.get('setpoint_rate_hz', 30.0),
            heartbeat_rate_hz=offboard_cfg.get('heartbeat_rate_hz', 1.0),
        ),
        telemetry=TelemetryConfig(
            timeout_ms=safety_cfg.get('telemetry_timeout_ms', 1000.0),
        ),
        failsafe=FailsafeConfig(
            track_lost_failsafe_ms=safety_cfg.get('track_timeout_ms', 500.0),
            telemetry_lost_failsafe_ms=safety_cfg.get('telemetry_timeout_ms', 1000.0),
        ),
    )


class MavlinkBridge:
    """
    Main MAVLink bridge.
    
    Connects to MAVProxy via UDP and bridges between:
    - ZMQ (setpoints from control, battery from GPIO)
    - MAVLink (FC commands, QGC commands, telemetry)
    """

    def __init__(self, config: MavlinkConfig):
        """
        Initialize MAVLink bridge.
        
        Args:
            config: MAVLink configuration
        """
        self.config = config
        
        # MAVLink connection
        self._connection = None
        
        # Components
        self._offboard: Optional[OffboardSession] = None
        self._cmd_parser = UserCommandParser()
        self._telemetry_sender: Optional[CustomTelemetrySender] = None
        self._telemetry_receiver = TelemetryReceiver(config.telemetry)
        self._failsafe = FailsafeManager(config.failsafe)
        
        # ZMQ
        self._publisher = ZmqPublisher(BusPorts.pub_endpoint(BusPorts.MAVLINK))
        self._setpoint_sub = ZmqSubscriber(BusPorts.sub_endpoint(BusPorts.CONTROL))
        self._battery_sub = ZmqSubscriber(BusPorts.sub_endpoint(BusPorts.ESP32_GPIO))
        
        self._setpoint_sub.subscribe("setpoints")
        self._battery_sub.subscribe("battery_state")
        
        # State
        self._running = False
        self._tracking_active = False
        self._current_setpoint = Setpoint.neutral()
        self._current_battery: Optional[BatteryState] = None
        
        logger.info("MavlinkBridge initialized")

    def connect(self) -> bool:
        """
        Connect to MAVProxy via UDP.
        
        Returns:
            True if connected successfully
        """
        if not PYMAVLINK_AVAILABLE:
            logger.warning("pymavlink not available - stub mode active")
            return True

        try:
            connection_string = f"udpin:{self.config.udp_host}:{self.config.udp_port}"
            logger.info(f"Connecting to {connection_string}")
            
            self._connection = mavutil.mavlink_connection(connection_string)
            
            # Wait for heartbeat
            logger.info("Waiting for heartbeat...")
            self._connection.wait_heartbeat(timeout=10)
            logger.info(f"Connected to system {self._connection.target_system}")
            
            # Initialize components that need connection
            self._offboard = OffboardSession(self._connection, self.config.offboard)
            self._telemetry_sender = CustomTelemetrySender(self._connection)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def start(self) -> None:
        """Start MAVLink bridge."""
        if not self.connect():
            logger.error("Failed to connect - running in degraded mode")

        logger.info("Starting MAVLink bridge...")
        self._running = True
        
        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("MAVLink bridge interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop MAVLink bridge."""
        self._running = False
        
        # Stop offboard if active
        if self._offboard and self._offboard.is_active:
            self._offboard.stop()
        
        # Close ZMQ
        self._publisher.close()
        self._setpoint_sub.close()
        self._battery_sub.close()
        
        logger.info("MAVLink bridge stopped")

    def _run_loop(self) -> None:
        """Main processing loop."""
        receive_period = 1.0 / self.config.receive_rate_hz
        
        while self._running:
            loop_start = time.time()
            
            # Receive MAVLink messages
            self._receive_mavlink()
            
            # Receive ZMQ messages
            self._receive_zmq()
            
            # Update failsafe
            self._update_failsafe()
            
            # Send custom telemetry
            self._send_telemetry()
            
            # Update offboard setpoint
            if self._offboard and self._offboard.is_active:
                if self._failsafe.should_command_neutral:
                    self._offboard.update_setpoint(Setpoint.neutral())
                else:
                    self._offboard.update_setpoint(self._current_setpoint)
            
            # Rate limiting
            elapsed = time.time() - loop_start
            if elapsed < receive_period:
                time.sleep(receive_period - elapsed)

    def _receive_mavlink(self) -> None:
        """Receive and process MAVLink messages."""
        if not self._connection:
            return

        while True:
            msg = self._connection.recv_match(blocking=False)
            if msg is None:
                break
            
            # Process telemetry
            self._telemetry_receiver.process_message(msg)
            
            # Process user commands
            cmd = self._cmd_parser.parse(msg)
            if cmd:
                self._handle_command(cmd)

    def _receive_zmq(self) -> None:
        """Receive ZMQ messages."""
        # Receive setpoints
        while True:
            result = self._setpoint_sub.receive(timeout_ms=0)
            if result is None:
                break
            topic, msg = result
            if isinstance(msg, Setpoint):
                self._current_setpoint = msg
            elif isinstance(msg, dict):
                self._current_setpoint = Setpoint(
                    roll_deg=msg.get('roll_deg', 0.0),
                    pitch_deg=msg.get('pitch_deg', 0.0),
                    thrust=msg.get('thrust', 0.0),
                    yaw_deg=msg.get('yaw_deg', 0.0),
                )
        
        # Receive battery state
        while True:
            result = self._battery_sub.receive(timeout_ms=0)
            if result is None:
                break
            topic, msg = result
            if isinstance(msg, BatteryState):
                self._current_battery = msg
            elif isinstance(msg, dict):
                self._current_battery = BatteryState(
                    bat1_active=msg.get('bat1_active', False),
                    bat2_active=msg.get('bat2_active', False),
                )

    def _handle_command(self, cmd: UserCommand) -> None:
        """Handle user command from QGC."""
        logger.info(f"Received command: {cmd.cmd_type.name}")
        
        # Publish to ZMQ for other nodes
        self._publisher.publish("qgc_cmds", cmd)
        
        # Handle tracking start/stop locally
        if cmd.cmd_type.name == "START_TRACKING":
            self._tracking_active = True
            if self._offboard and not self._offboard.is_active:
                self._offboard.start()
        elif cmd.cmd_type.name == "STOP_TRACKING":
            self._tracking_active = False
            if self._offboard and self._offboard.is_active:
                self._offboard.stop()

    def _update_failsafe(self) -> None:
        """Update failsafe state."""
        self._failsafe.update(
            track_valid=self._current_setpoint.timestamp > time.time() - 0.5,
            telemetry_valid=self._telemetry_receiver.is_connected,
            lock_valid=self._tracking_active
        )

    def _send_telemetry(self) -> None:
        """Send custom telemetry to QGC."""
        if not self._telemetry_sender:
            return
        
        # Send battery state
        if self._current_battery:
            self._telemetry_sender.send_battery_state(self._current_battery)


def main():
    """Run MAVLink bridge standalone."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="MAVLink Bridge")
    parser.add_argument("--config-dir", default="configs", help="Config directory")
    parser.add_argument("--mode", default="bench_px4_v1_16", help="Mode config name")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = load_mavlink_config(
        os.path.join(args.config_dir, "mavlink.yaml"),
        os.path.join(args.config_dir, "modes", f"{args.mode}.yaml"),
    )

    bridge = MavlinkBridge(config)
    bridge.start()


if __name__ == "__main__":
    main()
