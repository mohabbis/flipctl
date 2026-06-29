#!/usr/bin/env python3
"""
FlipCTL ping plugin.
Reads inputs from stdin as JSON, writes result to stdout as JSON.
"""
import ipaddress
import json
import platform
import re
import subprocess
import sys


def is_valid_target(target: str) -> bool:
    """Validate that target is a valid IP address or hostname."""
    # Check if it's a valid IP address (IPv4 or IPv6)
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        pass

    # Check if it's a valid hostname
    # Hostname rules: labels separated by dots, each label 1-63 chars,
    # containing only alphanumeric and hyphen, not starting/ending with hyphen
    if len(target) > 253:
        return False

    # Remove trailing dot if present (absolute hostname)
    if target.endswith('.'):
        target = target[:-1]

    labels = target.split('.')
    if len(labels) < 1:
        return False

    for label in labels:
        if not label or len(label) > 63:
            return False
        if label.startswith('-') or label.endswith('-'):
            return False
        if not all(c.isalnum() or c == '-' for c in label):
            return False

    return True


def parse_ping_output(output: str) -> tuple[bool, int, int, float | None]:
    """
    Parse ping output to extract statistics.
    Returns: (success, packets_sent, packets_received, avg_ms)
    """
    # Initialize defaults
    packets_sent = 0
    packets_received = 0
    avg_ms = None
    success = False

    # Common patterns for packets transmitted/received
    # Format varies by OS: Linux, macOS, BSD, Windows, etc.
    patterns_packets = [
        # Linux: "X packets transmitted, Y received"
        r"(\d+)\s+packets?\s+transmitted.*,\s*(\d+)\s+(?:packets?\s+)?received",
        # Alternative: "X packets transmitted, Y received, Z% packet loss"
        r"(\d+)\s+packets?\s+transmitted.*,\s*(\d+)\s+received",
        # Windows: "Sent = X, Received = Y, Lost = Z"
        r"Sent\s*=\s*(\d+),\s*Received\s*=\s*(\d+)",
        # macOS/BSD: "X packets transmitted, Y packets received"
        r"(\d+)\s+packets?\s+transmitted.*,\s*(\d+)\s+packets?\s+received",
        # Simple fallback: look for received count
        r"(\d+)\s+(?:packets?\s+)?received",
    ]

    # Try to extract packets sent and received
    for pattern in patterns_packets:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            if len(match.groups()) >= 2:
                # Two groups: sent and received
                packets_sent = int(match.group(1))
                packets_received = int(match.group(2))
                break
            elif len(match.groups()) == 1:
                # One group: received only, assume sent equals count parameter
                packets_received = int(match.group(1))
                # We'll set packets_sent later from the count parameter
                break

    # If we didn't get sent count from regex, we'll set it from count parameter later

    # Common patterns for average round trip time
    patterns_avg = [
        # Linux: rtt min/avg/max/mdev = 5.123/6.456/7.789/0.123 ms
        r"rtt\s+min\/avg\/max\/mdev\s*=\s*[\d.]+\/([\d.]+)\/",
        # Alternative format: round-trip min/avg/max/stddev = 5.123/6.456/7.789/0.123 ms
        r"round-trip\s+min\/avg\/max\/stddev\s*=\s*[\d.]+\/([\d.]+)\/",
        # Windows: Minimum = 5ms, Maximum = 6ms, Average = 7ms
        r"Average\s*=\s*([\d.]+)ms",
        # macOS: round-trip min/avg/max/stddev = 5.123/6.456/7.789/0.123 ms
        r"round-trip\s+\(ms\)\s+min\/avg\/max\/stddev\s*=\s*[\d.]+\/([\d.]+)\/",
        # Simple avg= pattern
        r"avg\s*=\s*([\d.]+)",
        # Average = Xms
        r"Average\s*=\s*([\d.]+)ms",
    ]

    # Try to extract average RTT
    for pattern in patterns_avg:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            try:
                avg_ms = float(match.group(1))
                break
            except (ValueError, IndexError):
                continue

    # Determine success: we got a response (typically means we got replies
    # More reliable: check if we received any packets
    success = packets_received > 0

    return success, packets_sent, packets_received, avg_ms


def run(target: str, count: int = 4) -> dict:
    # Validate target input to prevent command injection
    if not is_valid_target(target):
        return {
            "success": False,
            "target": target,
            "error": "invalid target format",
            "packets_sent": 0,
            "packets_received": 0,
            "avg_ms": None,
            "raw_output": ""
        }

    flag = "-n" if platform.system().lower() == "windows" else "-c"
    cmd = ["ping", flag, str(count), target]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        raw = result.stdout + result.stderr
        ping_success = result.returncode == 0

        packets_sent = count  # Default to what we requested
        packets_received = 0
        avg_ms = None

        # Parse the output for actual statistics
        parsed_success, parsed_sent, parsed_received, parsed_avg = parse_ping_output(raw)

        # Use parsed values if they make sense, otherwise fall back to defaults
        if parsed_sent > 0:
            packets_sent = parsed_sent
        if parsed_received >= 0:
            packets_received = parsed_received
        if parsed_avg is not None:
            avg_ms = parsed_avg

        # Override success based on whether we got replies
        # (some ping implementations return 0 even with partial success)
        final_success = parsed_success or (packet_received > 0 and ping_success)

        return {
            "success": final_success,
            "target": target,
            "packets_sent": packets_sent,
            "packets_received": packets_received,
            "avg_ms": avg_ms,
            "raw_output": raw.strip(),
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "target": target, "error": "timeout", "raw_output": ""}
    except FileNotFoundError:
        return {"success": False, "target": target, "error": "ping not found", "raw_output": ""}


if __name__ == "__main__":
    inputs = json.loads(sys.stdin.read())
    output = run(
        target=inputs["target"],
        count=int(inputs.get("count", 4)),
    )
    print(json.dumps(output))
