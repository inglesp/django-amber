from threading import Thread
from time import sleep

import requests

from django.core.management import call_command


def run_runserver_in_thread():
    Thread(
        target=call_command,
        args=('runserver',),
        kwargs={'use_reloader': False},
        daemon=True,
    ).start()

    for i in range(5):
        try:
            rsp = requests.get('http://localhost:8000/')
            return
        except requests.exceptions.ConnectionError:
            pass

        sleep(0.1 * 2 ** i)

    raise RuntimeError('Got no response from runserver')
