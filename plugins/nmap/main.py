#!/usr/bin/env python3
"""
FlipCTL nmap plugin.
Reads inputs from stdin as JSON, writes result to stdout as JSON.
Uses XML output for reliable parsing.
"""
import ipaddress
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


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


def parse_xml_output(xml_output: str) -> list[dict]:
    """Parse nmap XML output to extract open ports."""
    ports = []
    try:
        root = ET.fromstring(xml_output)
        for host in root.findall('host'):
            for port in host.findall('ports/port'):
                state = port.find('state')
                if state is not None and state.get('state') == 'open':
                    portid = port.get('portid')
                    protocol = port.get('protocol')
                    service_elem = port.find('service')
                    service = service_elem.get('name') if service_elem is not None else 'unknown'

                    ports.append({
                        "port": int(portid),
                        "protocol": protocol,
                        "service": service
                    })
    except ET.ParseError:
        # If XML parsing fails, fall back to empty list
        pass
    return ports


def run(target: str, flags: str = "-F") -> dict:
    # Validate target input to prevent command injection
    if not is_valid_target(target):
        return {
            "success": False,
            "target": target,
            "error": "invalid target format",
            "open_ports": [],
            "raw_output": ""
        }

    if not shutil.which("nmap"):
        return {
            "success": False,
            "target": target,
            "error": "nmap not installed",
            "open_ports": [],
            "raw_output": ""
        }

    # Use XML output for reliable parsing
    cmd = ["nmap"] + flags.split() + ["-oX", "-", target]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        xml_output = result.stdout
        stderr_output = result.stderr

        return {
            "success": result.returncode == 0,
            "target": target,
            "stubbed": False,
            "open_ports": parse_xml_output(xml_output),
            "raw_output": (xml_output + stderr_output).strip(),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "target": target, "error": "timeout", "open_ports": [], "raw_output": ""}


if __name__ == "__main__":
    inputs = json.loads(sys.stdin.read())
    output = run(
        target=inputs["target"],
        flags=inputs.get("flags", "-F"),
    )
    print(json.dumps(output))
