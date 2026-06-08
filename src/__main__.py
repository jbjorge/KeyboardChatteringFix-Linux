import argparse
import errno
import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Iterator

import libevdev

from src.filtering import filter_chattering
from src.keyboard_retrieval import retrieve_keyboard_path, resolve_keyboard_path

_RECONNECT_ERRORS = frozenset({errno.ENOENT, errno.ENODEV, errno.ENXIO})
_RECONNECT_POLL_INTERVAL = 1.0


@contextmanager
def get_device_handle(keyboard_path: str) -> Iterator[libevdev.Device]:
    """ Safely get an evdev device handle. """

    fd = open(keyboard_path, 'rb')
    try:
        evdev = libevdev.Device(fd)
        yield evdev
    finally:
        fd.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--keyboard', type=str, default=str(),
                        help="Name or absolute path of your chattering keyboard device. "
                             "For Bluetooth keyboards, use a stable symlink from "
                             "/dev/input/by-id or /dev/input/by-path to support reconnection. "
                             "If left unset, will be attempted to be retrieved automatically.")
    parser.add_argument('-t', '--threshold', type=int, default=30, help="Filter time threshold in milliseconds. "
                                                                        "Default=30ms.")
    parser.add_argument('-v', '--verbosity', type=int, default=1, choices=[0, 1, 2])
    args = parser.parse_args()

    logging.basicConfig(
        level={
            0: logging.CRITICAL,
            1: logging.INFO,
            2: logging.DEBUG
        }[args.verbosity],
        handlers=[
            logging.StreamHandler(
                sys.stdout
            )
        ],
        format="%(asctime)s - %(message)s",
        datefmt="%H:%M:%S"
    )

    keyboard_path = resolve_keyboard_path(args.keyboard) if args.keyboard else retrieve_keyboard_path()

    # Warn if using a raw eventX path — symlinks under by-id/by-path are stable across Bluetooth reconnects
    if os.path.basename(os.path.dirname(keyboard_path)) not in ('by-id', 'by-path'):
        logging.warning(
            f"'{keyboard_path}' is not under /dev/input/by-id or /dev/input/by-path. "
            "Bluetooth reconnection support requires a stable symlink path."
        )

    while True:
        try:
            with get_device_handle(keyboard_path) as device:
                filter_chattering(device, args.threshold)
        except OSError as e:
            if e.errno in _RECONNECT_ERRORS:
                logging.info("Device disconnected. Waiting for reconnect...")
                while not os.path.exists(keyboard_path):
                    time.sleep(_RECONNECT_POLL_INTERVAL)
                logging.info("Device reconnected. Resuming...")
            else:
                raise
