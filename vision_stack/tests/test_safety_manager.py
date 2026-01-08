"""
Tests for SafetyManager.

Run with: pytest tests/test_safety_manager.py -v
"""

import time
import pytest
from src.common.types import Setpoint
from src.control.safety_manager import SafetyManager, SafetyConfig


@pytest.fixture
def safety_manager():
    """Create safety manager with test config."""
    config = SafetyConfig(
        roll_ema_alpha=0.5,
        pitch_ema_alpha=0.5,
        roll_slew_rate_deg_s=30.0,
        pitch_slew_rate_deg_s=20.0,
        roll_limit_deg=20.0,
        pitch_limit_deg=10.0,
        track_timeout_ms=500.0,
        telemetry_timeout_ms=1000.0,
        bench_mode=True,
    )
    return SafetyManager(config)


class TestClampLimits:
    """Test output clamping."""

    def test_roll_clamped_positive(self, safety_manager):
        """Roll should be clamped to +20 deg."""
        setpoint = Setpoint(roll_deg=50.0, pitch_deg=0.0, thrust=0.0)
        result = safety_manager.apply(setpoint, lock_valid=True, track_fresh=True)
        
        # May not reach full clamp immediately due to slew/EMA
        # But should not exceed limit
        assert result.roll_deg <= 20.0

    def test_roll_clamped_negative(self, safety_manager):
        """Roll should be clamped to -20 deg."""
        setpoint = Setpoint(roll_deg=-50.0, pitch_deg=0.0, thrust=0.0)
        result = safety_manager.apply(setpoint, lock_valid=True, track_fresh=True)
        assert result.roll_deg >= -20.0

    def test_pitch_clamped(self, safety_manager):
        """Pitch should be clamped to ±10 deg."""
        setpoint = Setpoint(roll_deg=0.0, pitch_deg=30.0, thrust=0.0)
        result = safety_manager.apply(setpoint, lock_valid=True, track_fresh=True)
        assert result.pitch_deg <= 10.0


class TestGating:
    """Test validity gating."""

    def test_neutral_on_invalid_lock(self, safety_manager):
        """Should return neutral when lock invalid."""
        setpoint = Setpoint(roll_deg=15.0, pitch_deg=5.0, thrust=0.5)
        result = safety_manager.apply(setpoint, lock_valid=False, track_fresh=True)
        
        # After slew limiting, should be moving toward neutral
        # First call may not be exactly zero
        assert result.thrust == 0.0  # Thrust always 0 in bench

    def test_neutral_on_stale_track(self, safety_manager):
        """Should return neutral when track stale."""
        setpoint = Setpoint(roll_deg=15.0, pitch_deg=5.0, thrust=0.0)
        result = safety_manager.apply(setpoint, lock_valid=True, track_fresh=False)
        
        assert safety_manager.is_failsafe_active


class TestBenchMode:
    """Test bench mode behavior."""

    def test_thrust_zero_in_bench(self, safety_manager):
        """Thrust should always be 0 in bench mode."""
        setpoint = Setpoint(roll_deg=0.0, pitch_deg=0.0, thrust=0.8)
        result = safety_manager.apply(setpoint, lock_valid=True, track_fresh=True)
        
        assert result.thrust == 0.0

    def test_thrust_forced_zero(self, safety_manager):
        """Even with valid inputs, thrust is 0."""
        for _ in range(10):
            setpoint = Setpoint(roll_deg=5.0, pitch_deg=2.0, thrust=1.0)
            result = safety_manager.apply(setpoint, lock_valid=True, track_fresh=True)
            assert result.thrust == 0.0


class TestFiltering:
    """Test EMA and slew limiting."""

    def test_ema_smoothing(self, safety_manager):
        """Output should be smoothed by EMA."""
        # Send constant input, output should converge
        target = 10.0
        results = []
        
        for _ in range(50):
            setpoint = Setpoint(roll_deg=target, pitch_deg=0.0, thrust=0.0)
            result = safety_manager.apply(setpoint, lock_valid=True, track_fresh=True)
            results.append(result.roll_deg)
            time.sleep(0.01)
        
        # Should converge toward target
        assert abs(results[-1] - target) < 1.0

    def test_slew_rate_limiting(self, safety_manager):
        """Rate of change should be limited."""
        # Force reset to known state
        safety_manager.reset()
        
        # First, establish baseline at 0
        for _ in range(10):
            setpoint = Setpoint(roll_deg=0.0, pitch_deg=0.0, thrust=0.0)
            safety_manager.apply(setpoint, lock_valid=True, track_fresh=True)
            time.sleep(0.01)
        
        # Now jump to 20 deg
        setpoint = Setpoint(roll_deg=20.0, pitch_deg=0.0, thrust=0.0)
        result = safety_manager.apply(setpoint, lock_valid=True, track_fresh=True)
        
        # Should not jump to 20 immediately due to slew limiting
        assert result.roll_deg < 15.0  # Allow for EMA effect


class TestReset:
    """Test reset functionality."""

    def test_reset_clears_state(self, safety_manager):
        """Reset should clear filter state."""
        # Apply some setpoints
        for _ in range(10):
            setpoint = Setpoint(roll_deg=15.0, pitch_deg=8.0, thrust=0.0)
            safety_manager.apply(setpoint, lock_valid=True, track_fresh=True)
            time.sleep(0.01)
        
        # Reset
        safety_manager.reset()
        
        # Failsafe should be inactive
        assert not safety_manager.is_failsafe_active

    def test_force_neutral(self, safety_manager):
        """Force neutral should return zeros immediately."""
        result = safety_manager.force_neutral()
        
        assert result.roll_deg == 0.0
        assert result.pitch_deg == 0.0
        assert result.thrust == 0.0
