#!/usr/bin/env python3

# *****************************************
# Base class object for recording speed and distance
# *****************************************
#
# Description: This is a base clase which should be inherited from
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import time
import math

class SpeedBase:

    def __init__(
        self,
        radius=1.0,
        pulses_per_rev=1.0,
        distance_multiplier=1.0,
        cadence_pulses_per_rev=1.0,
    ):
        
        """ Initialize a bike speed calculator

        Arguments:
        pulse_gpio: gpio pin to read from
        radius: radius of the wheel in inches

        """
        # Initialize class attributes, note that because they are attributes of "self" they are
        # available to all functions in this class

        self.total_rev_count = 0
        self.start_time = time.time()
        self.prev_time = self.start_time
        self.curr_time_delta_sec = 0.0

        self.pulses_per_rev = max(float(pulses_per_rev), 1.0)
        self.distance_multiplier = float(distance_multiplier)
        self.cadence_pulses_per_rev = max(float(cadence_pulses_per_rev), 1.0)

        # Factor for converting sensor pulses to miles.
        # One revolution travels the wheel circumference, not the wheel area.
        circ_inches = 2 * math.pi * radius
        circ_feet = circ_inches / 12.0
        self.dist_factor = (circ_feet / 5280.0) * self.distance_multiplier / self.pulses_per_rev

    def _calc_cadence_rpm(self, pulse_delta, time_delta):
        """Convert sensor pulses over time into estimated crank cadence."""

        if time_delta <= 0.0:
            return 0.0
        pulses_per_minute = float(pulse_delta) / float(time_delta) * 60.0
        return pulses_per_minute / self.cadence_pulses_per_rev

    def stop_riding(self):       
        pass

    def avg_speed(self):
        """ Return the average speed """
        pass

    def curr_speed(self):
        """ Return the current speed """
        pass

    def distance(self):
        """ Return the total distance traveled """
        pass

    def rpm(self):
        """ Return the current RPM"""
        pass
