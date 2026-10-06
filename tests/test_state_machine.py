import unittest

from tracker.simulation import Mount, angular_error, wrap_180
from tracker.state_machine import Event, State, next_state


class StateMachineTest(unittest.TestCase):
    def test_happy_path(self):
        s = State.IDLE
        for event, expected in [
            (Event.START, State.ACQUIRING),
            (Event.FIX_ACQUIRED, State.POINTING),
            (Event.ON_TARGET, State.TRACKING),
            (Event.OFF_TARGET, State.POINTING),
            (Event.STOP, State.IDLE),
        ]:
            s = next_state(s, event)
            self.assertEqual(s, expected)

    def test_irrelevant_events_are_ignored(self):
        self.assertEqual(next_state(State.IDLE, Event.ON_TARGET), State.IDLE)
        self.assertEqual(next_state(State.TRACKING, Event.START), State.TRACKING)

    def test_fault_requires_reset(self):
        s = next_state(State.TRACKING, Event.FAULT)
        self.assertEqual(s, State.FAULT)
        self.assertEqual(next_state(s, Event.START), State.FAULT)
        self.assertEqual(next_state(s, Event.RESET), State.IDLE)


class SimulationTest(unittest.TestCase):
    def test_wrap(self):
        self.assertAlmostEqual(wrap_180(350), -10)
        self.assertAlmostEqual(wrap_180(-190), 170)

    def test_angular_error(self):
        self.assertAlmostEqual(angular_error(10, 30, 10, 30), 0, places=6)
        self.assertAlmostEqual(angular_error(0, 0, 90, 0), 90, places=6)

    def test_mount_takes_short_way_round(self):
        m = Mount(az=350, el=20, max_rate=10)
        m.slew_toward(10, 20, dt=1.0)
        self.assertAlmostEqual(m.az, 0)


if __name__ == "__main__":
    unittest.main()
