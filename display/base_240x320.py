#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: 
   This is a base class for displays using 
 a 240Hx320W resolution.  Other display 
 libraries will inherit this base class 
 and add device specific features.

*****************************************
'''

'''
 Imported Libraries
'''
import os
import time
import socket
import qrcode
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from common import read_control, write_control
from picycle_appliance import PiCycleAppliance, format_duration, format_mmss
import storage

'''
Display base class definition
'''


class DisplayBase:

    def __init__(self, dev_pins):

        # Init Global Variables and Constants
        self.dev_pins = dev_pins
        #self.buttonslevel = config['buttonslevel']
        self.rotation = 2
        self.display_active = False
        self.in_data = None
        self.status_data = None
        self.display_timeout = None
        self.display_command = 'splash'
        self.input_counter = 0
        self.input_enabled = False
        self.primary_font = 'trebuc.ttf'
        #self.primary_font = 'DejaVuSans.ttf'  # May need to switch to a default font in Raspberry Pi OS Lite due to MSTCorefonts Package Deprecation
        # Attempt to set the log level of PIL so that it does not pollute the logs
        logging.getLogger('PIL').setLevel(logging.CRITICAL + 1)
        # Init Display Device, Input Device, Assets
        self._init_globals()
        self._init_assets()
        self._init_input()
        self._init_display_device()

    def _init_globals(self):
        # Init constants and variables
        '''
        0 = Zero Degrees Rotation
        90, 1 = 90 Degrees Rotation (Pimoroni Libraries, Luma.LCD Libraries)
        180, 2 = 180 Degrees Rotation (Pimoroni Libraries, Luma.LCD Libraries)
        270, 3 = 270 Degrees Rotation (Pimoroni Libraries, Luma.LCD Libraries)
        '''
        if self.rotation in [90, 270, 1, 3]:
            self.WIDTH = 240
            self.HEIGHT = 320
        else:
            self.WIDTH = 320
            self.HEIGHT = 240

        self.inc_pulse_color = True
        self.icon_color = 100
        self.appliance = PiCycleAppliance(rides=self._load_ride_history())

    def _init_display_device(self):
        '''
        Inheriting classes will override this function to init the display device and start the display thread.
        '''
        pass

    def _init_input(self):
        '''
        Inheriting classes will override this function to setup the inputs.
        '''
        self.input_enabled = False  # If the inheriting class does not implement input, then clear this flag
        self.input_counter = 0

    def _init_menu(self):
        self.menu_active = False
        self.menu_time = 0
        self.menu_item = ''

        self.menu = {}

        self.menu['inactive'] = {
            # List of options for the 'inactive' menu.  This is the initial menu when smoker is not running.
            'Start': {
                'displaytext': 'Start',
                'icon': '\uf04b',  # FontAwesome Play Icon
                'iconcolor': (120, 169, 235)
            },
            'Network': {
                'displaytext': 'IP QR Code',
                'icon': '\uf1eb',  # FontAwesome Wifi Icon
                'iconcolor': (120, 169, 235)
            },
            'Power': {
                'displaytext': 'Power Menu',
                'icon': '\uf0e7',  #FontAwesome Power Icon
                'iconcolor': (120, 169, 235)
            }
        }

        self.menu['active'] = {
            # List of options for the 'active' menu.  This is the second level menu of options while running.
            'Stop': {
                'displaytext': 'Stop',
                'icon': '\uf04d',  # FontAwesome Stop Icon
                'iconcolor': (120, 169, 235)
            },
            'Network': {
                'displaytext': 'IP QR Code',
                'icon': '\uf1eb',  # FontAwesome Wifi Icon
                'iconcolor': (120, 169, 235)
            },
        }

        self.menu['power_menu'] = {
            'Power_Off': {
                'displaytext': 'Shutdown',
                'icon': '\uf011',  # FontAwesome Power Button
                'iconcolor': (120, 169, 235)
            },
            'Power_Restart': {
                'displaytext': 'Restart',
                'icon': '\uf2f9',  # FontAwesome Circle Arrow
                'iconcolor': (120, 169, 235)
            },
            'Menu_Back': {
                'displaytext': 'Back',
                'icon': '\uf060',  # FontAwesome Back Arrow
                'iconcolor': (120, 169, 235)
            }
        }

        self.menu['current'] = {}
        self.menu['current']['mode'] = 'none'  # Current Menu Mode (inactive, active)
        self.menu['current']['option'] = 0  # Current option in current mode

    def _display_loop(self):
        """
        Main display loop
        """
        while True:
            if self.input_enabled:
                self._event_detect()

            if self.display_command == 'clear':
                self.display_active = True
                self.display_timeout = None
                self.display_command = None
                self._display_clear()

            if self.display_command == 'splash':
                self._display_splash()
                self.display_timeout = time.time() + 2
                self.display_command = 'clear'
                time.sleep(1)  # Hold splash screen for 1 seconds

            if self.display_command == 'text':
                self._display_text()
                self.display_command = None
                self.display_timeout = time.time() + 15

            if self.display_command == 'network':
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                network_ip = s.getsockname()[0]
                if network_ip != '':
                    self._display_network(network_ip)
                    self.display_timeout = time.time() + 30
                    self.display_command = None
                else:
                    self.display_text("No IP Found")

            if not self.display_timeout:
                self._display_current(self.in_data or {})
            time.sleep(0.1)

    '''
    ============== Input Callbacks ============= 
    
    Inheriting classes will override these functions for all inputs.
    '''

    def _enter_callback(self):
        '''
        Inheriting classes will override this function.
        '''
        pass

    def _up_callback(self, held=False):
        '''
        Inheriting classes will override this function to clear the display device.
        '''
        pass

    def _down_callback(self, held=False):
        '''
        Inheriting classes will override this function to clear the display device.
        '''
        pass

    def _encoder_callback(self):
        '''
        Inheriting classes will override this function to read a rotary encoder.
        '''
        pass

    '''
    ============== Graphics / Display / Draw Methods ============= 
    '''

    def _init_assets(self):
        self._init_background()
        self._init_splash()

    def _init_background(self):
        self.background = Image.open('static/img/display/background.png')
        self.background = self.background.resize((self.WIDTH, self.HEIGHT))

    def _init_splash(self):
        self.splash = Image.open('static/img/display/background.png')
        # (self.splash_width, self.splash_height) = self.splash.size
        # self.splash_width *= 2
        # self.splash_height *= 2
        # self.splash = self.splash.resize((self.splash_width, self.splash_height))
        self.splash = self.splash.resize((self.WIDTH, self.HEIGHT))

    def _rounded_rectangle(self, draw, xy, rad, fill=None):
        x0, y0, x1, y1 = xy
        draw.rectangle([(x0, y0 + rad), (x1, y1 - rad)], fill=fill)
        draw.rectangle([(x0 + rad, y0), (x1 - rad, y1)], fill=fill)
        draw.pieslice([(x0, y0), (x0 + rad * 2, y0 + rad * 2)], 180, 270, fill=fill)
        draw.pieslice([(x1 - rad * 2, y1 - rad * 2), (x1, y1)], 0, 90, fill=fill)
        draw.pieslice([(x0, y1 - rad * 2), (x0 + rad * 2, y1)], 90, 180, fill=fill)
        draw.pieslice([(x1 - rad * 2, y0), (x1, y0 + rad * 2)], 270, 360, fill=fill)

    def _font(self, font_point_size, font_name=None):
        font_name = font_name or self.primary_font
        for candidate in (font_name, 'DejaVuSans.ttf'):
            try:
                return ImageFont.truetype(candidate, font_point_size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _draw_text(self, text, font_name, font_point_size, text_color, rect=False, fill_color=None, outline_color=None):
        font = self._font(font_point_size, font_name)
        font_bbox = font.getbbox(str(text))  # Grab the width of the text
        font_canvas_size = (font_bbox[2], font_bbox[3])
        font_canvas = Image.new('RGBA', font_canvas_size)
        font_draw = ImageDraw.Draw(font_canvas)
        font_draw.text((0, 0), str(text), font=font, fill=text_color)
        if rect:
            font_canvas = font_canvas.crop(font_canvas.getbbox())
            font_canvas_size = font_canvas.size
            rect_canvas_size = (font_canvas_size[0] + 16, font_canvas_size[1] + 16)
            rect_canvas = Image.new('RGBA', rect_canvas_size)
            rect_draw = ImageDraw.Draw(rect_canvas)
            rect_draw.rounded_rectangle((0, 0, rect_canvas_size[0], rect_canvas_size[1]), radius=8, fill=fill_color,
                                        outline=outline_color, width=3)
            rect_canvas.paste(font_canvas, (8, 8), font_canvas)
            return rect_canvas
        return font_canvas.crop(font_canvas.getbbox())

    def _text_circle(self, draw, position, size, text, fg_color=(255, 255, 255), bg_color=(0, 0, 0)):
        # Draw outline with fg_color
        coords = (position[0], position[1], position[0] + size[0], position[1] + size[1])
        draw.ellipse(coords, fill=fg_color)
        # Fill circle with Center with bg_color
        fill_coords = (coords[0] + 2, coords[1] + 2, coords[2] - 2, coords[3] - 2)
        draw.ellipse(fill_coords, fill=bg_color)
        # Place Text
        font_point_size = round(size[1] * 0.6)  # Convert size to height of circle * font point ratio 0.6
        font = ImageFont.truetype(self.primary_font, font_point_size)
        font_bbox = font.getbbox(str(text))  # Grab the bounding box of the text
        font_width = font_bbox[2]
        label_x = position[0] + (size[0] // 2) - (font_width // 2)
        label_y = position[1] + round((size[1] // 2) - (font_point_size // 2))
        label_origin = (label_x, label_y)
        draw.text(label_origin, text, font=font, fill=fg_color)

    def _create_icon(self, charid, size, color):
        icon_canvas = self._draw_text(charid, 'static/font/FA-Free-Solid.otf', size, color)
        return (icon_canvas)

    def _paste_icon(self, icon, canvas, position, rotation):
        # Rotate the icon
        icon = icon.rotate(rotation)
        # Set the position & paste the icon onto the canvas
        canvas.paste(icon, position, icon)
        return (canvas)

    def _draw_pause_icon(self, canvas, position):
        # Create a drawing object
        draw = ImageDraw.Draw(canvas)

        # Recipe Pause Icon
        icon_char = '\uf04c'
        icon_color = (255, self.icon_color, 0)

        # Draw Rounded Rectangle Border
        self._rounded_rectangle(draw,
                                (position[0], position[1],
                                 position[0] + 42, position[1] + 42),
                                5, icon_color)

        # Fill Rectangle with Black
        self._rounded_rectangle(draw,
                                (position[0] + 2, position[1] + 2,
                                 position[0] + 40, position[1] + 40),
                                5, (0, 0, 0))

        # Create Icon Image
        icon = self._create_icon(icon_char, 28, icon_color)
        icon_position = (position[0] + 9, position[1] + 9)
        canvas = self._paste_icon(icon, canvas, icon_position, 0)

        return canvas

    def _draw_gauge(self, canvas, position, size, fg_color, bg_color, percents, temps, label, sp1_color=(0, 200, 255),
                    sp2_color=(255, 255, 0)):
        # Create drawing object
        draw = ImageDraw.Draw(canvas)
        # bgcolor = (50, 50, 50)  # Grey
        # fgcolor = (200, 0, 0)  # Red
        # percents = [temperature, setpoint1, setpoint2]
        # temps = [current, setpoint1, setpoint2]
        # sp1_color = (0, 200, 255)  # Cyan
        # sp2_color = (255, 255, 0)  # Yellow
        fill_color = (0, 0, 0)  # Black

        # Draw Background Line
        coords = (position[0], position[1], position[0] + size[0], position[1] + size[1])
        draw.ellipse(coords, fill=bg_color)

        # Draw Arc for Temperature (Percent)
        if (percents[0] > 0) and (percents[0] < 100):
            endpoint = (360 * (percents[0] / 100)) + 90
        elif percents[0] > 100:
            endpoint = 360 + 90
        else:
            endpoint = 90
        draw.pieslice(coords, start=90, end=endpoint, fill=fg_color)

        # Draw Tic for Setpoint[1]
        if percents[1] > 0:
            if percents[1] < 100:
                setpoint = (360 * (percents[1] / 100)) + 90
            else:
                setpoint = 360 + 90
            draw.pieslice(coords, start=setpoint - 2, end=setpoint + 2, fill=sp1_color)

        # Draw Tic for Setpoint[2]
        if percents[2] > 0:
            if percents[2] < 100:
                setpoint = (360 * (percents[2] / 100)) + 90
            else:
                setpoint = 360 + 90
            draw.pieslice(coords, start=setpoint - 2, end=setpoint + 2, fill=sp2_color)

        # Fill Circle with Center with black
        fill_coords = (coords[0] + 10, coords[1] + 10, coords[2] - 10, coords[3] - 10)
        draw.ellipse(fill_coords, fill=fill_color)

        # Gauge Label
        if len(label) <= 5:
            font_point_size = round((size[1] * 0.75) / 4) + 1  # Convert size to height of circle * font point ratio / 8
        elif len(label) <= 6:
            font_point_size = round((size[1] * 0.60) / 4) + 1  # Convert size to height of circle * font point ratio / 8
        else:
            font_point_size = round((size[1] * 0.40) / 4) + 1  # Convert size to height of circle * font point ratio / 8
        label_canvas = self._draw_text(label, self.primary_font, font_point_size, (255, 255, 255))
        label_x = int(position[0] + (size[0] // 2) - (label_canvas.width // 2))
        label_y = int(position[1] + (round(((size[1] * 0.75) / 8) * 6.6)))
        label_origin = (label_x, label_y)
        canvas.paste(label_canvas, label_origin, label_canvas)

        # SetPoint1 Label
        if percents[1] > 0:
            sp1_label = f'>{temps[1]}<'
            font_point_size = round((size[1] * 0.6) / 4)  # Convert size to height of circle * font point ratio
            label_canvas = self._draw_text(sp1_label, self.primary_font, font_point_size, sp1_color)
            label_x = int(position[0] + (size[0] // 2) - (label_canvas.width // 2))
            label_y = int(position[1] + round(size[1] / 8))
            label_origin = (label_x, label_y)
            canvas.paste(label_canvas, label_origin, label_canvas)

        # Current Temperature (Large Centered)
        cur_temp = str(temps[0])[:5]
        if self.units == 'F':
            font_point_size = round(size[1] * 0.4)  # Convert size to height of circle * font point ratio / 8
        else:
            font_point_size = round(size[1] * 0.3)  # Convert size to height of circle * font point ratio / 8
        label_canvas = self._draw_text(cur_temp, self.primary_font, font_point_size, (255, 255, 255))
        label_x = int(position[0] + (size[0] // 2) - (label_canvas.width // 2))
        label_y = int(position[1] + ((size[1] // 1.8) - (font_point_size // 1.5)))
        label_origin = (label_x, label_y)
        canvas.paste(label_canvas, label_origin, label_canvas)

        return (canvas)

    def _display_clear(self):
        '''
        Inheriting classes will override this function to clear the display device.
        '''
        pass

    def _display_canvas(self, canvas):
        '''
        Inheriting classes will override this function to show the canvas on the display device.
        '''
        pass

    def _display_splash(self):
        # Create canvas
        img = Image.new('RGBA', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

        # Set the position & paste the splash image onto the canvas
        #position = ((self.WIDTH - self.splash_width) // 2, (self.HEIGHT - self.splash_height) // 2)
        position = (0, 0)
        img.paste(self.splash, position, self.splash)

        self._display_canvas(img)

    def _display_text(self):
        # Create canvas
        img = Image.new('RGBA', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

        label_canvas = self._draw_text(self.display_data, self.primary_font, 42, (255, 255, 0))
        label_x = (self.WIDTH // 2 - label_canvas.width // 2)
        label_y = self.HEIGHT // 2 - label_canvas.height // 2
        label_origin = (label_x, label_y)
        img.paste(label_canvas, label_origin, label_canvas)

        self._display_canvas(img)

    def _display_network(self, network_ip):
        # Create canvas
        img = Image.new('RGBA', (self.WIDTH, self.HEIGHT), color=(255, 255, 255))
        img_qr = qrcode.make('http://' + network_ip)
        img_qr_width, img_qr_height = img_qr.size
        img_qr_width *= 2
        img_qr_height *= 2
        w = min(self.WIDTH, self.HEIGHT)
        new_image = img_qr.resize((w, w))
        position = (int((self.WIDTH / 2) - (w / 2)), 0)
        img.paste(new_image, position)

        self._display_canvas(img)

    def _display_current(self, in_data):
        self.appliance.update_metrics(in_data or {})
        self._persist_saved_ride()
        self._persist_deleted_ride()
        img = Image.new('RGBA', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        snap = self.appliance.snapshot()
        view = snap['view']
        if view == 'menu':
            self._draw_menu(draw, 'PiCycle', snap['items'], snap['selected'], show_footer=False)
        elif view == 'programs':
            self._draw_menu(draw, 'Programs', snap['items'], snap['selected'])
        elif view == 'tabata_setup':
            self._draw_setup(draw, 'Tabata', [
                ('Warmup', format_duration(snap['tabata_config']['warmupSec'])),
                ('All Out', format_duration(snap['tabata_config']['hotSec'])),
                ('Recover', format_duration(snap['tabata_config']['recoverSec'])),
                ('Rounds', str(snap['tabata_config']['rounds'])),
                ('Start', ''),
            ], snap['selected'])
        elif view == 'swedish_setup':
            self._draw_setup(draw, 'Swedish 4x4', [
                ('Warmup', format_duration(snap['swedish_config']['warmupSec'])),
                ('Start', ''),
            ], snap['selected'])
        elif view == 'history':
            self._draw_history(draw, snap)
        elif view == 'review':
            self._draw_review(draw, snap)
        elif view == 'delete_confirm':
            self._draw_delete_confirm(draw, snap)
        elif view == 'pause':
            self._draw_menu(draw, 'Paused', snap['items'], snap['selected'])
        elif view in ['ride', 'tabata_ride', 'swedish_ride']:
            self._draw_ride(draw, snap)
        else:
            self._draw_top_bar(draw, 'Settings', '')
            self._draw_centered_text(draw, 'Wheel, display, and device settings.', 118, 18, (170, 170, 170))
            self._draw_footer(draw, 'Double-click for back')
        self._display_canvas(img)

    def _load_ride_history(self):
        try:
            with storage.open_database() as connection:
                return storage.list_completed_ride_summaries(connection, limit=20)
        except Exception:
            return []

    def _persist_saved_ride(self):
        ride = self.appliance.pop_saved_ride()
        if not ride:
            return
        try:
            with storage.open_database() as connection:
                storage.save_completed_ride_summary(connection, ride)
        except Exception:
            pass

    def _persist_deleted_ride(self):
        ride_id = self.appliance.pop_deleted_ride_id()
        if not ride_id:
            return
        try:
            with storage.open_database() as connection:
                storage.delete_completed_ride_summary(connection, ride_id)
        except Exception:
            pass

    def appliance_snapshot(self):
        return self.appliance.snapshot()

    def _handle_input_command(self, command):
        if command not in ['UP', 'DOWN', 'ENTER']:
            return
        self.display_active = True
        self.display_command = None
        self.display_data = None
        self.display_timeout = None
        self.appliance.handle_input(command)
        self._persist_saved_ride()
        self._persist_deleted_ride()

    def _text_size(self, draw, text, font):
        bbox = draw.textbbox((0, 0), str(text), font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def _draw_label(self, draw, text, xy, size, fill=(255, 255, 255), font_name=None):
        draw.text(xy, str(text), font=self._font(size, font_name), fill=fill)

    def _draw_right_label(self, draw, text, x, y, size, fill=(255, 255, 255)):
        font = self._font(size)
        width, _ = self._text_size(draw, text, font)
        draw.text((x - width, y), str(text), font=font, fill=fill)

    def _draw_centered_text(self, draw, text, center_y, size, fill=(255, 255, 255)):
        font = self._font(size)
        width, height = self._text_size(draw, text, font)
        draw.text(((self.WIDTH - width) // 2, int(center_y - height / 2)), str(text), font=font, fill=fill)

    def _draw_top_bar(self, draw, title, clock_text='', title_size=16, clock_size=16, bar_height=25):
        draw.line((0, bar_height, self.WIDTH, bar_height), fill=(45, 45, 45), width=1)
        self._draw_label(draw, title, (8, 4), title_size, (235, 235, 235))
        if clock_text:
            self._draw_right_label(draw, clock_text, self.WIDTH - 8, 4, clock_size, (235, 235, 235))

    def _draw_top_actions(self, draw, items, selected):
        x = self.WIDTH - 8
        for index in range(len(items) - 1, -1, -1):
            item = items[index]
            fill = (255, 255, 255) if index == selected else (150, 150, 150)
            font = self._font(12)
            width, _ = self._text_size(draw, item, font)
            draw.text((x - width, 7), item, font=font, fill=fill)
            if index == selected:
                draw.line((x - width, 22, x, 22), fill=fill, width=1)
            x -= width + 12

    def _draw_footer(self, draw, text):
        draw.line((0, self.HEIGHT - 24, self.WIDTH, self.HEIGHT - 24), fill=(45, 45, 45), width=1)
        self._draw_label(draw, text, (8, self.HEIGHT - 18), 12, (170, 170, 170))

    def _draw_menu(self, draw, title, items, selected, show_footer=True):
        self._draw_top_bar(draw, title, '')
        y = 39
        for index, item in enumerate(items):
            fill = (255, 255, 255) if index == selected else (190, 190, 190)
            self._draw_label(draw, item, (18, y), 24, fill)
            if index == selected:
                font = self._font(24)
                width, _ = self._text_size(draw, item, font)
                draw.line((18, y + 28, 18 + width, y + 28), fill=(255, 255, 255), width=2)
            y += 42
        if show_footer:
            self._draw_footer(draw, 'Double-click for back')

    def _draw_setup(self, draw, title, rows, selected):
        self._draw_top_bar(draw, title, '')
        y = 38
        for index, (label, value) in enumerate(rows):
            fill = (255, 255, 255) if index == selected else (190, 190, 190)
            self._draw_label(draw, label, (14, y), 21, fill)
            if value:
                self._draw_right_label(draw, value, self.WIDTH - 14, y, 21, fill)
            if index == selected:
                draw.line((14, y + 25, self.WIDTH - 14, y + 25), fill=(255, 255, 255), width=2)
            y += 35
        self._draw_footer(draw, 'Double-click for back')

    def _draw_ride(self, draw, snap):
        title = snap['active_label']
        self._draw_top_bar(draw, title, snap['elapsed_text'], title_size=22, clock_size=22, bar_height=34)
        y = 44
        if snap['phase']:
            phase = snap['phase']
            self._draw_centered_text(draw, phase['name'], 55, 24)
            self._draw_centered_text(draw, format_duration(phase['remaining']), 80, 28)
            self._draw_centered_text(draw, f"Round {phase['round']} of {phase['rounds']}", 106, 13, (170, 170, 170))
            if snap['feedback']:
                feedback = snap['feedback']
                self._draw_centered_text(draw, f"{feedback['status']} - {feedback['detail']}", 123, 12, (170, 170, 170))
                y = 132
            else:
                y = 119
        labels = [('mph', snap['speed']), ('Cal', snap['calories']), ('avg mph', snap['avg_speed'])]
        column_width = self.WIDTH // 3
        for index, (label, value) in enumerate(labels):
            cx = index * column_width + column_width // 2
            value_text = f"{value:.1f}"
            font = self._font(34)
            width, _ = self._text_size(draw, value_text, font)
            draw.text((cx - width // 2, y), value_text, font=font, fill=(255, 255, 255))
            label_font = self._font(13)
            label_width, _ = self._text_size(draw, label, label_font)
            draw.text((cx - label_width // 2, y + 38), label, font=label_font, fill=(170, 170, 170))
        self._draw_chart(draw, snap['pace_history'], (8, self.HEIGHT - 64, self.WIDTH - 8, self.HEIGHT - 30))
        self._draw_footer(draw, 'Press to pause')

    def _draw_history(self, draw, snap):
        self._draw_top_bar(draw, 'History', '')
        rides = snap['rides']
        selected = min(snap['selected'], max(0, len(rides) - 1))
        start = max(0, min(selected - 2, max(0, len(rides) - 5)))
        y = 34
        for offset, ride in enumerate(rides[start:start + 5]):
            index = start + offset
            fill = (255, 255, 255) if index == selected else (190, 190, 190)
            self._draw_label(draw, self._format_date(ride.get('ended_at')), (14, y), 18, fill)
            self._draw_label(draw, ride.get('type') or ride.get('label', 'Ride'), (14, y + 18), 12, (170, 170, 170))
            if index == selected:
                draw.line((14, y + 35, self.WIDTH - 14, y + 35), fill=(255, 255, 255), width=2)
            y += 36
        if not rides:
            self._draw_centered_text(draw, 'No saved rides yet.', 112, 18, (170, 170, 170))
        self._draw_footer(draw, 'Double-click for back')

    def _draw_review(self, draw, snap):
        ride = snap['review']
        self._draw_top_bar(draw, 'Review', '')
        self._draw_top_actions(draw, snap['items'], snap['selected'])
        if not ride:
            self._draw_centered_text(draw, 'No ride selected.', 112, 18, (170, 170, 170))
            self._draw_footer(draw, 'Press for back')
            return
        self._draw_label(draw, self._format_date(ride.get('ended_at')), (10, 31), 17)
        self._draw_label(draw, ride.get('type') or ride.get('label', 'Ride'), (10, 51), 12, (170, 170, 170))
        structure = ride.get('structure')
        program = ride.get('program')
        if structure and program == 'tabata':
            text = f"{structure['rounds']} x {structure['hotSec']}s all out / {structure['recoverSec']}s recover"
            self._draw_label(draw, text, (10, 68), 12, (190, 190, 190))
        elif structure and program == 'swedish':
            text = f"{structure['rounds']} x {format_duration(structure['hardSec'])} hard / {format_duration(structure['recoverSec'])} recover"
            self._draw_label(draw, text, (10, 68), 12, (190, 190, 190))
        metrics = [
            (format_mmss(ride.get('durationSec', 0)), 'time'),
            (f"{ride.get('calories', 0):.1f}", 'Cal'),
            (f"{ride.get('avgSpeed', 0):.1f}", 'avg mph'),
        ]
        for index, (value, label) in enumerate(metrics):
            x = 12 + index * 104
            self._draw_label(draw, value, (x, 91), 23)
            self._draw_label(draw, label, (x, 119), 11, (170, 170, 170))
        self._draw_chart(draw, ride.get('samples') or [0], (8, 146, self.WIDTH - 8, 202))
        self._draw_footer(draw, 'Turn to choose action, press to select')

    def _draw_delete_confirm(self, draw, snap):
        ride = snap['review']
        self._draw_top_bar(draw, 'Delete ride', '')
        if ride:
            self._draw_label(draw, self._format_date(ride.get('ended_at')), (12, 39), 16)
            self._draw_label(draw, ride.get('type') or ride.get('label', 'Ride'), (12, 58), 12, (170, 170, 170))
        self._draw_centered_text(draw, 'This will delete', 92, 22)
        self._draw_centered_text(draw, 'this ride.', 118, 22)
        self._draw_centered_text(draw, 'Are you sure?', 148, 17, (190, 190, 190))
        y = 177
        for index, item in enumerate(snap['items']):
            x = 83 + index * 93
            fill = (255, 255, 255) if index == snap['selected'] else (150, 150, 150)
            self._draw_label(draw, item, (x, y), 22, fill)
            if index == snap['selected']:
                font = self._font(22)
                width, _ = self._text_size(draw, item, font)
                draw.line((x, y + 27, x + width, y + 27), fill=fill, width=2)
        self._draw_footer(draw, 'No keeps ride, Yes deletes')

    def _draw_chart(self, draw, values, box):
        x0, y0, x1, y1 = box
        values = values or [0]
        max_value = max(1.0, max(values))
        points = []
        for index, value in enumerate(values):
            x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
            y = y1 - (float(value) / max_value) * (y1 - y0 - 4) - 2
            points.append((x, y))
        draw.line((x0, y1, x1, y1), fill=(65, 65, 65), width=1)
        if len(points) > 1:
            draw.line(points, fill=(120, 190, 235), width=2)

    def _format_date(self, timestamp):
        if not timestamp:
            return ''
        date = datetime.fromtimestamp(float(timestamp))
        return f"{date.strftime('%b')} {date.day} {date.strftime('%I:%M %p').lstrip('0')}"

    '''
     ====================== Input & Menu Code ========================
    '''

    def _event_detect(self):
        """
        Called to detect input events from buttons, encoder, touch, etc.
        This function should be overriden by the inheriting class.
        """
        pass

    def _menu_display(self, action):
        ''' Process user input from th display
            action: Will be UP, DOWN, or ENTER '''

        # If menu is not currently being displayed, check mode and draw menu
        print('action=', action)
        print("  menu=", self.menu['current'])

        # When the display has timed out it will be set to 'none'.  Wake it up based
        # not the current operating mode
        # Note the menu has the following modes: none, inactive, and active
        if self.menu['current']['mode'] == 'none':
            control = read_control()
            # If in an inactive mode
            if control['mode'] in ['Stop', 'Error']:
                self.menu['current']['mode'] = 'inactive'
            else:
                self.menu['current']['mode'] = 'active'

            self.menu['current']['option'] = 0  # Set the menu option to the very first item in the list

        # If selecting either active menu items or inactive menu items, take action based on what the button press was
        else:
            if action == 'DOWN':
                self.display_active = True
                self.menu_active = True
                self.menu['current']['option'] -= 1
                if self.menu['current']['option'] < 0:  # Check to make sure we haven't gone past 0
                    self.menu['current']['option'] = len(self.menu[self.menu['current']['mode']]) - 1
                temp_value = self.menu['current']['option']
                temp_mode = self.menu['current']['mode']
                index = 0
                selected = 'undefined'
                for item in self.menu[temp_mode]:
                    if index == temp_value:
                        selected = item
                        break
                    index += 1
            elif action == 'UP':
                self.display_active = True
                self.menu_active = True
                self.menu['current']['option'] += 1
                # Check to make sure we haven't gone past the end of the menu
                if self.menu['current']['option'] == len(self.menu[self.menu['current']['mode']]):
                    self.menu['current']['option'] = 0
                temp_value = self.menu['current']['option']
                temp_mode = self.menu['current']['mode']
                index = 0
                selected = 'undefined'
                for item in self.menu[temp_mode]:
                    if index == temp_value:
                        selected = item
                        break
                    index += 1
            elif action == 'ENTER':
                index = 0
                selected = 'undefined'
                for item in self.menu[self.menu['current']['mode']]:
                    if (index == self.menu['current']['option']):
                        selected = item
                        break
                    index += 1
                # Inactive Mode Items
                if selected == 'Start':
                    self.display_active = True
                    self.menu['current']['mode'] = 'none'
                    #self.menu['current']['mode'] = 'riding'
                    self.menu['current']['option'] = 0
                    self.menu_active = False
                    self.menu_time = 0
                    control = read_control()
                    control['updated'] = True
                    control['mode'] = 'Riding'
                    write_control(control, origin='display')
                    control = read_control()

                elif selected == 'Stop':
                    self.menu['current']['mode'] = 'none'
                    self.menu['current']['option'] = 0
                    self.menu_active = False
                    self.menu_time = 0
                    self.clear_display()
                    control = read_control()
                    control['updated'] = True
                    control['mode'] = 'Stop'
                    write_control(control, origin='display')
                elif selected == 'Power':
                    self.menu['current']['mode'] = 'power_menu'
                    self.menu['current']['option'] = 0
                elif 'Power_' in selected:
                    control = read_control()
                    if 'Off' in selected:
                        #TODO - splash a shutdown screen!

                        os.system('sudo shutdown -h now &')
                    elif 'Restart' in selected:
                        os.system('sudo reboot &')

                # Master Menu Back Function
                elif 'Menu_Back' in selected:
                    self.menu['current']['mode'] = 'inactive'
                    self.menu['current']['option'] = 0

                # Active Mode
                elif selected == 'Shutdown':
                    self.display_active = True
                    self.menu['current']['mode'] = 'none'
                    self.menu['current']['option'] = 0
                    self.menu_active = False
                    self.menu_time = 0
                    control = read_control()
                    control['updated'] = True
                    control['mode'] = 'Shutdown'
                    write_control(control, origin='display')
                elif selected == 'Network':
                    self.display_network()
                else:
                    print(f'menu selection {selected} is not supported!')
                #TODO log this instead

        # Create canvas
        img = Image.new('RGBA', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))
        # Set the position & paste background image onto canvas
        position = (0, 0)
        img.paste(self.background, position)
        # Create drawing object
        draw = ImageDraw.Draw(img)

        if self.menu['current']['mode'] == 'riding':

            # ...
            font_point_size = 80 if self.WIDTH == 240 else 120
            label_canvas = self._draw_text(str(self.menu['current']['option']), self.primary_font, font_point_size,
                                           (255, 255, 255))
            label_origin = (int(self.WIDTH // 2 - label_canvas.width // 2),
                            int(self.HEIGHT // 3 - label_canvas.height // 2)) if self.WIDTH == 240 else (
            int(self.WIDTH // 2 - label_canvas.width // 2 - 20), int(self.HEIGHT // 2.5 - label_canvas.height // 2))
            img.paste(label_canvas, label_origin, label_canvas)

            # Current Mode (Bottom Center)
            font_point_size = 40
            text = "Riding"
            label_canvas = self._draw_text(text, self.primary_font, font_point_size, (0, 0, 0))

            # Draw White Rectangle
            draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, self.HEIGHT)], fill=(255, 255, 255))
            # Draw White Line/Rectangle
            draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, ((self.HEIGHT // 8) * 6) + 2)],
                           fill=(130, 130, 130))
            # Draw Text
            label_origin = (int(self.WIDTH // 2 - label_canvas.width // 2), int((self.HEIGHT // 8) * 6.35))
            img.paste(label_canvas, label_origin, label_canvas)

        elif self.menu['current']['mode'] != 'none':
            # Menu Option (Large Top Center)
            index = 0
            selected = 'undefined'
            for item in self.menu[self.menu['current']['mode']]:
                if index == self.menu['current']['option']:
                    selected = item
                    break
                index += 1
            font_point_size = 80 if self.WIDTH == 240 else 120
            icon_color = self.menu[self.menu['current']['mode']][selected].get('iconcolor', (
            255, 255, 255))  # Get color from menu item, default to white if not defined
            text = self.menu[self.menu['current']['mode']][selected]['icon']
            label_canvas = self._draw_text(text, 'static/font/FA-Free-Solid.otf', font_point_size, icon_color)
            label_origin = (
            int(self.WIDTH // 2 - label_canvas.width // 2), int(self.HEIGHT // 2.5 - label_canvas.height // 2))
            img.paste(label_canvas, label_origin, label_canvas)

            # Current Mode (Bottom Center)
            # Draw White Rectangle
            draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, self.HEIGHT)], fill=(255, 255, 255))
            # Draw Gray Line/Rectangle
            draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, ((self.HEIGHT // 8) * 6) + 2)],
                           fill=(130, 130, 130))
            # Draw Text
            font_point_size = 40
            text = self.menu[self.menu['current']['mode']][selected]['displaytext']
            label_canvas = self._draw_text(text, self.primary_font, font_point_size, (0, 0, 0))
            label_origin = (int(self.WIDTH // 2 - label_canvas.width // 2), int((self.HEIGHT // 8) * 6.35))
            img.paste(label_canvas, label_origin, label_canvas)

        self._display_canvas(img)

    '''
    ================ Externally Available Methods ================
    '''

    def display_status(self, current):
        """
        - Updates the current data for the display loop, if in a work mode
        """
        self.display_active = True
        self.in_data = current

    def display_splash(self):
        """
        - Calls Splash Screen
        """
        self.display_command = 'splash'

    def clear_display(self):
        """
        - Clear display and turn off backlight
        """
        self.display_command = 'clear'

    def display_text(self, text):
        """
        - Display some text
        """
        self.display_command = 'text'
        self.display_data = text

    def display_network(self):
        """
        - Display Network IP QR Code
        """
        self.display_command = 'network'

    def display_test(self):
        # Create canvas
        img = Image.new('RGBA', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))
        # Set the position & paste background image onto canvas
        position = (0, 0)
        img.paste(self.background, position)
        # Create drawing object
        draw = ImageDraw.Draw(img)
        font_point_size = 80 if self.WIDTH == 240 else 120
        label_canvas = self._draw_text(str(self.menu['current']['option']), self.primary_font, font_point_size,
                                       (255, 255, 255))
        label_origin = (int(self.WIDTH // 2 - label_canvas.width // 2),
                        int(self.HEIGHT // 3 - label_canvas.height // 2)) if self.WIDTH == 240 else (
            int(self.WIDTH // 2 - label_canvas.width // 2 - 20), int(self.HEIGHT // 2.5 - label_canvas.height // 2))
        img.paste(label_canvas, label_origin, label_canvas)

        # Current Mode (Bottom Center)
        font_point_size = 40
        text = "Riding"
        label_canvas = self._draw_text(text, self.primary_font, font_point_size, (0, 0, 0))

        # Draw White Rectangle
        draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, self.HEIGHT)], fill=(255, 255, 255))
        # Draw White Line/Rectangle
        draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, ((self.HEIGHT // 8) * 6) + 2)],
                       fill=(130, 130, 130))
        # Draw Text
        label_origin = (int(self.WIDTH // 2 - label_canvas.width // 2), int((self.HEIGHT // 8) * 6.35))
        img.paste(label_canvas, label_origin, label_canvas)
