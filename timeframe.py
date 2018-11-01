import time
import numpy

def get_timeframe_seconds(timeframe, multiplier=1):
    timeframe_seconds = 60
    if timeframe == 'day':
        timeframe_seconds *= 24 * 60 * multiplier
    elif timeframe == 'hour':
        timeframe_seconds *= 60 * multiplier
    elif timeframe == 'thirtyMin':
        timeframe_seconds *= 30
    elif timeframe == 'fiveMin':
        timeframe_seconds *= 5

    return timeframe_seconds

def get_time_from_str(timestr):
    try:
        t = time.strptime(timestr, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        t = time.strptime(timestr, '%Y-%m-%dT%H:%M:%S')
    return int(time.mktime(t))

def get_timestamp(timestr):
    return int(get_time_from_str(timestr))

def get_current_timeframe(timeframe):
    seconds = get_timeframe_seconds(timeframe)
    return numpy.ceil(time.mktime(time.gmtime(time.time())) / seconds) * seconds

def get_timeframe_from_str(timestr, timeframe):
    seconds = get_timeframe_seconds(timeframe)
    return int(numpy.ceil(get_time_from_str(timestr) / seconds) * seconds)