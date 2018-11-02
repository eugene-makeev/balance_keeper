from multiprocessing import Event


class ShutdownNotification(Exception):
    pass


def check_event(evt):
    if evt.is_set():
        # do stuff
        # prepare to die
        evt.clear()
        raise ShutdownNotification


def main_logic(event):
    while True:
        x = 1
        check_event(event)
        y = 2
        check_event(event)


def start_parallel_service(event: Event):
    while True:
        try:
            main_logic(event)
        except ShutdownNotification:
            raise SystemExit(42)
