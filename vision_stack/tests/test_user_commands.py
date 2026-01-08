"""
Tests for user command parsing.

Run with: pytest tests/test_user_commands.py -v
"""

import pytest
from src.common.types import CommandType, UserCommand


class TestCommandType:
    """Test command type enum."""

    def test_all_command_types_exist(self):
        """Verify all expected command types."""
        assert CommandType.START_TRACKING
        assert CommandType.STOP_TRACKING
        assert CommandType.SELECT_TARGET_ID
        assert CommandType.SELECT_TARGET_PIXEL
        assert CommandType.SET_DEPTH_RANGE
        assert CommandType.CLEAR_LOCK
        assert CommandType.REQUEST_TRACK_LIST


class TestUserCommand:
    """Test UserCommand dataclass."""

    def test_start_tracking_command(self):
        """Create start tracking command."""
        cmd = UserCommand(cmd_type=CommandType.START_TRACKING)
        
        assert cmd.cmd_type == CommandType.START_TRACKING
        assert cmd.track_id is None
        assert cmd.pixel_u is None

    def test_select_by_id_command(self):
        """Create select by ID command."""
        cmd = UserCommand(
            cmd_type=CommandType.SELECT_TARGET_ID,
            track_id=42
        )
        
        assert cmd.cmd_type == CommandType.SELECT_TARGET_ID
        assert cmd.track_id == 42

    def test_select_by_pixel_command(self):
        """Create select by pixel command."""
        cmd = UserCommand(
            cmd_type=CommandType.SELECT_TARGET_PIXEL,
            pixel_u=640,
            pixel_v=480
        )
        
        assert cmd.cmd_type == CommandType.SELECT_TARGET_PIXEL
        assert cmd.pixel_u == 640
        assert cmd.pixel_v == 480

    def test_set_depth_range_command(self):
        """Create set depth range command."""
        cmd = UserCommand(
            cmd_type=CommandType.SET_DEPTH_RANGE,
            min_depth=5.0,
            max_depth=30.0
        )
        
        assert cmd.cmd_type == CommandType.SET_DEPTH_RANGE
        assert cmd.min_depth == 5.0
        assert cmd.max_depth == 30.0

    def test_command_has_timestamp(self):
        """Commands should have timestamp."""
        cmd = UserCommand(cmd_type=CommandType.CLEAR_LOCK)
        
        assert cmd.timestamp > 0
