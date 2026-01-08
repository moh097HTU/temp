"""
User command parser.

Parses MAVLink messages from QGC into UserCommand objects.
Uses custom MAVLink messages for tracking commands.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from ..common.types import UserCommand, CommandType

logger = logging.getLogger(__name__)

# Try to import pymavlink
try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False


# Custom command IDs for tracking (using USER commands range)
# MAV_CMD range 31000-31999 is reserved for user-defined commands
CMD_START_TRACKING = 31100
CMD_STOP_TRACKING = 31101
CMD_SELECT_TARGET_ID = 31102
CMD_SELECT_TARGET_PIXEL = 31103
CMD_SET_DEPTH_RANGE = 31104
CMD_CLEAR_LOCK = 31105
CMD_REQUEST_TRACK_LIST = 31106


class UserCommandParser:
    """
    Parses MAVLink messages into UserCommand objects.
    
    Expected message types:
    - COMMAND_LONG with custom command IDs
    - Named values for simple commands
    """

    def __init__(self):
        logger.info("UserCommandParser initialized")

    def parse(self, msg) -> Optional[UserCommand]:
        """
        Parse a MAVLink message into UserCommand.
        
        Args:
            msg: MAVLink message
            
        Returns:
            UserCommand if recognized, None otherwise
        """
        if not PYMAVLINK_AVAILABLE:
            return None

        msg_type = msg.get_type()

        if msg_type == 'COMMAND_LONG':
            return self._parse_command_long(msg)
        elif msg_type == 'NAMED_VALUE_INT':
            return self._parse_named_value_int(msg)
        elif msg_type == 'NAMED_VALUE_FLOAT':
            return self._parse_named_value_float(msg)
        
        return None

    def _parse_command_long(self, msg) -> Optional[UserCommand]:
        """Parse COMMAND_LONG message."""
        cmd_id = msg.command

        if cmd_id == CMD_START_TRACKING:
            return UserCommand(cmd_type=CommandType.START_TRACKING)
        
        elif cmd_id == CMD_STOP_TRACKING:
            return UserCommand(cmd_type=CommandType.STOP_TRACKING)
        
        elif cmd_id == CMD_SELECT_TARGET_ID:
            # param1 = track_id
            track_id = int(msg.param1)
            return UserCommand(
                cmd_type=CommandType.SELECT_TARGET_ID,
                track_id=track_id
            )
        
        elif cmd_id == CMD_SELECT_TARGET_PIXEL:
            # param1 = u, param2 = v
            pixel_u = int(msg.param1)
            pixel_v = int(msg.param2)
            return UserCommand(
                cmd_type=CommandType.SELECT_TARGET_PIXEL,
                pixel_u=pixel_u,
                pixel_v=pixel_v
            )
        
        elif cmd_id == CMD_SET_DEPTH_RANGE:
            # param1 = min_depth, param2 = max_depth
            min_depth = float(msg.param1)
            max_depth = float(msg.param2)
            return UserCommand(
                cmd_type=CommandType.SET_DEPTH_RANGE,
                min_depth=min_depth,
                max_depth=max_depth
            )
        
        elif cmd_id == CMD_CLEAR_LOCK:
            return UserCommand(cmd_type=CommandType.CLEAR_LOCK)
        
        elif cmd_id == CMD_REQUEST_TRACK_LIST:
            return UserCommand(cmd_type=CommandType.REQUEST_TRACK_LIST)
        
        return None

    def _parse_named_value_int(self, msg) -> Optional[UserCommand]:
        """Parse NAMED_VALUE_INT for simple commands."""
        name = msg.name.rstrip('\x00')  # Remove null padding
        value = msg.value

        if name == "TRK_START" and value == 1:
            return UserCommand(cmd_type=CommandType.START_TRACKING)
        elif name == "TRK_STOP" and value == 1:
            return UserCommand(cmd_type=CommandType.STOP_TRACKING)
        elif name == "TRK_SEL_ID":
            return UserCommand(
                cmd_type=CommandType.SELECT_TARGET_ID,
                track_id=value
            )
        elif name == "TRK_CLEAR" and value == 1:
            return UserCommand(cmd_type=CommandType.CLEAR_LOCK)
        
        return None

    def _parse_named_value_float(self, msg) -> Optional[UserCommand]:
        """Parse NAMED_VALUE_FLOAT (less common)."""
        # Not typically used for commands, but supported
        return None


def send_command_ack(
    connection,
    command_id: int,
    result: int = 0,
    target_system: int = 0,
    target_component: int = 0
) -> None:
    """
    Send COMMAND_ACK response.
    
    Args:
        connection: MAVLink connection
        command_id: Command being acknowledged
        result: Result code (0 = accepted)
        target_system: Target system ID
        target_component: Target component ID
    """
    if not PYMAVLINK_AVAILABLE:
        return

    try:
        connection.mav.command_ack_send(
            command=command_id,
            result=result,
            progress=0,
            result_param2=0,
            target_system=target_system,
            target_component=target_component
        )
    except Exception as e:
        logger.error(f"Failed to send command ACK: {e}")
