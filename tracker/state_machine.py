"""Supervisor state machine for the tracker.

Pure logic, no I/O: given the current state and an event, return the next
state. Keeping it side-effect free makes every transition unit-testable.
"""

from enum import Enum


class State(str, Enum):
    IDLE = "IDLE"
    ACQUIRING = "ACQUIRING"   # waiting for position fix + heading
    POINTING = "POINTING"     # slewing toward the target
    TRACKING = "TRACKING"     # locked on, following the target
    FAULT = "FAULT"


class Event(str, Enum):
    START = "start"
    STOP = "stop"
    FIX_ACQUIRED = "fix_acquired"
    ON_TARGET = "on_target"
    OFF_TARGET = "off_target"
    FAULT = "fault"
    RESET = "reset"


# (current state, event) -> next state. Anything not listed is ignored.
TRANSITIONS = {
    (State.IDLE, Event.START): State.ACQUIRING,
    (State.ACQUIRING, Event.FIX_ACQUIRED): State.POINTING,
    (State.POINTING, Event.ON_TARGET): State.TRACKING,
    (State.TRACKING, Event.OFF_TARGET): State.POINTING,
    (State.FAULT, Event.RESET): State.IDLE,
}

# STOP and FAULT apply from any active state.
for _s in (State.ACQUIRING, State.POINTING, State.TRACKING):
    TRANSITIONS[(_s, Event.STOP)] = State.IDLE
    TRANSITIONS[(_s, Event.FAULT)] = State.FAULT


def next_state(state: State, event: Event) -> State:
    """Return the state after `event`, or the same state if it doesn't apply."""
    return TRANSITIONS.get((state, event), state)


def is_active(state: State) -> bool:
    return state in (State.ACQUIRING, State.POINTING, State.TRACKING)
