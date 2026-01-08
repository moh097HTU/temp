"""
ESP32 GPIO bridge node.

Reads battery status from GPIO and publishes to ZMQ bus.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import yaml

from ..common.types import BatteryState
from ..common.bus import ZmqPublisher, BusPorts
from .gpio_reader import GpioReader, GpioConfig

logger = logging.getLogger(__name__)


@dataclass
class Esp32BridgeConfig:
    """ESP32 GPIO bridge configuration."""
    gpio: GpioConfig
    read_rate_hz: float = 20.0  # GPIO read rate
    publish_rate_hz: float = 2.0  # ZMQ publish rate (keep low for bandwidth)


def load_esp32_config(esp32_yaml: str) -> Esp32BridgeConfig:
    """Load configuration from YAML file."""
    with open(esp32_yaml, 'r') as f:
        cfg = yaml.safe_load(f)

    gpio_cfg = cfg.get('gpio', {})
    
    return Esp32BridgeConfig(
        gpio=GpioConfig(
            bat1_pin=gpio_cfg.get('bat1_pin', 17),
            bat2_pin=gpio_cfg.get('bat2_pin', 18),
            debounce_ms=gpio_cfg.get('debounce_ms', 50.0),
            pull_up=gpio_cfg.get('pull_up', True),
            active_low=gpio_cfg.get('active_low', False),
        ),
        read_rate_hz=cfg.get('read_rate_hz', 20.0),
        publish_rate_hz=cfg.get('publish_rate_hz', 2.0),
    )


class Esp32GpioBridge:
    """
    Bridge between ESP32 GPIO signals and ZMQ bus.
    
    Reads battery status at high rate, publishes at low rate
    to conserve bandwidth.
    """

    def __init__(self, config: Esp32BridgeConfig):
        """
        Initialize GPIO bridge.
        
        Args:
            config: Bridge configuration
        """
        self.config = config
        
        # Components
        self._gpio = GpioReader(config.gpio)
        self._publisher = ZmqPublisher(BusPorts.pub_endpoint(BusPorts.ESP32_GPIO))
        
        # State
        self._running = False
        self._last_state: Optional[BatteryState] = None
        self._last_publish_time = 0.0
        
        logger.info("Esp32GpioBridge initialized")

    def start(self) -> None:
        """Start GPIO bridge."""
        logger.info("Starting ESP32 GPIO bridge...")
        self._running = True
        
        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("ESP32 GPIO bridge interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop GPIO bridge."""
        self._running = False
        self._gpio.cleanup()
        self._publisher.close()
        logger.info("ESP32 GPIO bridge stopped")

    def _run_loop(self) -> None:
        """Main processing loop."""
        read_period = 1.0 / self.config.read_rate_hz
        publish_period = 1.0 / self.config.publish_rate_hz
        
        while self._running:
            loop_start = time.time()
            
            # Read GPIO
            state = self._gpio.read()
            
            # Check if state changed or time to publish
            should_publish = False
            
            if self._last_state is None:
                should_publish = True
            elif (state.bat1_active != self._last_state.bat1_active or
                  state.bat2_active != self._last_state.bat2_active):
                # State changed, publish immediately
                should_publish = True
                logger.info(f"Battery state changed: BAT1={state.bat1_active}, BAT2={state.bat2_active}")
            elif time.time() - self._last_publish_time >= publish_period:
                # Periodic publish
                should_publish = True
            
            if should_publish:
                self._publisher.publish("battery_state", state)
                self._last_publish_time = time.time()
            
            self._last_state = state
            
            # Rate limiting
            elapsed = time.time() - loop_start
            if elapsed < read_period:
                time.sleep(read_period - elapsed)

    def read_state(self) -> BatteryState:
        """Read current battery state (for testing)."""
        return self._gpio.read()


def main():
    """Run ESP32 GPIO bridge standalone."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="ESP32 GPIO Bridge")
    parser.add_argument("--config-dir", default="configs", help="Config directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = load_esp32_config(
        os.path.join(args.config_dir, "esp32_gpio.yaml")
    )

    bridge = Esp32GpioBridge(config)
    bridge.start()


if __name__ == "__main__":
    main()
