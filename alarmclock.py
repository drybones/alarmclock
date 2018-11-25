#!/usr/bin/env python

from time import sleep
import datetime 
import argparse
import logging
import threading
import simpleaudio as sa
import scrollphathd
from scrollphathd.fonts import font3x5
import RPi.GPIO as GPIO
import sn3218
import os
import flask

from coalesce import coalesce
from alarmstatus import AlarmStatus

BRIGHTNESS = 0.2

DISPLAY_OFF_HOUR = 21
DISPLAY_ON_HOUR = 7

ALARM_HOUR = 7
ALARM_MIN = 15
ALARM_ENABLED = True

BUTTON_DISPLAY_DURATION = 5.0

logger = logging.getLogger("alarmclock")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.info("Starting alarm clock. Press ctrl-c to exit.")

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
    coalesce(args.second, now.second),
    now.microsecond
)
offset_delta = datetime.datetime.combine(now.date(), offset_time) - now
logger.debug("Offset time is " + str(offset_time))
logger.debug("Offset delta is " + str(offset_delta))

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
alarm_status = AlarmStatus.WAITING
alarm_sound = sa.WaveObject.from_wave_file(os.path.join(__location__, "alarm.wav"))

sn3218.disable()

app = flask.Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return app.send_static_file('index.html')

@app.route('/api/time', methods=['GET'])
def get_current_time():
    return get_localtime().strftime("%H:%M:%S")

@app.route('/api/alarm_time', methods=['GET'])
def get_alarm_time():
    return str(ALARM_HOUR) + ':' + str(ALARM_MIN)

@app.route('/api/alarm_enabled', methods=['GET'])
def get_alarm_enable():
    return 'ON' if ALARM_ENABLED else "OFF"

@app.route('/api/alarm_enabled', methods=['POST'])
def set_alarm_enable():
    global ALARM_ENABLED
    result = flask.request.form['alarm_onoff']
    logger.debug("Setting ALARM_ENABLED to " + str(result == "ON"))
    ALARM_ENABLED = (result == "ON")
    return ('', 200)

def web_worker():
    app.run(host="sarah.local", debug=False)

def get_localtime():
    return datetime.datetime.now() + offset_delta

def button_callback(channel):
    global alarm_status
    global last_button_press

    last_button_press = get_localtime()
    logger.debug("Button pressed")

    if alarm_status==AlarmStatus.PLAYING:
        alarm_status = AlarmStatus.STOPPED
        logger.debug("Button press stopping alarm")

def time_logging_worker():
    while True:
        now = get_localtime()
        if now.second % 10 == 0:
            logger.info("Clock time is " + now.isoformat(sep=" "))
        sleep(1)

try:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(37, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(37, GPIO.RISING, callback=button_callback, bouncetime=300)

    last_button_press = get_localtime() # default to process start, so it displays on startup
    alarm_play_obj = None

    logging_thread = threading.Thread(target=time_logging_worker, daemon=True)
    logging_thread.start()

    web_thread = threading.Thread(target=web_worker, daemon=True)
    web_thread.start()

    while True:
        scrollphathd.clear()

        current_time = get_localtime()
        
        if ALARM_ENABLED and current_time.hour==ALARM_HOUR and current_time.minute==ALARM_MIN:
            if alarm_status==AlarmStatus.WAITING:
                logger.debug('Begin alarm')
                alarm_status = AlarmStatus.PLAYING
                alarm_play_obj = alarm_sound.play()
        else:
            alarm_status = AlarmStatus.WAITING
 
        if alarm_status==AlarmStatus.PLAYING and not alarm_play_obj.is_playing():
            logger.debug('Playing sound file')
            alarm_play_obj = alarm_sound.play()
             
        if alarm_status==AlarmStatus.PLAYING and current_time.second % 2 == 0:
            scrollphathd.fill(BRIGHTNESS, x=0, y=6, width=17, height=1)

        if (alarm_status==AlarmStatus.STOPPED or alarm_status==AlarmStatus.WAITING) and alarm_play_obj and alarm_play_obj.is_playing():
            logger.debug("Stoppng sound file")
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
            # Show if the alarm is set
            if ALARM_ENABLED:
                scrollphathd.set_pixel(16, 6, BRIGHTNESS)

        scrollphathd.show()
        sleep(0.1)

finally:
    GPIO.cleanup()
