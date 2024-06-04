#!/usr/bin/env python3

# *****************************************
# PiCycle Hall Sensor Interface Library
# *****************************************
#
# Description: This library simulates a speed
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import time
from datetime import timedelta
from speed_input.speed_input_base import SpeedBase
import random

class BikeSpeed(SpeedBase):

    BASE_SPEED = 10.0
    RANDOM_RANGE = 2.0

    def __init__(self, pulse_gpio=0, radius=1.0 ):
        super().__init__(radius)
        
        self._speed = 0
        self._distance = 0
        self._avg_speed = 0
        self._rpm = 0
        self._elapsed_time = 0.0
        self._elapsed_time_formatted = 0.0
        self._last_time = self.start_time
        self._riding = True
        self._avg_rpm = 0
        self._prev_avg = 0

    def avg_speed(self):
        """ Return the average speed """

        return 10.0
    
    def curr_speed(self):
        """ Return the current speed """

        if self._riding:
            # Every time this is requested, calculate a semi-random speed by adding a random
            # change between -0.05 and +0.05 mph
            speed_delta = random.random() * 0.1 - 0.05
            self._speed += speed_delta

            # prevent numbers from going too crazy
            self._speed = max(self.BASE_SPEED - self.RANDOM_RANGE, self._speed )
            self._speed = min(self.BASE_SPEED + self.RANDOM_RANGE, self._speed )
        else:
            self._speed = 0

        # get current time in seconds
        current_time = time.time()

        # update out distance
        self._distance += self._speed * (current_time - self._last_time ) / 3600.0

        # update out timer
        self._elapsed_time += round((current_time - self._last_time), 0)
        print(f'Time in Seconds: {self._elapsed_time}')
        self._elapsed_time_formatted = timedelta(seconds=self._elapsed_time)
        print(f'formatted: {self._elapsed_time_formatted}')

        # update out rpm and average rpm over duration of ride
        # self._rpm = 60/(current_time - self._last_time)
        self._rpm = random.uniform(75, 90)
        print(self._rpm)
        self._avg_rpm = round((self._prev_avg * (self._elapsed_time - 1) + self._rpm) / self._elapsed_time, 1)
        print(f"Average RPM: {self._avg_rpm}")
        self._prev_avg = self._avg_rpm

        self._last_time = current_time
        return self._speed
    
    def distance(self):
        """ Return the total distance traveled """
        return self._distance

    def stop_riding(self):       
        self._riding = False

    def avg_speed(self):
        """ Return the average speed """
        time_delta_hrs = (time.time() - self.start_time) / 3600.0
        s = self._distance / time_delta_hrs
        return s

    def rpm(self):
        """
        Return the current Revolutions per Minute
        The RPMs are being calculated inside curr_speed()
        """
        return self._rpm
        # current_time = time.time()
        # time_delta = current_time - self._last_time
        # print(time_delta)
        # if time_delta == 0:
        #     return 0.0
        # else:
        #     self.rpm = 1/time_delta
        #     self._last_time = current_time
        #     return self._rpm

    def timer(self):
        """
        Return the elapsed time
        """
        return self._elapsed_time_formatted
    # I might need to pass the non-formatted value because of JSON serializing... look into that later

    def average_rpm(self):
        """
        Return the average rpm for the duration of the ride
        """
        return self._avg_rpm
