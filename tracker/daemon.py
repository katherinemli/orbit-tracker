"""Tracker daemon: the single authority over the mount.

Runs a fixed-rate control loop, feeds events into the state machine,
and publishes a snapshot to `state.json` for anyone who wants to read it.
Commands arrive as small JSON files dropped into the runtime directory, so
the API never touches the hardware directly.
"""

import argparse
import json
import os
import random
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from .simulation import Environment, Mount, Target, angular_error, signal_dbm
from .state_machine import Event, State, is_active, next_state

LOOP_HZ = 10
ACQUIRE_SECONDS = 3.0
LOCK_THRESHOLD = 0.4     # deg: enter TRACKING below this error
UNLOCK_THRESHOLD = 1.2   # deg: drop back to POINTING above this (hysteresis)
FAULT_TEMP = 50.0        # °C


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_atomic(path: Path, data: dict) -> None:
    """Write via temp file + rename so readers never see a half-written file."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


class Tracker:
    def __init__(self, runtime: Path):
        self.runtime = runtime
        self.state = State.IDLE
        self.target = Target()
        self.mount = Mount()
        self.env = Environment()
        self.time_in_state = 0.0
        self.events = deque(maxlen=50)
        self.log("Daemon started")

    # -- helpers ---------------------------------------------------------
    def log(self, message: str, level: str = "info") -> None:
        self.events.appendleft({"time": now_iso(), "level": level, "message": message})

    def fire(self, event: Event) -> None:
        new = next_state(self.state, event)
        if new != self.state:
            self.log(f"{self.state.value} → {new.value} ({event.value})",
                     "warn" if new == State.FAULT else "info")
            self.state = new
            self.time_in_state = 0.0

    def read_command(self) -> None:
        cmd_file = self.runtime / "command.json"
        if not cmd_file.exists():
            return
        try:
            action = json.loads(cmd_file.read_text()).get("action")
        except (json.JSONDecodeError, OSError):
            action = None
        cmd_file.unlink(missing_ok=True)
        mapping = {"start": Event.START, "stop": Event.STOP, "reset": Event.RESET}
        if action in mapping:
            self.log(f"Command received: {action}")
            self.fire(mapping[action])

    # -- control loop ----------------------------------------------------
    def step(self, dt: float) -> None:
        self.read_command()
        self.target.step(dt)
        self.env.step(dt, is_active(self.state))
        self.time_in_state += dt

        if self.state == State.ACQUIRING and self.time_in_state >= ACQUIRE_SECONDS:
            self.fire(Event.FIX_ACQUIRED)

        if self.state in (State.POINTING, State.TRACKING):
            self.mount.slew_toward(self.target.az, self.target.el, dt)
            # Servo jitter: a real mount never sits exactly on target.
            self.mount.az += random.gauss(0, 0.04)
            self.mount.el += random.gauss(0, 0.04)
            # Occasional disturbance (wind gust) to show re-acquisition.
            if self.state == State.TRACKING and random.random() < 0.002:
                self.mount.az += random.choice([-1, 1]) * random.uniform(2, 4)
                self.log("Disturbance detected", "warn")

        error = angular_error(self.mount.az, self.mount.el,
                              self.target.az, self.target.el)
        if self.state == State.POINTING and error < LOCK_THRESHOLD:
            self.fire(Event.ON_TARGET)
        elif self.state == State.TRACKING and error > UNLOCK_THRESHOLD:
            self.fire(Event.OFF_TARGET)

        if is_active(self.state) and self.env.temperature > FAULT_TEMP:
            self.fire(Event.FAULT)

        self.publish(error)

    def publish(self, error: float) -> None:
        tracking = self.state == State.TRACKING
        write_atomic(self.runtime / "state.json", {
            "timestamp": now_iso(),
            "state": self.state.value,
            "mount": {"az": round(self.mount.az, 2), "el": round(self.mount.el, 2)},
            "target": {"az": round(self.target.az, 2), "el": round(self.target.el, 2)},
            "error_deg": round(error, 3),
            "signal_dbm": round(signal_dbm(error), 1) if is_active(self.state) else None,
            "locked": tracking,
            "temperature_c": round(self.env.temperature, 1),
            "events": list(self.events)[:20],
        })

    def run(self) -> None:
        period = 1.0 / LOOP_HZ
        last = time.monotonic()
        while True:
            now = time.monotonic()
            self.step(now - last)
            last = now
            time.sleep(max(0.0, period - (time.monotonic() - now)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Orbit Tracker daemon")
    parser.add_argument("--runtime", default="runtime", help="state/command directory")
    parser.add_argument("--autostart", action="store_true", help="start tracking on boot")
    args = parser.parse_args()

    runtime = Path(args.runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    tracker = Tracker(runtime)
    if args.autostart:
        tracker.fire(Event.START)
    try:
        tracker.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
