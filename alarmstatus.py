from enum import Enum

class AlarmStatus(Enum):
    WAITING, PLAYING, STOPPED = range(3)