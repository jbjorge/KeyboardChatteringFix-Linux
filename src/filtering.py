import logging
from collections import defaultdict
from typing import DefaultDict, Dict

import libevdev
import time


def filter_chattering(evdev: libevdev.Device, threshold: int) -> None:
    # add delay to allow enter key to work after execution
    time.sleep(1)
    # grab the device - now only we see the events it emits
    evdev.grab()
    # create a copy of the device that we can write to - this will emit the filtered events to anyone who listens
    ui_dev = evdev.create_uinput_device()

    logging.info("Listening to input events...")

    last_key_up: Dict[libevdev.EventCode, int] = {}
    key_pressed: DefaultDict[libevdev.EventCode, bool] = defaultdict(bool)

    try:
        while True:
            # since the descriptor is blocking, this blocks until there are events available
            for e in evdev.events():
                if _from_keystroke(e, threshold, last_key_up, key_pressed):
                    ui_dev.send_events([e, libevdev.InputEvent(libevdev.EV_SYN.SYN_REPORT, 0)])
    finally:
        try:
            evdev.ungrab()
        except Exception:
            pass


def _from_keystroke(
    event: libevdev.InputEvent,
    threshold: int,
    last_key_up: Dict[libevdev.EventCode, int],
    key_pressed: DefaultDict[libevdev.EventCode, bool],
) -> bool:
    # no need to relay those - we are going to emit our own
    if event.matches(libevdev.EV_SYN) or event.matches(libevdev.EV_MSC):
        return False

    # some events we don't want to filter, like EV_LED for toggling NumLock and the like, and also key hold events
    if not event.matches(libevdev.EV_KEY) or event.value > 1:
        logging.debug(f'FORWARDING {event.code}')
        return True

    # the values are 0 for up, 1 for down and 2 for hold
    if event.value == 0:
        if key_pressed[event.code]:
            logging.debug(f'FORWARDING {event.code} up')
            last_key_up[event.code] = event.sec * 1_000_000 + event.usec
            key_pressed[event.code] = False
            return True
        else:
            logging.info(f'FILTERING {event.code} up: key not pressed beforehand')
            return False

    prev = last_key_up.get(event.code)
    now = event.sec * 1_000_000 + event.usec

    if prev is None or now - prev > threshold * 1_000:
        logging.debug(f'FORWARDING {event.code} down')
        key_pressed[event.code] = True
        return True

    logging.info(
        f'FILTERED {event.code} down: last key up event happened {(now - prev) / 1E3} ms ago')
    return False
