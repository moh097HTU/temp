"""
Multi-object tracker implementation.

Uses ByteTrack or OCSORT for stable track IDs across frames.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple

import numpy as np

from ..common.types import Detection, Track, BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class TrackerConfig:
    """Tracker configuration."""
    max_age: int = 30  # Max frames to keep lost tracks
    min_hits: int = 3  # Min hits before track is confirmed
    iou_threshold: float = 0.3  # IOU threshold for association
    track_buffer: int = 30  # Buffer size for track history


class Tracker(Protocol):
    """Protocol for multi-object trackers."""

    def update(self, detections: List[Detection], frame: np.ndarray) -> List[Track]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of detections from current frame
            frame: Current frame (may be used for appearance features)
            
        Returns:
            List of confirmed tracks
        """
        ...

    def reset(self) -> None:
        """Reset tracker state."""
        ...


class SimpleIOUTracker:
    """
    Simple IOU-based tracker implementation.
    
    For production, use ByteTrack via the ByteTrackTracker wrapper.
    This is a minimal reference implementation.
    """

    def __init__(self, config: TrackerConfig):
        self.config = config
        self._tracks: dict = {}  # track_id -> track_data
        self._next_id = 1
        self._frame_count = 0

    def update(self, detections: List[Detection], frame: np.ndarray) -> List[Track]:
        """Update tracker with new detections."""
        self._frame_count += 1
        
        if not detections:
            # Age out tracks
            self._age_tracks()
            return self._get_confirmed_tracks()

        # Convert detections to matrix format for matching
        det_boxes = np.array([[d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2] 
                              for d in detections])
        
        # Get existing track boxes
        track_ids = list(self._tracks.keys())
        if track_ids:
            track_boxes = np.array([self._tracks[tid]["bbox"] for tid in track_ids])
            
            # Compute IOU matrix
            iou_matrix = self._compute_iou_matrix(det_boxes, track_boxes)
            
            # Greedy matching
            matched_dets = set()
            matched_tracks = set()
            
            while True:
                if iou_matrix.size == 0:
                    break
                max_iou = np.max(iou_matrix)
                if max_iou < self.config.iou_threshold:
                    break
                
                det_idx, track_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                
                # Update matched track
                tid = track_ids[track_idx]
                det = detections[det_idx]
                self._update_track(tid, det)
                
                matched_dets.add(det_idx)
                matched_tracks.add(track_idx)
                
                # Remove matched from consideration
                iou_matrix[det_idx, :] = 0
                iou_matrix[:, track_idx] = 0
            
            # Start new tracks for unmatched detections
            for i, det in enumerate(detections):
                if i not in matched_dets:
                    self._create_track(det)
            
            # Age unmatched tracks
            for i, tid in enumerate(track_ids):
                if i not in matched_tracks:
                    self._tracks[tid]["age"] += 1
        else:
            # No existing tracks, create from all detections
            for det in detections:
                self._create_track(det)

        # Remove old tracks
        self._remove_old_tracks()
        
        return self._get_confirmed_tracks()

    def _compute_iou_matrix(self, boxes1: np.ndarray, boxes2: np.ndarray) -> np.ndarray:
        """Compute IOU between two sets of boxes."""
        n1, n2 = len(boxes1), len(boxes2)
        iou_matrix = np.zeros((n1, n2))
        
        for i in range(n1):
            for j in range(n2):
                iou_matrix[i, j] = self._compute_iou(boxes1[i], boxes2[j])
        
        return iou_matrix

    def _compute_iou(self, box1: np.ndarray, box2: np.ndarray) -> float:
        """Compute IOU between two boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0

    def _create_track(self, det: Detection) -> None:
        """Create a new track from detection."""
        self._tracks[self._next_id] = {
            "bbox": [det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2],
            "class_id": det.class_id,
            "label": det.label,
            "confidence": det.confidence,
            "hits": 1,
            "age": 0,
            "timestamp": det.timestamp
        }
        self._next_id += 1

    def _update_track(self, track_id: int, det: Detection) -> None:
        """Update existing track with new detection."""
        track = self._tracks[track_id]
        track["bbox"] = [det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2]
        track["confidence"] = det.confidence
        track["hits"] += 1
        track["age"] = 0
        track["timestamp"] = det.timestamp

    def _age_tracks(self) -> None:
        """Increment age of all tracks."""
        for tid in self._tracks:
            self._tracks[tid]["age"] += 1

    def _remove_old_tracks(self) -> None:
        """Remove tracks that exceeded max age."""
        to_remove = [tid for tid, t in self._tracks.items() 
                     if t["age"] > self.config.max_age]
        for tid in to_remove:
            del self._tracks[tid]

    def _get_confirmed_tracks(self) -> List[Track]:
        """Get tracks that meet minimum hit requirement."""
        tracks = []
        for tid, t in self._tracks.items():
            if t["hits"] >= self.config.min_hits and t["age"] <= self.config.max_age:
                tracks.append(Track(
                    track_id=tid,
                    bbox=BoundingBox(t["bbox"][0], t["bbox"][1], t["bbox"][2], t["bbox"][3]),
                    class_id=t["class_id"],
                    label=t["label"],
                    confidence=t["confidence"],
                    timestamp=t["timestamp"]
                ))
        return tracks

    def reset(self) -> None:
        """Reset tracker state."""
        self._tracks.clear()
        self._next_id = 1
        self._frame_count = 0


class ByteTrackTracker:
    """
    ByteTrack wrapper for high-performance multi-object tracking.
    
    Requires: pip install supervision bytetrack
    Falls back to SimpleIOUTracker if not available.
    """

    def __init__(self, config: TrackerConfig):
        self.config = config
        self._tracker = None
        
        try:
            # Try to import ByteTrack via supervision
            from supervision import ByteTrack
            self._tracker = ByteTrack(
                track_activation_threshold=0.25,
                lost_track_buffer=config.max_age,
                minimum_matching_threshold=config.iou_threshold,
                frame_rate=30
            )
            logger.info("Using ByteTrack tracker")
        except ImportError:
            logger.warning("ByteTrack not available, using SimpleIOUTracker")
            self._fallback = SimpleIOUTracker(config)

    def update(self, detections: List[Detection], frame: np.ndarray) -> List[Track]:
        """Update tracker with new detections."""
        if self._tracker is None:
            return self._fallback.update(detections, frame)

        try:
            import supervision as sv
            
            if not detections:
                # Create empty detections
                sv_detections = sv.Detections.empty()
            else:
                # Convert to supervision format
                xyxy = np.array([[d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2] 
                                 for d in detections])
                confidence = np.array([d.confidence for d in detections])
                class_id = np.array([d.class_id for d in detections])
                
                sv_detections = sv.Detections(
                    xyxy=xyxy,
                    confidence=confidence,
                    class_id=class_id
                )

            # Run ByteTrack
            tracked = self._tracker.update_with_detections(sv_detections)
            
            # Convert back to Track objects
            tracks = []
            if tracked.tracker_id is not None:
                for i in range(len(tracked)):
                    bbox = tracked.xyxy[i]
                    tracks.append(Track(
                        track_id=int(tracked.tracker_id[i]),
                        bbox=BoundingBox(
                            x1=float(bbox[0]),
                            y1=float(bbox[1]),
                            x2=float(bbox[2]),
                            y2=float(bbox[3])
                        ),
                        class_id=int(tracked.class_id[i]) if tracked.class_id is not None else 0,
                        label=detections[0].label if detections else "unknown",
                        confidence=float(tracked.confidence[i]) if tracked.confidence is not None else 0.0
                    ))
            
            return tracks

        except Exception as e:
            logger.error(f"ByteTrack error: {e}")
            return []

    def reset(self) -> None:
        """Reset tracker state."""
        if self._tracker:
            self._tracker.reset()
        elif hasattr(self, '_fallback'):
            self._fallback.reset()
