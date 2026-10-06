# Orbit Tracker 🛰️

A small control system for a two-axis tracking mount: a **supervisor daemon** that owns the hardware, a **REST API** that never touches it directly, and a **live dashboard** for the operator. The mount and sensors are simulated, so the whole thing runs on a laptop with one command.

![Dashboard](docs/dashboard.png)

## Run it

```bash
python3 run.py
```

Open http://localhost:8000. The mount acquires a fix, slews to the target and locks on. Python 3.10+, no dependencies to install.

Run the tests with `python3 -m unittest`.

## Architecture

```
┌──────────────┐  state.json (atomic write, 10 Hz)  ┌─────────────┐  JSON over HTTP  ┌───────────┐
│    Daemon    │ ─────────────────────────────────▶ │     API     │ ───────────────▶ │ Dashboard │
│ control loop │ ◀───────────────────────────────── │  + history  │ ◀─────────────── │  (Vue 3)  │
└──────────────┘        command.json (drop-in)      └─────────────┘   POST command   └───────────┘
```

- **One authority.** Only the daemon moves the mount. The API publishes what the daemon reports and forwards operator commands as files; if the API crashes, tracking continues.
- **Atomic hand-off.** Snapshots and commands are written to a temp file and renamed, so a reader never sees half a file.
- **Testable core.** The state machine is a pure transition table with no I/O.

### State machine

```
IDLE ──start──▶ ACQUIRING ──fix──▶ POINTING ──on target──▶ TRACKING
  ▲                                    ▲                       │
  └────────────── stop ────────────────┴───── off target ──────┘
                 any active state ──fault──▶ FAULT ──reset──▶ IDLE
```

Lock uses hysteresis (enter below 0.4°, drop above 1.2°) so the state doesn't flicker at the edge. A random disturbance now and then knocks the mount off target to show re-acquisition.

### Simulation

- Target drifts along a slow figure-eight
- Mount slews at a capped rate, always the short way around in azimuth, with a bit of servo jitter
- Signal follows a Gaussian beam model: strong when on target, falling off with pointing error
- Enclosure temperature settles toward an equilibrium that depends on whether the motors are running

Swap `tracker/simulation.py` for real drivers and nothing else needs to change.

## Layout

```
tracker/   daemon, state machine, simulation
api/       HTTP server (stdlib): /api/status, /api/history, /api/command
web/       dashboard: sky view, telemetry, charts, event log
tests/     state machine and geometry tests
```

## API

| Method | Path | |
|---|---|---|
| GET | `/api/status` | Latest snapshot from the daemon |
| GET | `/api/history` | Last 5 minutes of signal, error and temperature |
| POST | `/api/command` | `{"action": "start" \| "stop" \| "reset"}` |

---
Katherine Liberona Irarrázabal · [github.com/katherinemli](https://github.com/katherinemli)
