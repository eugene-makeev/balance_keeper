import multiprocessing
import time
import service
import importlib
import requests

event_code_updated = multiprocessing.Event()
event_do_shutdown = multiprocessing.Event()


def get_process_handler():
    importlib.reload(service)
    return multiprocessing.Process(target=service.start_parallel_service, args=(event_code_updated,))


def get_github_content():
    # do git pull
    return 0x1


def is_github_code_updated(old_hash):
    new_hash = get_github_content()
    return old_hash != new_hash


def main_loop():
    git_working_head = None

    get_process_handler().start()

    while True:
        if is_github_code_updated(git_working_head):
            git_working_head = get_github_content()

            event_code_updated.set()

            while event_code_updated.is_set():
                time.sleep(0.1)
            new_process = get_process_handler()
            new_process.start()
            continue


if __name__ == '__main__':
    main_loop()
