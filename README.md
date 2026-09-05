# NetJoin

A lightweight router-based Wi-Fi new device detector that monitors a compatible router's DHCP client list and sends WhatsApp alerts when a previously unseen device appears on the network.

## Features

- Automatic router login and logout for every run
- Retrieves and prints the current DHCP client list
- Maintains a local database of previously detected MAC addresses
- Alerts only for previously unseen MAC addresses
- No alerts for known devices that disconnect and reconnect
- Optional WhatsApp notifications through a self-hosted OpenWA API
- Designed for periodic execution with cron
- Lightweight Python implementation

## How it works

```text
Router
  │
  │ Login
  ▼
DHCP Client List
  │
  ▼
Print Client List
  │
  ▼
Logout
  │
  ▼
Compare MAC addresses
  │
  ├── Known → Ignore
  │
  └── New → Save → OpenWA → WhatsApp alert
```

Each execution is independent. The router session is not kept open, which is useful for routers with web-session timeouts.

## Requirements

- Linux
- Python 3
- `curl`
- Python `requests`
- Compatible router exposing its DHCP client list through its web interface
- Router administrator credentials
- Self-hosted OpenWA instance if WhatsApp alerts are required

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/netjoin.git
cd netjoin

sudo apt update
sudo apt install python3 python3-requests curl

sudo mkdir -p /opt/netjoin
sudo cp netjoin.py /opt/netjoin/
sudo chmod 755 /opt/netjoin/netjoin.py
```

## Configuration

Create `/etc/netjoin.conf`:

```ini
OPENWA_URL=http://127.0.0.1:2785/api/sessions/YOUR_SESSION_ID/messages/send-text
OPENWA_API_KEY=YOUR_OPENWA_API_KEY
WHATSAPP_RECIPIENT=YOUR_WHATSAPP_RECIPIENT
STATE_FILE=/var/lib/netjoin/devices.json
```

Create `/etc/netjoin-router.conf`:

```ini
ROUTER_URL=http://192.168.1.1
ROUTER_USERNAME=admin
ROUTER_PASSWORD=YOUR_ROUTER_PASSWORD
```

Protect both files:

```bash
sudo chmod 600 /etc/netjoin.conf
sudo chmod 600 /etc/netjoin-router.conf
```

## Local Device Database

Previously detected devices are stored in:

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

A MAC remains known even after the device disconnects.

## Manual Run

```bash
sudo python3 /opt/netjoin/netjoin.py
```

Example:

```text
[STATE] Known devices: 9
[ROUTER] Login...
[ROUTER] Login successful.

[DHCP CLIENT LIST] 7 active client(s)

IP Address      MAC Address         Device Name                  Interface       RSSI     Expiry
----------------------------------------------------------------------------------------------------
192.168.1.34    c6:07:0f:77:d6:42   POCO-X6-Neo-5G               wlan0           -45      ...
192.168.1.35    a4:86:db:81:51:f1   IPC_7709                     wlan0           -62      ...

[ROUTER] Logout...
[RESULT] No new devices.
```

A new MAC produces:

```text
[NEW] 192.168.1.55 aa:bb:cc:dd:ee:ff New-Phone
[WHATSAPP] Sent for aa:bb:cc:dd:ee:ff
[RESULT] 1 new device(s) detected.
```

## Cron

NetJoin is a one-shot script. A 30-minute schedule can be configured with root's crontab:

```bash
sudo crontab -e
```

Add:

```cron
*/30 * * * * /usr/bin/python3 /opt/netjoin/netjoin.py >> /var/log/netjoin.log 2>&1
```

View the log:

```bash
sudo tail -f /var/log/netjoin.log
```

## WhatsApp / OpenWA

If OpenWA is self-hosted, NetJoin uses its HTTP API to send the new-device notification to the configured WhatsApp recipient.

NetJoin does not store or implement WhatsApp authentication itself; it sends the notification through the configured OpenWA endpoint.

## Security

Do not commit credentials or runtime data to GitHub.

Keep these files outside the repository:

```text
/etc/netjoin.conf
/etc/netjoin-router.conf
/var/lib/netjoin/devices.json
```

Never commit:

- Router passwords
- OpenWA API keys
- WhatsApp recipient information
- Real device databases containing private network information

Use:

```bash
sudo chmod 600 /etc/netjoin.conf
sudo chmod 600 /etc/netjoin-router.conf
```

## Randomized MAC Addresses

Modern phones may use private/randomized MAC addresses. If the same physical device changes its MAC address, NetJoin will treat the new MAC as a new device.

This is intentional because detection is MAC-address based.

## Limitations

- Router-specific login and HTML parsing may need modification for other router firmware.
- Devices that connect and disconnect between two scheduled runs may not be detected.
- MAC randomization can make one physical device appear as multiple devices.
- WhatsApp alerts require a working OpenWA installation.
- The current implementation is designed around the tested router's login and DHCP client-list behavior.

## Project Structure

```text
netjoin/
├── netjoin.py
├── README.md
├── netjoin.conf.example
├── netjoin-router.conf.example
├── .gitignore
└── LICENSE
```

## License

MIT License
