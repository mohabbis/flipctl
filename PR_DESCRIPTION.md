# PR: prototype: minimal FlipCTL architecture with Web UI + TUI + plugin system

**Suggested PR title:** `prototype: minimal FlipCTL architecture — Web UI + TUI + language-agnostic plugin system`

**Suggested labels:** `architecture-proposal`, `prototype`, `needs-review`

**Target:** `flipperdevices/flipctl` → `main`

---

## Architecture description

FlipCTL's core challenge is serving multiple, radically different frontends (headless WebKit on DRM, SSH TUI, desktop browser, future hardware panel) from a single, stable backend — without coupling any UI concern to the core logic.

This proposal organises FlipCTL into four independent layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Control Interfaces                        │
│   ┌──────────────────┐          ┌──────────────────────────┐   │
│   │    Web Browser   │          │    Terminal / SSH         │   │
│   │   (index.html)   │          │    (tui/app.py)           │   │
│   └────────┬─────────┘          └──────────────┬────────────┘   │
│            │  HTTP fetch()                      │  httpx async   │
└────────────┼───────────────────────────────────┼───────────────┘
             ▼                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (server.py)                   │
│   GET  /api/plugins   →  list plugins + input schemas           │
│   POST /api/execute   →  run plugin, return JSON result         │
│   GET  /              →  serve web/index.html                   │
└───────────────────────────────┬─────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│               Plugin Manager (core/plugin_manager.py)           │
│   • Discovers plugins/ on startup via plugin.yaml               │
│   • Validates input schemas                                     │
│   • Executes plugin process: stdin=JSON → stdout=JSON           │
└──────────────┬──────────────────────────────────┬──────────────┘
               ▼                                  ▼
     plugins/ping/                      plugins/nmap/
     ├── plugin.yaml                    ├── plugin.yaml
     └── main.py                        └── main.py
```

**Key design decisions:**

- **Single API surface:** both the Web UI and the TUI call identical endpoints. A third frontend (native app, hardware panel, FlipCTL Control Panel) requires zero backend changes.
- **Subprocess isolation:** each plugin runs as a child process. A crashing plugin cannot take down the server, and resource limits (ulimit, cgroups) can be applied per-process.
- **No framework lock-in:** the Web UI is a zero-dependency single HTML file, making it suitable for headless WebKit rendering on DRM without a build step.

---

## Plugin system & wrappers vision

### `plugin.yaml` schema

```yaml
name: ping
description: "Send ICMP echo requests and report reachability."
version: "1.0"
inputs:
  - name: target
    type: string       # string | integer | boolean
    required: true
    description: IP address or hostname
  - name: count
    type: integer
    required: false
    default: 4
command: python main.py   # entry-point, relative to plugin dir
timeout: 30               # seconds before SIGKILL
```

### Execution contract

| Concern | Contract |
|---------|----------|
| Inputs | JSON object on **stdin** |
| Output | JSON object on **stdout** |
| Errors | non-zero exit OR empty stdout treated as plugin error |
| Language | any — `python main.py`, `bash main.sh`, `./scanner` (Go/Rust binary), `node main.js` |

### `ping` wrapper example

Wraps `ping -c <count> <target>` (cross-platform: `-n` on Windows). Returns:
```json
{ "success": true, "target": "1.1.1.1", "packets_sent": 4, "packets_received": 4, "avg_ms": 12.3, "raw_output": "..." }
```

### `nmap` wrapper example

Wraps `nmap -F <target>`. Gracefully stubs if nmap is not installed (safe for CI/review). Returns:
```json
{ "success": true, "target": "192.168.1.1", "open_ports": [{"port": 22, "protocol": "tcp", "service": "ssh"}], "raw_output": "..." }
```

### Extensibility path

Adding a new plugin is four steps:
1. `mkdir plugins/<name>`
2. Write `plugin.yaml` following the schema
3. Write the entry-point script (any language)
4. Restart the server — the plugin manager rescans on startup

Future plugins envisioned: `traceroute`, `nmcli` (NetworkManager), `systemctl status`, `iwlist scan`, `tcpdump` (streaming via WebSocket).

---

## Minimal working prototype

Both frontends are implemented and functional. No hardware required.

### Run instructions

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) install nmap for real port scans
#    macOS:  brew install nmap
#    Linux:  sudo apt install nmap

# 3. Start the backend
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# 4. Open the Web UI
open http://localhost:8000        # or navigate in any browser

# 5. Run the TUI (separate terminal, server must be running)
python tui/app.py
```

### What reviewers should see

- Web UI loads at `http://localhost:8000` with a plugin dropdown pre-populated from the API.
- Selecting `ping`, entering a target (e.g. `1.1.1.1`), clicking Run returns structured JSON output.
- Selecting `nmap` works the same; returns stub data if nmap not installed.
- TUI shows the same plugins and same output from the same API endpoints.
- Both UIs update independently — they share no state except the backend API.

> **Screenshots:** attach two screenshots to this PR — one of the Web UI and one of the TUI running `ping 1.1.1.1`. The TUI screenshot can be taken with `textual run --screenshot tui/app.py` or a standard terminal capture.

---

## Reviewer checklist

- [ ] `uvicorn server:app --reload` starts without errors
- [ ] `GET /api/plugins` returns both `ping` and `nmap` with correct input schemas
- [ ] `POST /api/execute` with `{"plugin":"ping","inputs":{"target":"1.1.1.1"}}` returns a JSON result
- [ ] Web UI at `http://localhost:8000` loads, plugin selector works, Run button calls the API and displays output
- [ ] TUI (`python tui/app.py`) connects to the server, lists plugins, executes and displays results
- [ ] nmap plugin returns stub data when nmap is not installed (no crash)
- [ ] Adding a new `plugin.yaml` + `main.py` and restarting the server makes the new plugin appear in both UIs
- [ ] `DESIGN.md` covers architecture diagram, plugin schema, run instructions, and future-proofing notes
