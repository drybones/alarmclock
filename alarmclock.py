#!/usr/bin/env python

from time import sleep
import datetime 
import argparse
import simpleaudio as sa
import scrollphathd
from scrollphathd.fonts import font3x5
import RPi.GPIO as GPIO
import sn3218
import os

from coalesce import coalesce
from alarmstatus import AlarmStatus

print("""
Sarah's alarm clock
Press Ctrl+C to exit!

""")

BRIGHTNESS = 0.1

DISPLAY_OFF_HOUR = 21
DISPLAY_ON_HOUR = 7

ALARM_HOUR = 7
ALARM_MIN = 15

BUTTON_DISPLAY_DURATION = 5.0

parser = argparse.ArgumentParser()
parser.add_argument("--hour", type=int,
                    help="hour override (for testing)")
parser.add_argument("--minute", type=int,
                    help="minute override (for testing)")
parser.add_argument("--second", type=int,
                    help="second override (for testing)")
args = parser.parse_args()

now = datetime.datetime.now()
offset_time = datetime.time(
    coalesce(args.hour, now.hour),
    coalesce(args.minute, now.minute),
    coalesce(args.second, now.second)
)
offset_delta = now - datetime.datetime.combine(now.date(), offset_time)

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
alarm_status = AlarmStatus.WAITING
alarm_sound = sa.WaveObject.from_wave_file(os.path.join(__location__, "alarm.wav"))

sn3218.disable()

def get_localtime():
    return datetime.datetime.now() - offset_delta

def button_callback(channel):
    global alarm_status
    global last_button_press

    last_button_press = get_localtime()
    print("Button pressed")

    if alarm_status==AlarmStatus.PLAYING:
        alarm_status = AlarmStatus.STOPPED
        print("Button press stopping alarm")

try:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(37, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(37, GPIO.RISING, callback=button_callback, bouncetime=300)

    last_button_press = get_localtime() # default to process start, so it displays on startup
    alarm_play_obj = None

    while True:
        scrollphathd.clear()

        current_time = get_localtime()

        if current_time.hour==ALARM_HOUR and current_time.minute==ALARM_MIN:
            if alarm_status==AlarmStatus.WAITING:
                alarm_status = AlarmStatus.PLAYING
                alarm_play_obj = alarm_sound.play()
        else:
            alarm_status = AlarmStatus.WAITING
            
        if alarm_status==AlarmStatus.PLAYING and current_time.second % 2 == 0:
            scrollphathd.fill(BRIGHTNESS, x=0, y=6, width=17, height=1)
            if not alarm_play_obj.is_playing():
                alarm_play_obj = alarm_sound.play()

        if (alarm_status==AlarmStatus.STOPPED or alarm_status==AlarmStatus.WAITING) and alarm_play_obj:
            alarm_play_obj.stop()
        
        if ((current_time.hour >= DISPLAY_ON_HOUR and current_time.hour < DISPLAY_OFF_HOUR) or
            alarm_status==AlarmStatus.PLAYING or
            (current_time-last_button_press).total_seconds() <= BUTTON_DISPLAY_DURATION):
            # Display the time
            display_hour = ((current_time.hour-1) % 12) + 1
            scrollphathd.write_string(
                "{:>2}:{:0>2}".format(display_hour, current_time.minute),
                x=0, y=0, font=font3x5, brightness=BRIGHTNESS
            )

        scrollphathd.show()
        sleep(0.1)

finally:
    GPIO.cleanup()
