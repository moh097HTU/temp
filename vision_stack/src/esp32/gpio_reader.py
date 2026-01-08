"""
GPIO reader for ESP32 battery signals.

Reads digital inputs from Jetson GPIO and applies debouncing.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from ..common.types import BatteryState
from ..common.filters import Debouncer

logger = logging.getLogger(__name__)

# Try to import Jetson GPIO
try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("Jetson.GPIO not available - running in stub mode")


@dataclass
class GpioConfig:
    """GPIO configuration."""
    bat1_pin: int = 17  # BCM pin for BAT1_ACTIVE
    bat2_pin: int = 18  # BCM pin for BAT2_ACTIVE
    debounce_ms: float = 50.0  # Debounce time in ms
    pull_up: bool = True  # Use internal pull-up resistors
    active_low: bool = False  # If True, low = active


class GpioReader:
    """
    Reads GPIO inputs for battery status.
    
    The ESP32 outputs two digital signals:
    - BAT1_ACTIVE: High when battery 1 is active
    - BAT2_ACTIVE: High when battery 2 is active
    
    These are connected to Jetson GPIO pins and read periodically.
    """

    def __init__(self, config: GpioConfig):
        """
        Initialize GPIO reader.
        
        Args:
            config: GPIO configuration
        """
        self.config = config
        
        # Debouncers
        self._bat1_debouncer = Debouncer(debounce_ms=config.debounce_ms)
        self._bat2_debouncer = Debouncer(debounce_ms=config.debounce_ms)
        
        # Initialize GPIO
        self._initialized = False
        if GPIO_AVAILABLE:
            self._setup_gpio()
        
        logger.info(f"GpioReader initialized (pins: {config.bat1_pin}, {config.bat2_pin})")

    def _setup_gpio(self) -> None:
        """Setup Jetson GPIO pins."""
        try:
            GPIO.setmode(GPIO.BCM)
            
            pull = GPIO.PUD_UP if self.config.pull_up else GPIO.PUD_DOWN
            
            GPIO.setup(self.config.bat1_pin, GPIO.IN, pull_up_down=pull)
            GPIO.setup(self.config.bat2_pin, GPIO.IN, pull_up_down=pull)
            
            self._initialized = True
            logger.info("GPIO pins configured successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")
            self._initialized = False

    def read(self) -> BatteryState:
        """
        Read current battery state.
        
        Returns:
            Debounced BatteryState
        """
        if not GPIO_AVAILABLE or not self._initialized:
            # Stub mode: return default state
            return BatteryState(bat1_active=True, bat2_active=False)

        try:
            # Read raw GPIO values
            raw_bat1 = GPIO.input(self.config.bat1_pin)
            raw_bat2 = GPIO.input(self.config.bat2_pin)
            
            # Apply active-low inversion if configured
            if self.config.active_low:
                raw_bat1 = not raw_bat1
                raw_bat2 = not raw_bat2
            
            # Apply debouncing
            bat1_debounced = self._bat1_debouncer.update(bool(raw_bat1))
            bat2_debounced = self._bat2_debouncer.update(bool(raw_bat2))
            
            return BatteryState(
                bat1_active=bat1_debounced,
                bat2_active=bat2_debounced
            )
            
        except Exception as e:
            logger.error(f"GPIO read error: {e}")
            return BatteryState(bat1_active=False, bat2_active=False)

    def read_raw(self) -> tuple:
        """
        Read raw (non-debounced) GPIO values.
        
        Returns:
            Tuple of (bat1_raw, bat2_raw)
        """
        if not GPIO_AVAILABLE or not self._initialized:
            return (True, False)

        try:
            bat1 = GPIO.input(self.config.bat1_pin)
            bat2 = GPIO.input(self.config.bat2_pin)
            
            if self.config.active_low:
                bat1 = not bat1
                bat2 = not bat2
            
            return (bool(bat1), bool(bat2))
            
        except Exception as e:
            logger.error(f"GPIO read error: {e}")
            return (False, False)

    def cleanup(self) -> None:
        """Cleanup GPIO resources."""
        if GPIO_AVAILABLE and self._initialized:
            try:
                GPIO.cleanup([self.config.bat1_pin, self.config.bat2_pin])
                logger.info("GPIO cleaned up")
            except Exception as e:
                logger.error(f"GPIO cleanup error: {e}")

    def __del__(self):
        self.cleanup()
