"""
FlipCTL Plugin Manager.

Discovers plugins by scanning the plugins/ directory for subdirectories
containing a plugin.yaml descriptor. Executes plugins by spawning their
entry-point process, passing inputs as JSON via stdin, and reading JSON
output from stdout.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"


class PluginError(Exception):
    pass


class PluginManager:
    def __init__(self, plugins_dir: Path = PLUGINS_DIR):
        self.plugins_dir = plugins_dir
        self._plugins: dict[str, dict] = {}
        self._load_all()

    def _load_all(self) -> None:
        for entry in sorted(self.plugins_dir.iterdir()):
            spec_path = entry / "plugin.yaml"
            if entry.is_dir() and spec_path.exists():
                try:
                    self._plugins[entry.name] = self._load_spec(entry, spec_path)
                except Exception as exc:
                    print(f"[plugin_manager] skipping {entry.name}: {exc}", file=sys.stderr)

    def _load_spec(self, plugin_dir: Path, spec_path: Path) -> dict:
        with open(spec_path) as f:
            spec = yaml.safe_load(f)
        required_keys = {"name", "description", "version", "inputs", "command", "timeout"}
        missing = required_keys - spec.keys()
        if missing:
            raise ValueError(f"plugin.yaml missing keys: {missing}")
        spec["_dir"] = plugin_dir
        return spec

    def list_plugins(self) -> list[dict]:
        return [
            {
                "name": spec["name"],
                "description": spec["description"],
                "version": spec["version"],
                "inputs": spec["inputs"],
            }
            for spec in self._plugins.values()
        ]

    def execute(self, plugin_name: str, inputs: dict[str, Any]) -> dict:
        spec = self._plugins.get(plugin_name)
        if spec is None:
            raise PluginError(f"Unknown plugin: {plugin_name!r}")

        self._validate_inputs(spec, inputs)

        plugin_dir: Path = spec["_dir"]
        command: str = spec["command"]
        timeout: int = spec.get("timeout", 30)

        # Resolve the command relative to the plugin directory.
        # If the command starts with "python", use the current interpreter.
        parts = command.split()
        if parts[0] in ("python", "python3"):
            parts[0] = sys.executable

        try:
            result = subprocess.run(
                parts,
                input=json.dumps(inputs),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=plugin_dir,
            )
        except subprocess.TimeoutExpired:
            raise PluginError(f"Plugin {plugin_name!r} timed out after {timeout}s")
        except FileNotFoundError as exc:
            raise PluginError(f"Plugin command not found: {exc}")

        if result.returncode != 0 and not result.stdout.strip():
            raise PluginError(
                f"Plugin {plugin_name!r} exited {result.returncode}: {result.stderr.strip()}"
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise PluginError(f"Plugin {plugin_name!r} returned invalid JSON: {exc}")

    def _validate_inputs(self, spec: dict, inputs: dict) -> None:
        for field in spec.get("inputs", []):
            if field.get("required") and field["name"] not in inputs:
                raise PluginError(f"Missing required input: {field['name']!r}")
