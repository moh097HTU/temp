# GCS Installation Notes

Setting up the Ground Control Station PC.

## Prerequisites

- Windows 10/11 or Linux
- Custom QGC build (already provided as EXE)
- Network connection to Jetson Nano

## QGC Setup

1. Copy `DroneQGC.exe` to GCS PC
2. Run the executable
3. No installation required (portable)

## Network Configuration

Configure static IP on the interface connected to Jetson:

**Windows:**
1. Open Network Settings
2. Change adapter options
3. Right-click Ethernet adapter → Properties
4. IPv4 → Properties
5. Set:
   - IP: `192.168.1.100`
   - Subnet: `255.255.255.0`
   - Gateway: (leave empty if direct connection)

**Linux:**
```bash
sudo ip addr add 192.168.1.100/24 dev eth0
```

## Firewall

Allow incoming UDP:
- Port 14550 (MAVLink)
- Port 5600 (Video)

**Windows:**
```powershell
netsh advfirewall firewall add rule name="MAVLink" dir=in action=allow protocol=UDP localport=14550
netsh advfirewall firewall add rule name="Video" dir=in action=allow protocol=UDP localport=5600
```

## Video Reception

QGC should automatically receive the video stream.

If testing without QGC:
```bash
# Using GStreamer
gst-launch-1.0 udpsrc port=5600 ! \
  application/x-rtp,payload=96 ! \
  rtph264depay ! avdec_h264 ! autovideosink

# Using VLC
vlc rtp://@:5600
```

## Verification

1. Start Jetson vision stack
2. Launch QGC
3. Check:
   - [ ] Video displays in QGC
   - [ ] Telemetry shows (armed status, mode, etc.)
   - [ ] Track overlay appears when targets detected
   - [ ] Can click to select targets
   - [ ] Battery status updates
