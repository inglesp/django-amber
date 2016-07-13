from threading import Thread
from time import sleep
from socket import socket

import requests

from django.core.management import call_command
from django.core.management.commands.runserver import Command as RunserverCommand


default_port = RunserverCommand.default_port


def run_runserver_in_thread(port=default_port):
    Thread(
        target=call_command,
        args=('runserver', port),
        kwargs={'use_reloader': False},
        daemon=True,
    ).start()

    wait_for_server()


def wait_for_server(port=default_port):
    for i in range(5):
        try:
            rsp = requests.get('http://localhost:{}/'.format(port))
            return
        except requests.exceptions.ConnectionError:
            pass

        sleep(0.1 * 2 ** i)

    raise RuntimeError('Got no response from runserver')
