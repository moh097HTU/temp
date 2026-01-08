"""
Tests for SET_ATTITUDE_TARGET builder.

Run with: pytest tests/test_setpoints_attitude.py -v
"""

import math
import pytest
from src.common.types import Setpoint
from src.mavlink.setpoints_attitude import (
    build_attitude_target_quaternion,
    DEFAULT_TYPE_MASK,
)


class TestQuaternionBuilder:
    """Test quaternion construction from Euler angles."""

    def test_identity_quaternion(self):
        """Zero angles should give identity quaternion."""
        q = build_attitude_target_quaternion(0.0, 0.0, 0.0)
        
        assert abs(q[0] - 1.0) < 0.001  # w ≈ 1
        assert abs(q[1]) < 0.001        # x ≈ 0
        assert abs(q[2]) < 0.001        # y ≈ 0
        assert abs(q[3]) < 0.001        # z ≈ 0

    def test_pure_roll(self):
        """Pure roll should only affect x component."""
        q = build_attitude_target_quaternion(45.0, 0.0, 0.0)
        
        # For 45° roll: w ≈ 0.924, x ≈ 0.383
        assert abs(q[0] - 0.924) < 0.01
        assert abs(q[1] - 0.383) < 0.01
        assert abs(q[2]) < 0.01
        assert abs(q[3]) < 0.01

    def test_pure_pitch(self):
        """Pure pitch should only affect y component."""
        q = build_attitude_target_quaternion(0.0, 30.0, 0.0)
        
        # For 30° pitch: w ≈ 0.966, y ≈ 0.259
        assert abs(q[0] - 0.966) < 0.01
        assert abs(q[1]) < 0.01
        assert abs(q[2] - 0.259) < 0.01
        assert abs(q[3]) < 0.01

    def test_quaternion_normalized(self):
        """Quaternion should always be normalized."""
        for roll in [-45, 0, 45]:
            for pitch in [-30, 0, 30]:
                q = build_attitude_target_quaternion(float(roll), float(pitch), 0.0)
                norm = math.sqrt(sum(x*x for x in q))
                assert abs(norm - 1.0) < 0.001

    def test_negative_angles(self):
        """Negative angles should work correctly."""
        q_pos = build_attitude_target_quaternion(20.0, 10.0, 0.0)
        q_neg = build_attitude_target_quaternion(-20.0, -10.0, 0.0)
        
        # w should be same (symmetric)
        assert abs(q_pos[0] - q_neg[0]) < 0.01
        # x and y should be opposite
        assert abs(q_pos[1] + q_neg[1]) < 0.01
        assert abs(q_pos[2] + q_neg[2]) < 0.01


class TestTypeMask:
    """Test type mask configuration."""

    def test_type_mask_ignores_rates(self):
        """Type mask should ignore body rates."""
        # Bits 0-2 should be set (ignore roll/pitch/yaw rates)
        assert DEFAULT_TYPE_MASK & 0b111 == 0b111

    def test_type_mask_uses_attitude(self):
        """Type mask should NOT ignore attitude."""
        # Bit 7 (attitude ignore) should NOT be set
        assert not (DEFAULT_TYPE_MASK & 128)


class TestBenchModeThrust:
    """Test thrust behavior in bench mode."""

    def test_setpoint_neutral_has_zero_thrust(self):
        """Neutral setpoint should have zero thrust."""
        neutral = Setpoint.neutral()
        assert neutral.thrust == 0.0

    def test_setpoint_properties(self):
        """Verify setpoint structure."""
        sp = Setpoint(roll_deg=15.0, pitch_deg=5.0, thrust=0.0, yaw_deg=0.0)
        
        assert sp.roll_deg == 15.0
        assert sp.pitch_deg == 5.0
        assert sp.thrust == 0.0
        assert sp.yaw_deg == 0.0
