"""
Target lock manager.

Handles target selection, maintaining lock across frames,
and loss-of-track detection.
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..common.types import Track, LockState, LockStatus, BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class LockConfig:
    """Lock manager configuration."""
    lock_timeout_ms: float = 500.0  # Time before lock is considered lost
    reacquire_timeout_ms: float = 2000.0  # Time to try reacquiring before giving up
    iou_threshold: float = 0.3  # IOU threshold for track matching
    max_pixel_distance: float = 100.0  # Max pixel distance for pixel selection


class LockManager:
    """
    Manages target selection and lock.
    
    Supports:
    - Selection by track_id
    - Selection by pixel click (finds nearest track)
    - Maintaining lock across frames via track_id
    - Timeout on loss-of-track
    """

    def __init__(self, config: LockConfig):
        """
        Initialize lock manager.
        
        Args:
            config: Lock configuration
        """
        self.config = config
        
        # Lock state
        self._locked_track_id: Optional[int] = None
        self._lock_timestamp: Optional[float] = None
        self._last_seen_timestamp: Optional[float] = None
        self._lock_bbox: Optional[BoundingBox] = None
        self._status = LockStatus.UNLOCKED
        self._frames_locked = 0
        
        logger.info("LockManager initialized")

    def select_by_id(self, track_id: int, tracks: List[Track]) -> bool:
        """
        Select target by track ID.
        
        Args:
            track_id: ID of track to lock onto
            tracks: Current track list
            
        Returns:
            True if track found and locked
        """
        for track in tracks:
            if track.track_id == track_id:
                self._lock_to_track(track)
                logger.info(f"Locked to track ID {track_id}")
                return True
        
        logger.warning(f"Track ID {track_id} not found in current tracks")
        return False

    def select_by_pixel(self, u: int, v: int, tracks: List[Track]) -> bool:
        """
        Select target by pixel click.
        
        Finds the track whose bbox center is closest to (u, v).
        
        Args:
            u, v: Pixel coordinates of click
            tracks: Current track list
            
        Returns:
            True if a track was found within threshold
        """
        if not tracks:
            logger.warning("No tracks available for pixel selection")
            return False

        # Find track with bbox containing or nearest to click point
        best_track = None
        best_distance = float('inf')
        
        for track in tracks:
            bbox = track.bbox
            cx, cy = bbox.center
            
            # Check if click is inside bbox
            if bbox.x1 <= u <= bbox.x2 and bbox.y1 <= v <= bbox.y2:
                best_track = track
                best_distance = 0
                break
            
            # Otherwise compute distance to center
            distance = ((u - cx) ** 2 + (v - cy) ** 2) ** 0.5
            if distance < best_distance:
                best_distance = distance
                best_track = track

        if best_track and best_distance <= self.config.max_pixel_distance:
            self._lock_to_track(best_track)
            logger.info(f"Locked to track ID {best_track.track_id} via pixel ({u}, {v})")
            return True
        
        logger.warning(f"No track found near pixel ({u}, {v})")
        return False

    def _lock_to_track(self, track: Track) -> None:
        """Lock onto a specific track."""
        self._locked_track_id = track.track_id
        self._lock_timestamp = time.time()
        self._last_seen_timestamp = time.time()
        self._lock_bbox = track.bbox
        self._status = LockStatus.LOCKED
        self._frames_locked = 0

    def update(self, tracks: List[Track]) -> LockState:
        """
        Update lock state with new tracks.
        
        Args:
            tracks: Current track list
            
        Returns:
            Current LockState
        """
        if self._locked_track_id is None:
            return LockState(status=LockStatus.UNLOCKED)

        current_time = time.time()
        
        # Try to find locked track in current tracks
        found_track = None
        for track in tracks:
            if track.track_id == self._locked_track_id:
                found_track = track
                break

        if found_track:
            # Track still visible
            self._last_seen_timestamp = current_time
            self._lock_bbox = found_track.bbox
            self._status = LockStatus.LOCKED
            self._frames_locked += 1
        else:
            # Track not in current frame
            time_since_seen = (current_time - self._last_seen_timestamp) * 1000  # ms
            
            if time_since_seen < self.config.lock_timeout_ms:
                # Still within timeout, keep lock
                self._status = LockStatus.LOCKING  # Searching
            elif time_since_seen < self.config.reacquire_timeout_ms:
                # Trying to reacquire
                self._status = LockStatus.LOST
            else:
                # Give up
                logger.warning(f"Lock lost for track {self._locked_track_id}")
                self.clear_lock()
                return LockState(status=LockStatus.UNLOCKED)

        return LockState(
            status=self._status,
            locked_track_id=self._locked_track_id,
            lock_timestamp=self._lock_timestamp,
            frames_since_lock=self._frames_locked
        )

    def clear_lock(self) -> None:
        """Clear current lock."""
        if self._locked_track_id is not None:
            logger.info(f"Cleared lock on track {self._locked_track_id}")
        
        self._locked_track_id = None
        self._lock_timestamp = None
        self._last_seen_timestamp = None
        self._lock_bbox = None
        self._status = LockStatus.UNLOCKED
        self._frames_locked = 0

    def get_locked_track(self, tracks: List[Track]) -> Optional[Track]:
        """
        Get the currently locked track from a track list.
        
        Args:
            tracks: Current track list
            
        Returns:
            The locked Track, or None if not found
        """
        if self._locked_track_id is None:
            return None
        
        for track in tracks:
            if track.track_id == self._locked_track_id:
                return track
        
        return None

    @property
    def is_locked(self) -> bool:
        """Check if currently locked to a target."""
        return self._status == LockStatus.LOCKED

    def get_lock_state(self) -> LockState:
        """Get current lock state."""
        return LockState(
            status=self._status,
            locked_track_id=self._locked_track_id,
            lock_timestamp=self._lock_timestamp,
            frames_since_lock=self._frames_locked
        )

    @property
    def locked_track_id(self) -> Optional[int]:
        """Get the locked track ID."""
        return self._locked_track_id

    @property
    def locked_bbox(self) -> Optional[BoundingBox]:
        """Get the last known bbox of locked target."""
        return self._lock_bbox

    @property
    def time_since_lock_ms(self) -> Optional[float]:
        """Get time since lock was established in ms."""
        if self._lock_timestamp is None:
            return None
        return (time.time() - self._lock_timestamp) * 1000

    @property
    def time_since_seen_ms(self) -> Optional[float]:
        """Get time since locked target was last seen in ms."""
        if self._last_seen_timestamp is None:
            return None
        return (time.time() - self._last_seen_timestamp) * 1000
