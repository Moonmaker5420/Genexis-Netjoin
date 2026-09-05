#!/usr/bin/env python3
"""NetJoin: lightweight router DHCP new-device detector."""

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from urllib.parse import quote

import requests

CONFIG_FILE = "/etc/netjoin.conf"
ROUTER_CONFIG = "/etc/netjoin-router.conf"


def load_config_file(filename):
    config = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()
    return config


config = load_config_file(CONFIG_FILE)
router_config = load_config_file(ROUTER_CONFIG)

OPENWA_URL = config["OPENWA_URL"]
OPENWA_API_KEY = config["OPENWA_API_KEY"]
WHATSAPP_RECIPIENT = config["WHATSAPP_RECIPIENT"]
STATE_FILE = config.get("STATE_FILE", "/var/lib/netjoin/devices.json")

ROUTER_URL = router_config.get("ROUTER_URL", "http://192.168.1.1")
ROUTER_USERNAME = router_config.get("ROUTER_USERNAME", "admin")
ROUTER_PASSWORD = router_config["ROUTER_PASSWORD"]


def js_encode(value):
    encoded = quote(value, safe="-_.!~*'()")
    for char, replacement in {
        "!": "%21", "'": "%27", "(": "%28",
        ")": "%29", "~": "%7E",
    }.items():
        encoded = encoded.replace(char, replacement)
    return encoded.replace("%20", "+")


def js_int32(value):
    value &= 0xffffffff
    return value - 0x100000000 if value & 0x80000000 else value


def make_checksum(data):
    csum = 0
    for i in range(0, len(data), 4):
        c1 = ord(data[i]) if i < len(data) else 0
        c2 = ord(data[i + 1]) if i + 1 < len(data) else 0
        c3 = ord(data[i + 2]) if i + 2 < len(data) else 0
        c4 = ord(data[i + 3]) if i + 3 < len(data) else 0
        csum += (c1 << 24) + (c2 << 16) + (c3 << 8) + c4
    csum = js_int32(csum)
    csum = (csum & 0xffff) + (csum >> 16)
    return str((~csum) & 0xffff)


def curl(args):
    result = subprocess.run(
        ["/usr/bin/curl", "--http0.9", "-sS"] + args,
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def router_login(cookie_file):
    print("[ROUTER] Login...")
    login_page = curl([f"{ROUTER_URL}/admin/login.asp"])

    match = re.search(r'code\s*=\s*"([^"]+)"', login_page)
    if not match:
        raise RuntimeError("Could not find router CAPTCHA")

    fields = [
        ("challenge", ""),
        ("username", ROUTER_USERNAME),
        ("password", ROUTER_PASSWORD),
        ("captchaTextBox", match.group(1)),
        ("save", "Login"),
        ("submit-url", "/admin/login.asp"),
    ]

    data = "".join(
        js_encode(name) + "=" + js_encode(value) + "&"
        for name, value in fields
    )
    data += "postSecurityFlag=" + make_checksum(data) + "&"

    fd, post_file = tempfile.mkstemp(prefix="netjoin-", suffix=".post", dir="/run")
    os.close(fd)
    os.chmod(post_file, 0o600)
    response_file = post_file + ".response"

    try:
        with open(post_file, "w", encoding="utf-8") as f:
            f.write(data)

        curl([
            "-c", cookie_file, "-b", cookie_file,
            "-H", "Content-Type: application/x-www-form-urlencoded",
            "--data-binary", f"@{post_file}",
            "-o", response_file,
            f"{ROUTER_URL}/boaform/admin/formLogin",
        ])

        page = curl([
            "-b", cookie_file,
            f"{ROUTER_URL}/admin/status_client_list.asp",
        ])

        if "You have not logined" in page:
            raise RuntimeError("Router login failed")
        if "Active DHCP Clients" not in page:
            raise RuntimeError("Router login verification failed")

        print("[ROUTER] Login successful.")
    finally:
        for path in (post_file, response_file):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def router_logout(cookie_file):
    print("[ROUTER] Logout...")
    try:
        data = (
            "save=" + js_encode("Logout") +
            "&submit-url=" + js_encode("/admin/logout.asp") + "&"
        )
        data += "postSecurityFlag=" + make_checksum(data) + "&"

        fd, post_file = tempfile.mkstemp(prefix="netjoin-", suffix=".post", dir="/run")
        os.close(fd)
        os.chmod(post_file, 0o600)

        try:
            with open(post_file, "w", encoding="utf-8") as f:
                f.write(data)

            curl([
                "-b", cookie_file, "-c", cookie_file,
                "-H", "Content-Type: application/x-www-form-urlencoded",
                "--data-binary", f"@{post_file}",
                f"{ROUTER_URL}/boaform/admin/formLogout",
            ])
        finally:
            try:
                os.unlink(post_file)
            except FileNotFoundError:
                pass
    except Exception as error:
        print(f"[ROUTER] Logout warning: {error}")


def get_clients(cookie_file):
    page = curl([
        "-b", cookie_file,
        f"{ROUTER_URL}/admin/status_client_list.asp",
    ])
    if "You have not logined" in page:
        raise RuntimeError("Router session expired during scan")
    if "Active DHCP Clients" not in page:
        raise RuntimeError("Unexpected router client page")
    return parse_clients(page)


def parse_clients(page):
    devices = {}
    rows = re.findall(r"<tr>(.*?)</tr>", page, re.DOTALL | re.IGNORECASE)

    for row in rows:
        cells = re.findall(r"<td>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 6:
            continue

        values = [re.sub(r"<[^>]+>", "", cell).strip() for cell in cells]
        mac, ip, name, interface, rssi, expiry = values[:6]

        mac = mac.lower()
        if not re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", mac):
            continue

        devices[mac] = {
            "mac": mac,
            "ip": ip,
            "device_name": name or "Unknown",
            "interface": interface or "Unknown",
            "rssi": rssi or "N/A",
            "expiry": expiry or "",
        }

    return devices


def print_client_list(clients):
    print()
    print("=" * 100)
    print(f"[DHCP CLIENT LIST] {len(clients)} active client(s)")
    print("=" * 100)

    if not clients:
        print("No active DHCP clients found.")
        print()
        return

    print(
        f"{'IP Address':15} {'MAC Address':19} "
        f"{'Device Name':28} {'Interface':15} "
        f"{'RSSI':8} {'Expiry':10}"
    )
    print("-" * 100)

    for device in clients.values():
        print(
            f"{device['ip'][:15]:15} "
            f"{device['mac']:19} "
            f"{device['device_name'][:27]:28} "
            f"{device['interface'][:14]:15} "
            f"{device['rssi'][:7]:8} "
            f"{device['expiry'][:9]:10}"
        )

    print("=" * 100)
    print()


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("known", {})
    except FileNotFoundError:
        return {}


def save_state(known):
    directory = os.path.dirname(STATE_FILE)
    os.makedirs(directory, exist_ok=True)
    temporary = STATE_FILE + ".tmp"

    with open(temporary, "w", encoding="utf-8") as f:
        json.dump({"known": known}, f, indent=2)

    os.replace(temporary, STATE_FILE)


def send_whatsapp(message):
    response = requests.post(
        OPENWA_URL,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": OPENWA_API_KEY,
        },
        json={
            "chatId": WHATSAPP_RECIPIENT,
            "text": message,
        },
        timeout=15,
    )
    response.raise_for_status()


def make_message(device):
    now = datetime.now().astimezone()
    return (
        "🚨 NEW DEVICE DETECTED\n\n"
        f"Device: {device.get('device_name', 'Unknown')}\n"
        f"IP: {device.get('ip', '?')}\n"
        f"MAC: {device.get('mac', '?')}\n"
        f"Interface: {device.get('interface', 'Unknown')}\n"
        f"RSSI: {device.get('rssi', 'N/A')}\n"
        f"Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )


def main():
    print()
    print("=" * 100)
    print("NetJoin - New Device Detector")
    print("=" * 100)

    known = load_state()
    print(f"[STATE] Known devices: {len(known)}")

    fd, cookie_file = tempfile.mkstemp(
        prefix="netjoin-", suffix=".cookies", dir="/run"
    )
    os.close(fd)
    os.chmod(cookie_file, 0o600)

    clients = {}

    try:
        router_login(cookie_file)
        clients = get_clients(cookie_file)
        print_client_list(clients)
    finally:
        router_logout(cookie_file)
        try:
            os.unlink(cookie_file)
        except FileNotFoundError:
            pass

    new_devices = [
        device for mac, device in clients.items()
        if mac not in known
    ]

    for device in new_devices:
        mac = device["mac"]
        print(f"[NEW] {device['ip']} {mac} {device['device_name']}")

        # Save before notification to prevent duplicate alerts
        # if OpenWA fails.
        known[mac] = device

        try:
            send_whatsapp(make_message(device))
            print(f"[WHATSAPP] Sent for {mac}")
        except Exception as error:
            print(f"[WHATSAPP ERROR] {error}")

    save_state(known)

    print()
    if new_devices:
        print(f"[RESULT] {len(new_devices)} new device(s) detected.")
    else:
        print("[RESULT] No new devices.")

    print(f"[STATE] Known devices: {len(known)}")
    print("[DONE]")


if __name__ == "__main__":
    main()
