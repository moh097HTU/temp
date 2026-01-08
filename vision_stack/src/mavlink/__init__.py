"""MAVLink module - FC and QGC communication."""

from .setpoints_attitude import (
    build_attitude_target_quaternion,
    build_attitude_target_message,
    send_attitude_target,
)
from .offboard_session import OffboardSession, OffboardConfig
from .user_commands import UserCommandParser, send_command_ack
from .custom_telemetry import CustomTelemetrySender
from .telemetry import TelemetryReceiver, TelemetryConfig
from .failsafe import FailsafeManager, FailsafeConfig, FailsafeState, FailsafeAction
from .mavlink_bridge import MavlinkBridge, MavlinkConfig, load_mavlink_config

__all__ = [
    # Setpoints
    "build_attitude_target_quaternion",
    "build_attitude_target_message",
    "send_attitude_target",
    # Offboard
    "OffboardSession",
    "OffboardConfig",
    # Commands
    "UserCommandParser",
    "send_command_ack",
    # Telemetry
    "CustomTelemetrySender",
    "TelemetryReceiver",
    "TelemetryConfig",
    # Failsafe
    "FailsafeManager",
    "FailsafeConfig",
    "FailsafeState",
    "FailsafeAction",
    # Bridge
    "MavlinkBridge",
    "MavlinkConfig",
    "load_mavlink_config",
]
