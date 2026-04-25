import sys

from evdev import InputDevice, categorize, ecodes, list_devices


def list_input_devices():
    for path in list_devices():
        device = InputDevice(path)
        print(f"{path}: {device.name} ({device.phys})")


def read_input_device(path):
    device = InputDevice(path)
    print(f"Reading {path}: {device.name}")
    for event in device.read_loop():
        if event.type == ecodes.EV_SYN:
            continue

        print(categorize(event))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        read_input_device(sys.argv[1])
    else:
        list_input_devices()
