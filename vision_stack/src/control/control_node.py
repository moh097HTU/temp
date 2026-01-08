"""
Control node - orchestrates control mapping and safety.

Subscribes to errors from targeting, applies control and safety,
publishes setpoints to MAVLink bridge.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import yaml

from ..common.types import Errors, Setpoint
from ..common.bus import ZmqPublisher, ZmqSubscriber, BusPorts
from .control_mapper import ControlMapper, ControlConfig, ControlGains, ControlLimits
from .safety_manager import SafetyManager, SafetyConfig

logger = logging.getLogger(__name__)


@dataclass
class ControlNodeConfig:
    """Control node configuration."""
    control: ControlConfig
    safety: SafetyConfig
    update_rate_hz: float = 30.0


def load_control_config(control_yaml: str, mode_yaml: str) -> ControlNodeConfig:
    """Load configuration from YAML files."""
    with open(control_yaml, 'r') as f:
        control_cfg = yaml.safe_load(f)
    with open(mode_yaml, 'r') as f:
        mode_cfg = yaml.safe_load(f)

    mode = mode_cfg.get('mode', 'bench')
    is_bench = mode == 'bench'
    
    ctrl = mode_cfg.get('control', {})
    safety_cfg = mode_cfg.get('safety', {})

    return ControlNodeConfig(
        control=ControlConfig(
            gains=ControlGains(
                yaw_to_roll=control_cfg.get('gains', {}).get('yaw_to_roll', 30.0),
                pitch_to_pitch=control_cfg.get('gains', {}).get('pitch_to_pitch', 20.0),
                range_to_thrust=ctrl.get('range_to_thrust_gain', 0.05),
            ),
            limits=ControlLimits(
                roll_min_deg=-ctrl.get('roll_limit_deg', 20.0),
                roll_max_deg=ctrl.get('roll_limit_deg', 20.0),
                pitch_min_deg=-ctrl.get('pitch_limit_deg', 10.0),
                pitch_max_deg=ctrl.get('pitch_limit_deg', 10.0),
                thrust_min=0.0,
                thrust_max=ctrl.get('thrust_max', 0.8),
            ),
            thrust_enabled=ctrl.get('thrust_enabled', False),
            yaw_deadband_rad=control_cfg.get('deadband', {}).get('yaw_rad', 0.02),
            pitch_deadband_rad=control_cfg.get('deadband', {}).get('pitch_rad', 0.02),
            range_deadband_m=control_cfg.get('deadband', {}).get('range_m', 0.5),
        ),
        safety=SafetyConfig(
            roll_ema_alpha=ctrl.get('roll_ema_alpha', 0.3),
            pitch_ema_alpha=ctrl.get('pitch_ema_alpha', 0.3),
            roll_slew_rate_deg_s=ctrl.get('roll_slew_rate_deg_s', 30.0),
            pitch_slew_rate_deg_s=ctrl.get('pitch_slew_rate_deg_s', 20.0),
            roll_limit_deg=ctrl.get('roll_limit_deg', 20.0),
            pitch_limit_deg=ctrl.get('pitch_limit_deg', 10.0),
            track_timeout_ms=safety_cfg.get('track_timeout_ms', 500.0),
            telemetry_timeout_ms=safety_cfg.get('telemetry_timeout_ms', 1000.0),
            bench_mode=is_bench,
        ),
        update_rate_hz=control_cfg.get('update_rate_hz', 30.0),
    )


class ControlNode:
    """
    Control node.
    
    Subscribes to:
    - errors from targeting
    
    Publishes:
    - setpoints to MAVLink bridge
    """

    def __init__(self, config: ControlNodeConfig):
        """
        Initialize control node.
        
        Args:
            config: Control node configuration
        """
        self.config = config
        
        # Components
        self._mapper = ControlMapper(config.control)
        self._safety = SafetyManager(config.safety)
        
        # ZMQ
        self._publisher = ZmqPublisher(BusPorts.pub_endpoint(BusPorts.CONTROL))
        self._error_sub = ZmqSubscriber(BusPorts.sub_endpoint(BusPorts.TARGETING))
        self._error_sub.subscribe("errors")
        
        # State
        self._running = False
        self._last_errors: Optional[Errors] = None
        self._frame_count = 0
        
        logger.info(f"ControlNode initialized (bench={config.safety.bench_mode})")

    def start(self) -> None:
        """Start control node."""
        logger.info("Starting control node...")
        self._running = True
        
        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("Control node interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop control node."""
        self._running = False
        
        # Send neutral setpoints before stopping
        neutral = self._safety.force_neutral()
        self._publisher.publish("setpoints", neutral)
        
        self._publisher.close()
        self._error_sub.close()
        logger.info("Control node stopped")

    def _run_loop(self) -> None:
        """Main processing loop."""
        target_period = 1.0 / self.config.update_rate_hz
        
        while self._running:
            loop_start = time.time()
            
            # Get latest errors
            self._receive_errors()
            
            # Compute and publish setpoint
            setpoint = self._compute_setpoint()
            self._publisher.publish("setpoints", setpoint)
            
            self._frame_count += 1
            
            # Rate limiting
            elapsed = time.time() - loop_start
            if elapsed < target_period:
                time.sleep(target_period - elapsed)

            # Periodic logging
            if self._frame_count % 100 == 0:
                self._log_status(setpoint)

    def _receive_errors(self) -> None:
        """Receive latest errors from targeting."""
        while True:
            result = self._error_sub.receive(timeout_ms=0)
            if result is None:
                break
            
            topic, msg = result
            if isinstance(msg, Errors):
                self._last_errors = msg
            elif isinstance(msg, dict):
                # Reconstruct from dict
                self._last_errors = Errors(
                    yaw_error=msg.get('yaw_error', 0.0),
                    pitch_error=msg.get('pitch_error', 0.0),
                    range_error=msg.get('range_error', 0.0),
                    track_valid=msg.get('track_valid', False),
                    depth_valid=msg.get('depth_valid', False),
                    lock_valid=msg.get('lock_valid', False),
                )

    def _compute_setpoint(self) -> Setpoint:
        """Compute safe setpoint from errors."""
        if self._last_errors is None:
            return Setpoint.neutral()
        
        # Map errors to raw setpoint
        raw_setpoint = self._mapper.map(self._last_errors)
        
        # Apply safety constraints
        safe_setpoint = self._safety.apply(
            setpoint=raw_setpoint,
            lock_valid=self._last_errors.lock_valid,
            track_fresh=self._last_errors.track_valid,
            telemetry_fresh=True  # TODO: Get from MAVLink
        )
        
        return safe_setpoint

    def _log_status(self, setpoint: Setpoint) -> None:
        """Log periodic status."""
        if self._last_errors:
            logger.debug(
                f"Frame {self._frame_count}: "
                f"yaw_err={self._last_errors.yaw_error:.3f} "
                f"pitch_err={self._last_errors.pitch_error:.3f} "
                f"→ roll={setpoint.roll_deg:.1f}° pitch={setpoint.pitch_deg:.1f}° "
                f"thrust={setpoint.thrust:.2f}"
            )


def main():
    """Run control node standalone."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Control Node")
    parser.add_argument("--config-dir", default="configs", help="Config directory")
    parser.add_argument("--mode", default="bench_px4_v1_16", help="Mode config name")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = load_control_config(
        os.path.join(args.config_dir, "control.yaml"),
        os.path.join(args.config_dir, "modes", f"{args.mode}.yaml"),
    )

    node = ControlNode(config)
    node.start()


if __name__ == "__main__":
    main()
