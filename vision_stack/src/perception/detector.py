"""
YOLO detector interface and implementation.

Provides object detection using YOLO models.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Protocol

import numpy as np

from ..common.types import Detection, BoundingBox

logger = logging.getLogger(__name__)


# Try to import ultralytics
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    logger.warning("Ultralytics not available - using stub detector")


@dataclass
class DetectorConfig:
    """Detector configuration."""
    model_path: str = "yolov8n.pt"
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.45
    max_detections: int = 100
    device: str = "0"  # CUDA device or "cpu"
    classes: Optional[List[int]] = None  # Filter specific classes (legacy)
    filter_classes: Optional[List] = None  # New: filter by name or ID
    class_names: Optional[dict] = None  # Name to ID mapping


class Detector(Protocol):
    """Protocol for object detectors."""

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect objects in a frame.
        
        Args:
            frame: BGR image as numpy array
            
        Returns:
            List of Detection objects
        """
        ...


class YoloDetector:
    """
    YOLO detector using ultralytics.
    
    Supports YOLOv8/v9/v10/v11 models.
    """

    # COCO class names for reference
    COCO_CLASSES = {
        0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
        5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
        10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench",
        14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
        20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
        25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee",
        30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite", 34: "baseball bat",
        35: "baseball glove", 36: "skateboard", 37: "surfboard", 38: "tennis racket",
        39: "bottle", 40: "wine glass", 41: "cup", 42: "fork", 43: "knife",
        44: "spoon", 45: "bowl", 46: "banana", 47: "apple", 48: "sandwich",
        49: "orange", 50: "broccoli", 51: "carrot", 52: "hot dog", 53: "pizza",
        54: "donut", 55: "cake", 56: "chair", 57: "couch", 58: "potted plant",
        59: "bed", 60: "dining table", 61: "toilet", 62: "tv", 63: "laptop",
        64: "mouse", 65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave",
        69: "oven", 70: "toaster", 71: "sink", 72: "refrigerator", 73: "book",
        74: "clock", 75: "vase", 76: "scissors", 77: "teddy bear", 78: "hair drier",
        79: "toothbrush"
    }

    def __init__(self, config: DetectorConfig):
        """
        Initialize YOLO detector.
        
        Args:
            config: Detector configuration
        """
        self.config = config
        self._model: Optional[YOLO] = None
        self._class_filter: Optional[List[int]] = None
        
        if ULTRALYTICS_AVAILABLE:
            self._model = YOLO(config.model_path)
            logger.info(f"Loaded YOLO model: {config.model_path}")
            
            # Resolve class filter
            self._class_filter = self._resolve_class_filter(config)
            if self._class_filter:
                logger.info(f"Class filter: {self._class_filter}")
        else:
            logger.warning("Running in stub mode - no real detections")

    def _resolve_class_filter(self, config: DetectorConfig) -> Optional[List[int]]:
        """
        Resolve filter_classes to list of class IDs.
        
        Supports:
        - None or "all": no filter
        - List of ints: direct class IDs
        - List of strings: resolve via class_names or COCO
        """
        filter_classes = config.filter_classes
        
        # Handle legacy 'classes' parameter
        if filter_classes is None and config.classes:
            return config.classes
        
        if filter_classes is None or filter_classes == "all":
            return None
        
        if not isinstance(filter_classes, list):
            return None
        
        # Build name-to-ID mapping
        name_to_id = {}
        
        # Add from config class_names
        if config.class_names:
            for class_id, name in config.class_names.items():
                name_to_id[name.lower()] = int(class_id)
        
        # Add from model names if available
        if self._model and hasattr(self._model, 'names'):
            for class_id, name in self._model.names.items():
                name_to_id[name.lower()] = int(class_id)
        
        # Add COCO classes as fallback
        for class_id, name in self.COCO_CLASSES.items():
            if name.lower() not in name_to_id:
                name_to_id[name.lower()] = class_id
        
        # Resolve each item in filter_classes
        resolved = []
        for item in filter_classes:
            if isinstance(item, int):
                resolved.append(item)
            elif isinstance(item, str):
                item_lower = item.lower()
                if item_lower in name_to_id:
                    resolved.append(name_to_id[item_lower])
                else:
                    logger.warning(f"Unknown class name: {item}")
        
        return resolved if resolved else None

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect objects in a frame.
        
        Args:
            frame: BGR image (H, W, 3)
            
        Returns:
            List of Detection objects
        """
        if self._model is None:
            return []

        try:
            results = self._model.predict(
                frame,
                conf=self.config.confidence_threshold,
                iou=self.config.iou_threshold,
                max_det=self.config.max_detections,
                device=self.config.device,
                classes=self._class_filter,  # Use resolved class filter
                verbose=False
            )

            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                for i in range(len(boxes)):
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls = int(boxes.cls[i].cpu().numpy())
                    
                    bbox = BoundingBox(
                        x1=float(xyxy[0]),
                        y1=float(xyxy[1]),
                        x2=float(xyxy[2]),
                        y2=float(xyxy[3])
                    )
                    
                    # Use model's class names if available, fallback to COCO
                    if hasattr(result, 'names') and cls in result.names:
                        label = result.names[cls]
                    else:
                        label = self.COCO_CLASSES.get(cls, f"class_{cls}")
                    
                    detections.append(Detection(
                        bbox=bbox,
                        class_id=cls,
                        label=label,
                        confidence=conf
                    ))

            return detections

        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []


class StubDetector:
    """Stub detector for testing without a model."""

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Return empty detections."""
        return []
