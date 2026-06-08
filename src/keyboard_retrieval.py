import os
from typing import Dict, Final, List, Optional, Tuple

_PROC_INPUT_DEVICES: Final = '/proc/bus/input/devices'
_INPUT_PATH: Final = '/dev/input'
_BY_ID_PATH: Final = '/dev/input/by-id'
_BY_PATH_PATH: Final = '/dev/input/by-path'
_SEARCH_DIRS: Final = [_BY_ID_PATH, _BY_PATH_PATH]

# Kept for backward compatibility
INPUT_DEVICES_PATH: Final = _BY_ID_PATH

_BUS_NAMES: Final[Dict[int, str]] = {
    0x0001: 'PCI',
    0x0003: 'USB',
    0x0005: 'Bluetooth',
    0x0011: 'PS/2',
    0x0018: 'I2C',
    0x0019: 'Platform',
}


def _parse_proc_input_devices() -> List[Dict[str, str]]:
    """Parse /proc/bus/input/devices into a list of device attribute dicts."""
    try:
        with open(_PROC_INPUT_DEVICES) as f:
            content = f.read()
    except OSError:
        return []

    devices = []
    current: Dict[str, str] = {}
    for line in content.splitlines():
        if not line.strip():
            if current:
                devices.append(current)
                current = {}
            continue
        if ': ' in line:
            _, value = line.split(': ', 1)
            key = line[0]
            current[key] = value
    if current:
        devices.append(current)
    return devices


def _stable_path_for_event(event_node: str) -> Optional[str]:
    """Return a stable by-id or by-path symlink for the given eventX node, if one exists."""
    real_event = os.path.realpath(os.path.join(_INPUT_PATH, event_node))
    for directory in _SEARCH_DIRS:
        try:
            for name in os.listdir(directory):
                candidate = os.path.join(directory, name)
                if os.path.realpath(candidate) == real_event:
                    return candidate
        except FileNotFoundError:
            continue
    return None


def _find_keyboard_devices() -> List[Tuple[str, str]]:
    """
    Find keyboard devices from /proc/bus/input/devices.
    Returns (path, label) pairs where path is a stable symlink when available,
    otherwise the raw /dev/input/eventX node.
    """
    seen_real: set = set()
    result = []

    for dev in _parse_proc_input_devices():
        handlers = dev.get('H', '')
        # Only include devices with a keyboard handler
        if 'kbd' not in handlers.split():
            continue

        # Extract the eventX node from the handlers line
        event_node = next((h for h in handlers.split() if h.startswith('event')), None)
        if event_node is None:
            continue

        event_path = os.path.join(_INPUT_PATH, event_node)
        real = os.path.realpath(event_path)
        if real in seen_real:
            continue
        seen_real.add(real)

        # Prefer a stable symlink for reconnection support
        stable = _stable_path_for_event(event_node)
        path = stable if stable else event_path

        name = dev.get('N', event_node).removeprefix('Name=').strip('"')
        try:
            bus_id = int(dev.get('I', '').split()[0].split('=')[1], 16)
            bus_name = _BUS_NAMES.get(bus_id, f'Bus {bus_id:#06x}')
        except (IndexError, ValueError):
            bus_name = None

        label = f"{name} ({bus_name})" if bus_name else name
        result.append((path, label))

    return result


def retrieve_keyboard_path() -> str:
    """Interactively select a keyboard device and return its absolute path."""
    devices = _find_keyboard_devices()

    if not devices:
        raise ValueError(f"Couldn't find any keyboard devices in '{_PROC_INPUT_DEVICES}'")

    n = len(devices)
    default_idx = 1 if n == 1 else None

    print("Available keyboard devices:")
    for idx, (path, label) in enumerate(devices, start=1):
        suggestion = " (suggested)" if idx == default_idx else ""
        print(f"{idx}. {label}{suggestion}")

    prompt = f"Enter your choice (number){f' [default: {default_idx}]' if default_idx else ''}: "
    selected_idx = -1
    while selected_idx < 1 or selected_idx > n:
        try:
            raw = input(prompt).strip()
            if raw == "" and default_idx is not None:
                selected_idx = default_idx
            else:
                selected_idx = int(raw)
            if selected_idx < 1 or selected_idx > n:
                print(f"Please select a number between 1 and {n}")
        except ValueError:
            print("Please enter a valid number")

    return devices[selected_idx - 1][0]


def resolve_keyboard_path(keyboard: str) -> str:
    """Resolve a keyboard name or absolute path to an absolute path."""
    if os.path.isabs(keyboard):
        if not os.path.exists(keyboard):
            raise ValueError(f"Keyboard device '{keyboard}' not found")
        return keyboard
    # Try by-id / by-path by name
    for directory in _SEARCH_DIRS:
        candidate = os.path.join(directory, keyboard)
        if os.path.exists(candidate):
            return candidate
    # Try as a bare eventX node
    candidate = os.path.join(_INPUT_PATH, keyboard)
    if os.path.exists(candidate):
        return candidate
    raise ValueError(
        f"Couldn't find keyboard '{keyboard}' in "
        f"'{_BY_ID_PATH}', '{_BY_PATH_PATH}', or '{_INPUT_PATH}'"
    )


# Kept for backward compatibility
def retrieve_keyboard_name() -> str:
    return retrieve_keyboard_path()


def abs_keyboard_path(device: str) -> str:
    return resolve_keyboard_path(device)
