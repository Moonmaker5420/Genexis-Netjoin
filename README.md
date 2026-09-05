### Repository description

> Lightweight router-based Wi-Fi new device detector with DHCP monitoring and WhatsApp alerts via self-hosted OpenWA.

---

# README.md

````markdown
# Genexis-DHCP-USER-FINDER


A lightweight Wi-Fi new device detector that monitors the DHCP client list of a compatible router and sends WhatsApp alerts when a previously unseen device appears on the network.

Genexis-DHCP-USER-FINDER is designed for small networks where you want a simple notification when a new device connects, without deploying a full network monitoring platform.

## Features

- 🔐 Automatic router login
- 📋 Retrieves the router's DHCP client list
- 💾 Maintains a local database of previously detected devices
- 🔎 Detects new devices using their MAC address
- 📱 Sends WhatsApp alerts through a self-hosted OpenWA instance
- 🔕 Does not alert when a known device reconnects
- ⏱️ Designed to run periodically using cron
- 🪶 Lightweight Python implementation
- 🔒 Router and OpenWA credentials are stored separately from the application code

## How It Works

```text
                 Router
                    │
                    │ Login
                    ▼
            DHCP Client List
                    │
                    ▼
             Display Clients
                    │
                    ▼
            Compare MAC Address
                    │
          ┌─────────┴─────────┐
          │                   │
       Known MAC           New MAC
          │                   │
          ▼                   ▼
        Ignore         Save to Database
                              │
                              ▼
                       Send WhatsApp
                           Alert
                              │
                              ▼
                           OpenWA
                              │
                              ▼
                    Configured WhatsApp
                         Number
````

## Detection Logic

Genexis-DHCP-USER-FINDER keeps a local record of MAC addresses that have previously been detected.

For every scan:

1. Log in to the router.
2. Retrieve the current DHCP client list.
3. Display the client list.
4. Log out of the router.
5. Compare the current MAC addresses with the local device database.
6. If a MAC address has never been seen before:

   * Record the device.
   * Send a WhatsApp notification through OpenWA.
7. Exit.

Known devices do not generate alerts when they disconnect and reconnect.

## Example

When a new device is detected:

```text
🚨 NEW DEVICE DETECTED

Device: CMF-by-Nothing-Phon
IP: 192.168.1.50
MAC: 32:70:09:05:b7:07
Interface: wlan0
RSSI: -55
Time: 2026-09-05 10:30:00 IST
```

The MAC address is then stored locally.

If the same device reconnects later, no additional notification is generated.

## Requirements

* Linux
* Python 3
* `curl`
* Python `requests`
* A compatible router with a web-based DHCP client list
* Router administrator credentials
* Self-hosted OpenWA instance for WhatsApp notifications

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/Genexis-DHCP-USER-FINDER.git
cd Genexis-DHCP-USER-FINDER

```

Copy the script:

```bash
sudo mkdir -p /opt/netjoin
sudo cp netjoin.py /opt/netjoin/
sudo chmod 755 /opt/netjoin/netjoin.py
```

Install Python dependencies:

```bash
sudo apt update
sudo apt install python3 python3-requests curl
```

## Configuration

### Main configuration

Create:

```bash
sudo nano /etc/netjoin.conf
```

Example:

```ini
OPENWA_URL=http://127.0.0.1:2785/api/sessions/YOUR_SESSION_ID/messages/send-text
OPENWA_API_KEY=YOUR_OPENWA_API_KEY
WHATSAPP_RECIPIENT=YOUR_WHATSAPP_NUMBER
STATE_FILE=/var/lib/netjoin/devices.json
```

### Router configuration

Create:

```bash
sudo nano /etc/netjoin-router.conf
```

Example:

```ini
ROUTER_URL=http://192.168.1.1
ROUTER_USERNAME=admin
ROUTER_PASSWORD=YOUR_ROUTER_PASSWORD
```

Protect the configuration files:

```bash
sudo chmod 600 /etc/netjoin.conf
sudo chmod 600 /etc/netjoin-router.conf
```

## Local Device Database

Genexis-DHCP-USER-FINDER stores previously detected devices in:

```text
/var/lib/netjoin/devices.json
```

Example:

```json
{
  "known": {
    "32:70:09:05:b7:07": {
      "mac": "32:70:09:05:b7:07",
      "ip": "192.168.1.50",
      "device_name": "CMF-by-Nothing-Phon",
      "interface": "wlan0",
      "rssi": "-55",
      "expiry": "..."
    }
  }
}
```

The database is used to determine whether a device has been seen before.

A device is identified by its MAC address.

## Run Manually

Run:

```bash
sudo python3 /opt/netjoin/netjoin.py
```

Example output:

```text
============================================================
NetJoin - New Device Detector
============================================================
[STATE] Known devices: 9
[ROUTER] Login...
[ROUTER] Login successful.

====================================================================================================
[DHCP CLIENT LIST] 7 active client(s)
====================================================================================================
IP Address      MAC Address         Device Name                  Interface       RSSI     Expiry
----------------------------------------------------------------------------------------------------
192.168.1.34    c6:07:0f:77:d6:42   POCO-X6-Neo-5G               wlan0           -45      ...
192.168.1.35    a4:86:db:81:51:f1   IPC_7709                     wlan0           -62      ...
192.168.1.37    28:2e:89:d1:37:ca   DESKTOP-37E6FDJ              wlan0           -38      ...
====================================================================================================

[ROUTER] Logout...
[RESULT] No new devices.
[STATE] Known devices: 9
[DONE]
```

When a new device appears:

```text
[NEW] 192.168.1.55 aa:bb:cc:dd:ee:ff New-Phone
[WHATSAPP] Sent for aa:bb:cc:dd:ee:ff
[RESULT] 1 new device(s)
[STATE] Known devices: 10
[DONE]
```

## Cron

NetJoin is designed to run as a one-shot process.

For example, run it every 30 minutes:

```bash
sudo crontab -e
```

Add:

```cron
*/30 * * * * /usr/bin/python3 /opt/netjoin/netjoin.py >> /var/log/netjoin.log 2>&1
```

Check the cron configuration:

```bash
sudo crontab -l
```

View the log:

```bash
sudo tail -f /var/log/netjoin.log
```

## Why Login and Logout Every Run?

NetJoin intentionally does not maintain a permanent router web session.

Each execution performs:

```text
Login
  ↓
Get DHCP Clients
  ↓
Print Client List
  ↓
Logout
  ↓
Compare Devices
  ↓
Send Alert if New
  ↓
Exit
```

This avoids keeping a router administrator session open until the router's session timeout.

It also makes the script suitable for routers with short or fixed web-session timeouts.

## WhatsApp Notifications

WhatsApp notifications are sent through a self-hosted OpenWA API.

The application itself does not directly communicate with WhatsApp.

```text
NetJoin
   │
   │ HTTP API
   ▼
OpenWA
   │
   ▼
WhatsApp
```

You must have a working OpenWA installation and session before enabling WhatsApp notifications.

## Security

Do not commit credentials to GitHub.

The following files should remain outside the repository:

```text
/etc/netjoin.conf
/etc/netjoin-router.conf
/var/lib/netjoin/devices.json
```

Never place the following directly inside `netjoin.py`:

* Router password
* OpenWA API key
* WhatsApp recipient information

The configuration files should have restricted permissions:

```bash
sudo chmod 600 /etc/netjoin.conf
sudo chmod 600 /etc/netjoin-router.conf
```

## Important: Randomized MAC Addresses

Modern phones may use randomized/private MAC addresses.

For example, the same physical phone may appear with a different MAC address:

```text
Phone
 ├── MAC A → detected as new
 └── MAC B → detected as another new device
```

NetJoin identifies devices by MAC address, so a changed MAC address is treated as a new device.

This is intentional.

## Limitations

* Detection depends on the router exposing connected DHCP clients through its web interface.
* Devices that connect and disconnect between two scans may not be detected.
* MAC randomization can cause the same physical device to appear as multiple devices.
* Router-specific login and DHCP parsing may need modification for different router firmware.
* WhatsApp notifications require a functioning OpenWA installation.

## Project Structure

```text
netjoin/
├── netjoin.py
└── README.md
```

Runtime configuration:

```text
/etc/netjoin.conf
/etc/netjoin-router.conf
```

Runtime device database:

```text
/var/lib/netjoin/devices.json
```

