#!/usr/bin/env python3
"""Headless display implementation for local smoke tests."""


class Display:
    def __init__(self, dev_pins=None):
        self.dev_pins = dev_pins or {}
        self.last_status = None
        self.test_frames = 0

    def display_status(self, current):
        self.last_status = current

    def display_splash(self):
        pass

    def clear_display(self):
        pass

    def display_text(self, text):
        self.last_status = {"text": text}

    def display_network(self):
        pass

    def display_test(self):
        self.test_frames += 1

