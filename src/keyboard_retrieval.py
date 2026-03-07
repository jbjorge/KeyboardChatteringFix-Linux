import logging
import os
from typing import Final, List

INPUT_DEVICES_PATH: Final = '/dev/input/by-id'

def retrieve_keyboard_name() -> str:
    # List all devices in the directory
    all_devices = os.listdir(INPUT_DEVICES_PATH)

    keyboard_devices = [
        d for d in all_devices
    ]

    # Remove duplicates just in case
    keyboard_devices = list(set(keyboard_devices))

    n_devices = len(keyboard_devices)

    if n_devices == 0:
        raise ValueError(f"Couldn't find a keyboard in '{INPUT_DEVICES_PATH}'")

    if n_devices == 1:
        logging.info(f"Found keyboard: {keyboard_devices[0]}")
        return keyboard_devices[0]

    # Use native Python input for user selection
    print("Select a device:")
    for idx, device in enumerate(sorted(keyboard_devices), start=1):
        print(f"{idx}. {device}")

    selected_idx = -1
    while selected_idx < 1 or selected_idx > n_devices:
        try:
            selected_idx = int(input("Enter your choice (number): "))
            if selected_idx < 1 or selected_idx > n_devices:
                print(f"Please select a number between 1 and {n_devices}")
        except ValueError:
            print("Please enter a valid number")

    return keyboard_devices[selected_idx - 1]

def abs_keyboard_path(device: str) -> str:
    return os.path.join(INPUT_DEVICES_PATH, device)
