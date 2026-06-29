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

from .sandbox import sandboxed


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
        missing = required_keys - set(spec.keys())
        if missing:
            raise ValueError(f"plugin.yaml missing keys: {missing}")
        # Add sandbox capability flag
        spec["_sandbox_capable"] = False  # Plugins opt-in to sandboxing
        spec["_dir"] = plugin_dir
        return spec

    def list_plugins(self) -> list[dict]:
        return [
            {
                "name": spec["name"],
                "description": spec["description"],
                "version": spec["version"],
                "inputs": spec["inputs"],
                "sandbox_capable": spec.get("_sandbox_capable", False)
            }
            for spec in self._plugins.values()
        ]

    @sandboxed
    def _execute_in_sandbox(self, plugin_name: str, inputs: dict[str, Any]) -> dict:
        """
        Execute a plugin within the sandbox context.
        This method is decorated with @sandboxed to run in a sandbox.
        """
        return self._execute_plugin_direct(plugin_name, inputs)

    def _execute_plugin_direct(self, plugin_name: str, inputs: dict[str, Any]) -> dict:
        """
        Execute a plugin directly (the actual implementation).
        This is called from within the sandboxed context.
        """
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
                shell=False,  # Explicitly set shell=False for security
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

    def execute(self, plugin_name: str, inputs: dict[str, Any]) -> dict:
        """
        Execute a plugin with given inputs.

        Args:
            plugin_name: Name of the plugin to execute
            inputs: Dictionary of input parameters

        Returns:
            Dictionary containing plugin output

        Raises:
            PluginError: If plugin execution fails
        """
        # Check if plugin is sandbox capable, otherwise use direct execution
        spec = self._plugins.get(plugin_name)
        if spec and spec.get("_sandbox_capable", False):
            return self._execute_in_sandbox(plugin_name, inputs)
        else:
            # For non-sandbox-capable plugins, execute directly but still with shell=False
            return self._execute_plugin_direct(plugin_name, inputs)

    def _validate_inputs(self, spec: dict, inputs: dict) -> None:
        for field in spec.get("inputs", []):
            if field.get("required") and field["name"] not in inputs:
                raise PluginError(f"Missing required input: {field['name']!r}")