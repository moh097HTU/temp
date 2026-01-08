"""
ZMQ message bus for inter-process communication on Jetson.

Provides typed publish/subscribe messaging between vision stack components.
"""

import json
import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Dict, Optional, Tuple, Type, TypeVar

import zmq

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ZmqSerializer:
    """Serialize/deserialize dataclasses to JSON for ZMQ transport."""

    @staticmethod
    def serialize(obj: Any) -> bytes:
        """Serialize object to JSON bytes."""
        if is_dataclass(obj) and not isinstance(obj, type):
            data = asdict(obj)
            data["__type__"] = type(obj).__name__
        elif isinstance(obj, dict):
            data = obj
        else:
            data = {"value": obj}
        return json.dumps(data).encode("utf-8")

    @staticmethod
    def deserialize(data: bytes, type_registry: Optional[Dict[str, Type]] = None) -> Any:
        """Deserialize JSON bytes to object."""
        obj = json.loads(data.decode("utf-8"))
        if isinstance(obj, dict) and "__type__" in obj and type_registry:
            type_name = obj.pop("__type__")
            if type_name in type_registry:
                cls = type_registry[type_name]
                return cls(**obj)
        return obj


class ZmqPublisher:
    """
    Publishes typed messages to a topic.
    
    Usage:
        pub = ZmqPublisher("tcp://*:5555")
        pub.publish("tracks", track_list)
    """

    def __init__(self, endpoint: str, hwm: int = 10):
        """
        Initialize publisher.
        
        Args:
            endpoint: ZMQ endpoint (e.g., "tcp://*:5555")
            hwm: High water mark (message queue limit)
        """
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.PUB)
        self._socket.setsockopt(zmq.SNDHWM, hwm)
        self._socket.bind(endpoint)
        self._endpoint = endpoint
        logger.info(f"Publisher bound to {endpoint}")

    def publish(self, topic: str, message: Any) -> None:
        """
        Publish message to topic.
        
        Args:
            topic: Topic name (e.g., "tracks")
            message: Message object (dataclass or dict)
        """
        try:
            payload = ZmqSerializer.serialize(message)
            self._socket.send_multipart([topic.encode("utf-8"), payload])
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")

    def close(self) -> None:
        """Close publisher socket."""
        self._socket.close()
        logger.info(f"Publisher closed: {self._endpoint}")


class ZmqSubscriber:
    """
    Subscribes to topics with non-blocking receive.
    
    Usage:
        sub = ZmqSubscriber("tcp://localhost:5555")
        sub.subscribe("tracks")
        topic, msg = sub.receive(timeout_ms=100)
    """

    def __init__(
        self,
        endpoint: str,
        type_registry: Optional[Dict[str, Type]] = None,
        hwm: int = 10
    ):
        """
        Initialize subscriber.
        
        Args:
            endpoint: ZMQ endpoint (e.g., "tcp://localhost:5555")
            type_registry: Map of type names to classes for deserialization
            hwm: High water mark (message queue limit)
        """
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.RCVHWM, hwm)
        self._socket.connect(endpoint)
        self._endpoint = endpoint
        self._type_registry = type_registry or {}
        logger.info(f"Subscriber connected to {endpoint}")

    def subscribe(self, topic: str) -> None:
        """Subscribe to a topic."""
        self._socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        logger.debug(f"Subscribed to topic: {topic}")

    def subscribe_all(self) -> None:
        """Subscribe to all topics."""
        self._socket.setsockopt_string(zmq.SUBSCRIBE, "")
        logger.debug("Subscribed to all topics")

    def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        self._socket.setsockopt_string(zmq.UNSUBSCRIBE, topic)
        logger.debug(f"Unsubscribed from topic: {topic}")

    def receive(self, timeout_ms: int = 0) -> Optional[Tuple[str, Any]]:
        """
        Receive message with optional timeout.
        
        Args:
            timeout_ms: Timeout in milliseconds (0 = non-blocking)
            
        Returns:
            Tuple of (topic, message) or None if no message
        """
        if timeout_ms > 0:
            self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        else:
            self._socket.setsockopt(zmq.RCVTIMEO, -1)  # Blocking

        try:
            if timeout_ms == 0:
                # Non-blocking poll
                if self._socket.poll(0) == 0:
                    return None
            
            parts = self._socket.recv_multipart(zmq.NOBLOCK if timeout_ms == 0 else 0)
            if len(parts) >= 2:
                topic = parts[0].decode("utf-8")
                message = ZmqSerializer.deserialize(parts[1], self._type_registry)
                return topic, message
        except zmq.Again:
            return None
        except Exception as e:
            logger.error(f"Failed to receive: {e}")
            return None

        return None

    def close(self) -> None:
        """Close subscriber socket."""
        self._socket.close()
        logger.info(f"Subscriber closed: {self._endpoint}")


class ZmqBus:
    """
    Combined publisher/subscriber bus for simpler usage.
    
    Usage:
        bus = ZmqBus(pub_port=5555, sub_port=5556)
        bus.publish("tracks", track_list)
        bus.subscribe("errors")
        msg = bus.receive()
    """

    # Standard topic names
    TOPIC_TRACKS = "tracks"
    TOPIC_LOCK_STATE = "lock_state"
    TOPIC_ERRORS = "errors"
    TOPIC_SETPOINTS = "setpoints"
    TOPIC_BATTERY = "battery_state"
    TOPIC_QGC_CMDS = "qgc_cmds"
    TOPIC_TELEMETRY = "telemetry"
    TOPIC_FRAMES = "frames"

    def __init__(
        self,
        pub_endpoint: Optional[str] = None,
        sub_endpoints: Optional[list] = None,
        type_registry: Optional[Dict[str, Type]] = None
    ):
        """
        Initialize bus with publisher and optional subscribers.
        
        Args:
            pub_endpoint: Publisher endpoint (e.g., "tcp://*:5555")
            sub_endpoints: List of subscriber endpoints to connect to
            type_registry: Map of type names to classes
        """
        self._publisher: Optional[ZmqPublisher] = None
        self._subscribers: Dict[str, ZmqSubscriber] = {}
        self._type_registry = type_registry or {}

        if pub_endpoint:
            self._publisher = ZmqPublisher(pub_endpoint)

        if sub_endpoints:
            for endpoint in sub_endpoints:
                self._subscribers[endpoint] = ZmqSubscriber(
                    endpoint, self._type_registry
                )

    def publish(self, topic: str, message: Any) -> None:
        """Publish message to topic."""
        if self._publisher:
            self._publisher.publish(topic, message)
        else:
            logger.warning("No publisher configured")

    def subscribe(self, topic: str, endpoint: Optional[str] = None) -> None:
        """Subscribe to topic on all or specific endpoint."""
        if endpoint and endpoint in self._subscribers:
            self._subscribers[endpoint].subscribe(topic)
        else:
            for sub in self._subscribers.values():
                sub.subscribe(topic)

    def receive(self, timeout_ms: int = 0) -> Optional[Tuple[str, Any]]:
        """Receive from any subscribed topic."""
        for sub in self._subscribers.values():
            result = sub.receive(timeout_ms=0)
            if result:
                return result
        
        if timeout_ms > 0:
            # Wait with timeout on first subscriber
            if self._subscribers:
                first_sub = next(iter(self._subscribers.values()))
                return first_sub.receive(timeout_ms=timeout_ms)
        
        return None

    def close(self) -> None:
        """Close all sockets."""
        if self._publisher:
            self._publisher.close()
        for sub in self._subscribers.values():
            sub.close()


# Pre-defined port assignments for vision stack components
class BusPorts:
    """Standard port assignments for ZMQ buses."""
    
    # Each component publishes on its own port
    OAK_BRIDGE = 5550       # Publishes: frames (internal)
    PERCEPTION = 5551       # Publishes: tracks
    TARGETING = 5552        # Publishes: lock_state, errors
    CONTROL = 5553          # Publishes: setpoints
    MAVLINK = 5554          # Publishes: qgc_cmds, telemetry
    ESP32_GPIO = 5555       # Publishes: battery_state

    @staticmethod
    def pub_endpoint(port: int) -> str:
        return f"tcp://*:{port}"

    @staticmethod
    def sub_endpoint(port: int, host: str = "localhost") -> str:
        return f"tcp://{host}:{port}"
