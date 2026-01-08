# Network Setup

Network configuration for Jetson ↔ GCS communication.

## Network Topology

```
┌─────────────────┐                    ┌─────────────────┐
│   Jetson Nano   │                    │    GCS PC       │
│                 │                    │                 │
│  192.168.1.10   │◄──── Ethernet ────►│  192.168.1.100  │
│                 │     or WiFi        │                 │
│  UDP 14551 (in) │                    │  QGC            │
│  UDP 5600 (out) │────── Video ──────►│  UDP 5600 (in)  │
└─────────────────┘                    └─────────────────┘
         │
         │ Serial 57600
         ▼
┌─────────────────┐
│  Orange Cube    │
│  TELEM1         │
└─────────────────┘
```

## IP Configuration

### Jetson Nano (Static IP recommended)

```bash
# /etc/netplan/01-network.yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 192.168.1.10/24
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8]
```

Apply: `sudo netplan apply`

### GCS PC

Configure static IP `192.168.1.100/24` on network adapter.

## Firewall Rules

### Jetson

```bash
# Allow MAVLink and video ports
sudo ufw allow 14551/udp  # MAVLink in
sudo ufw allow 5600/udp   # Video out (optional)
```

### GCS PC

Allow incoming on:
- UDP 14550 (MAVLink from MAVProxy)
- UDP 5600 (Video stream)

## WiFi Setup (Alternative)

If using WiFi instead of Ethernet:

### Jetson

```bash
# Connect to network
nmcli dev wifi connect "YourSSID" password "YourPassword"

# Get IP
ip addr show wlan0
```

### Considerations

- WiFi adds latency (5-50ms vs <1ms Ethernet)
- Use 5GHz band for lower latency
- Avoid channel congestion
- Consider dedicated access point

## Testing Connectivity

### From GCS to Jetson

```bash
ping 192.168.1.10
```

### Video Stream Test

```bash
# On GCS, receive test pattern
gst-launch-1.0 udpsrc port=5600 ! \
  application/x-rtp ! rtph264depay ! avdec_h264 ! autovideosink
```

### MAVLink Test

```bash
# On GCS, connect to MAVProxy output
mavproxy.py --master=udp:0.0.0.0:14550
```

## Recommended Hardware

- **Ethernet**: Preferred for reliability and low latency
- **Direct cable**: No switch needed (crossover auto-detected)
- **WiFi adapter**: Intel AC series or better
- **5GHz WiFi**: Lower interference than 2.4GHz
