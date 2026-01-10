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
    classes: Optional[List[int]] = None  # Filter specific classes


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
    
    Supports YOLOv8/v9/v10 models.
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
        
        if ULTRALYTICS_AVAILABLE:
            self._model = YOLO(config.model_path)
            logger.info(f"Loaded YOLO model: {config.model_path}")
        else:
            logger.warning("Running in stub mode - no real detections")

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
                classes=self.config.classes,
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
