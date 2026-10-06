"""Physical simulation: a moving target and a rate-limited two-axis mount.

Replace this module with real sensor/motor drivers and the rest of the
system keeps working unchanged.
"""

import math
import random
from dataclasses import dataclass


def wrap_180(deg: float) -> float:
    """Normalize an angle difference to (-180, 180]."""
    return (deg + 180.0) % 360.0 - 180.0


def angular_error(az1: float, el1: float, az2: float, el2: float) -> float:
    """Great-circle angle between two az/el directions, in degrees."""
    a1, e1, a2, e2 = map(math.radians, (az1, el1, az2, el2))
    cos_d = (math.sin(e1) * math.sin(e2)
             + math.cos(e1) * math.cos(e2) * math.cos(a1 - a2))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_d))))


@dataclass
class Target:
    """A target drifting slowly across the sky along a figure-eight path."""
    center_az: float = 205.0
    center_el: float = 38.0
    t: float = 0.0

    def step(self, dt: float) -> None:
        self.t += dt

    @property
    def az(self) -> float:
        return (self.center_az + 6.0 * math.sin(self.t / 40.0)) % 360.0

    @property
    def el(self) -> float:
        return self.center_el + 3.0 * math.sin(self.t / 20.0)


@dataclass
class Mount:
    """Two-axis mount that slews toward a commanded position at a max rate."""
    az: float = 0.0
    el: float = 10.0
    max_rate: float = 12.0  # deg/s

    def slew_toward(self, az: float, el: float, dt: float) -> None:
        step = self.max_rate * dt
        d_az = wrap_180(az - self.az)
        d_el = el - self.el
        self.az = (self.az + max(-step, min(step, d_az))) % 360.0
        self.el = self.el + max(-step, min(step, d_el))


@dataclass
class Environment:
    """Sensor readings that change on their own."""
    temperature: float = 24.0
    heading_noise: float = 0.15

    def step(self, dt: float, active: bool) -> None:
        # First-order approach to an equilibrium: motors warm the enclosure.
        equilibrium = 37.0 if active else 24.0
        self.temperature += (equilibrium - self.temperature) * dt / 90.0
        self.temperature += random.gauss(0, 0.02)


def signal_dbm(error_deg: float, beamwidth: float = 2.0) -> float:
    """Received level falls off with pointing error (Gaussian beam model)."""
    peak, floor = -42.0, -95.0
    gain = math.exp(-2.77 * (error_deg / beamwidth) ** 2)
    return floor + (peak - floor) * gain + random.gauss(0, 0.4)
