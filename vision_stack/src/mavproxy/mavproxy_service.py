"""
MAVProxy service management.

Provides utilities for starting/stopping MAVProxy as a service.
"""

import logging
import subprocess
import time
from typing import Optional

from .mavproxy_cmd_builder import MavproxyConfig, build_mavproxy_command

logger = logging.getLogger(__name__)


class MavproxyService:
    """
    Manages MAVProxy process.
    
    Can be used to start/stop MAVProxy programmatically,
    though typically MAVProxy runs as a systemd service.
    """

    def __init__(self, config: MavproxyConfig):
        """
        Initialize MAVProxy service.
        
        Args:
            config: MAVProxy configuration
        """
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        
        logger.info("MavproxyService initialized")

    def start(self) -> bool:
        """
        Start MAVProxy process.
        
        Returns:
            True if started successfully
        """
        if self._process and self._process.poll() is None:
            logger.warning("MAVProxy already running")
            return True

        cmd = build_mavproxy_command(self.config)
        try:
            logger.info(f"Starting MAVProxy: {' '.join(cmd)}")
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait briefly to check if it started
            time.sleep(0.5)
            
            if self._process.poll() is not None:
                # Process exited immediately
                stdout, stderr = self._process.communicate()
                logger.error(f"MAVProxy failed to start: {stderr.decode()}")
                return False
            
            logger.info(f"MAVProxy started (PID: {self._process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MAVProxy: {e}")
            return False

    def stop(self) -> None:
        """Stop MAVProxy process."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
                logger.info("MAVProxy stopped")
            except subprocess.TimeoutExpired:
                self._process.kill()
                logger.warning("MAVProxy killed (didn't terminate gracefully)")
            except Exception as e:
                logger.error(f"Failed to stop MAVProxy: {e}")
            finally:
                self._process = None

    def is_running(self) -> bool:
        """Check if MAVProxy is running."""
        if self._process:
            return self._process.poll() is None
        return False

    @property
    def pid(self) -> Optional[int]:
        """Get MAVProxy process ID."""
        if self._process and self._process.poll() is None:
            return self._process.pid
        return None
