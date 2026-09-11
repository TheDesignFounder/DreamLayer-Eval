"""
scheduler.py - Helper functions for value scheduling and interpolation.
"""

from math import cos, pi
from typing import List


def linear_schedule(start: float, end: float, steps: int) -> List[float]:
    """
    Generate a linear schedule from start to end over a number of steps.

    >>> linear_schedule(0, 1, 5)
    [0.0, 0.25, 0.5, 0.75, 1.0]
    >>> linear_schedule(5, 5, 3)
    [5.0, 5.0, 5.0]
    >>> linear_schedule(2, 4, 1)
    [4]
    >>> linear_schedule(0, 1, 0)
    Traceback (most recent call last):
    ...
    ValueError: steps must be a positive integer
    """
    if steps <= 0:
        raise ValueError("steps must be a positive integer")
    if steps == 1:
        return [end]
    delta = (end - start) / (steps - 1)
    return [round(start + i * delta, 6) for i in range(steps)]


def cosine_schedule(start: float, end: float, steps: int) -> List[float]:
    """
    Generate a cosine-eased schedule from start to end over steps.

    >>> cosine_schedule(0, 1, 3)
    [0.0, 0.5, 1.0]
    >>> cosine_schedule(2, 4, 2)
    [2.0, 4.0]
    >>> cosine_schedule(3, 3, 1)
    [3]
    >>> cosine_schedule(1, 2, 0)
    Traceback (most recent call last):
    ...
    ValueError: steps must be a positive integer
    """
    if steps <= 0:
        raise ValueError("steps must be a positive integer")
    if steps == 1:
        return [end]
    return [
        round(start + (1 - cos(pi * i / (steps - 1))) / 2 * (end - start), 6)
        for i in range(steps)
    ]


def constant_schedule(value: float, steps: int) -> List[float]:
    """
    Generate a constant schedule of fixed value.

    >>> constant_schedule(0.7, 4)
    [0.7, 0.7, 0.7, 0.7]
    >>> constant_schedule(1.5, 1)
    [1.5]
    >>> constant_schedule(2.0, 0)
    []
    >>> constant_schedule(2.0, -3)
    []
    """
    if steps <= 0:
        return []
    return [value] * steps


def interpolate(schedule: List[float], step: int) -> float:
    """
    Interpolate a value from the schedule at the given step index.
    Returns the last value if step exceeds the schedule.

    >>> interpolate([0.0, 0.5, 1.0], 1)
    0.5
    >>> interpolate([0.0, 0.5, 1.0], 5)
    1.0
    >>> interpolate([], 0)
    Traceback (most recent call last):
    ...
    ValueError: schedule cannot be empty
    >>> interpolate([0.0, 0.5, 1.0], -1)
    Traceback (most recent call last):
    ...
    ValueError: step cannot be negative
    """
    if not schedule:
        raise ValueError("schedule cannot be empty")
    if step < 0:
        raise ValueError("step cannot be negative")
    return schedule[min(step, len(schedule) - 1)]
