"""Air-bike effort and machine-calorie approximations."""

from __future__ import annotations


ECHO_WATT_SECONDS_PER_MACHINE_CALORIE = 1200.0
_LOW_CADENCE_FIT_FLOOR_RPM = 20.0


def _echo_watts_polynomial(rpm: float) -> float:
    """Approximate Echo Bike V2/V3 watts from crank cadence."""

    return (
        0.00001 * rpm**4
        - 0.0011 * rpm**3
        + 0.1455 * rpm**2
        - 3.3264 * rpm
        + 29.355
    )


def echo_watts_from_rpm(rpm: float) -> float:
    """Return an approximate mechanical power output for an Echo-style air bike.

    The public calibration curve is only useful at normal riding cadences. Below
    20 RPM, linearly blend the fitted 20 RPM value down to zero so a stopped bike
    never reports phantom power from the polynomial's non-zero intercept.
    """

    cadence = max(0.0, float(rpm))
    if cadence == 0.0:
        return 0.0
    if cadence < _LOW_CADENCE_FIT_FLOOR_RPM:
        floor_watts = max(0.0, _echo_watts_polynomial(_LOW_CADENCE_FIT_FLOOR_RPM))
        return floor_watts * cadence / _LOW_CADENCE_FIT_FLOOR_RPM
    return max(0.0, _echo_watts_polynomial(cadence))


def echo_machine_calories_per_minute(rpm: float) -> float:
    """Return Echo-style console calories per minute for a crank cadence."""

    watts = echo_watts_from_rpm(rpm)
    return watts * 60.0 / ECHO_WATT_SECONDS_PER_MACHINE_CALORIE
