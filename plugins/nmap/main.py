#!/usr/bin/env python3
"""
FlipCTL nmap plugin.
Reads inputs from stdin as JSON, writes result to stdout as JSON.
Gracefully stubs if nmap is not installed.
"""
import json
import re
import shutil
import subprocess
import sys


def parse_ports(raw: str) -> list[dict]:
    ports = []
    for line in raw.splitlines():
        m = re.match(r"(\d+)/(tcp|udp)\s+open\s+(\S+)", line.strip())
        if m:
            ports.append({"port": int(m.group(1)), "protocol": m.group(2), "service": m.group(3)})
    return ports


def run(target: str, flags: str = "-F") -> dict:
    if not shutil.which("nmap"):
        return {
            "success": True,
            "target": target,
            "stubbed": True,
            "open_ports": [
                {"port": 22, "protocol": "tcp", "service": "ssh"},
                {"port": 80, "protocol": "tcp", "service": "http"},
            ],
            "raw_output": "[nmap not installed — returning stub data]",
        }

    cmd = ["nmap"] + flags.split() + [target]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        raw = result.stdout + result.stderr
        return {
            "success": result.returncode == 0,
            "target": target,
            "stubbed": False,
            "open_ports": parse_ports(raw),
            "raw_output": raw.strip(),
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
