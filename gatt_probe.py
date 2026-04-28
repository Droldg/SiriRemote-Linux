import sys
import time

from bluepy.btle import BTLEException, DefaultDelegate, Peripheral, Scanner


class DebugDelegate(DefaultDelegate):
    def handleNotification(self, handle, data):
        print(f"notification handle=0x{handle:04x} data={data.hex()}", flush=True)


def main():
    if len(sys.argv) < 2:
        print("usage: python gatt_probe.py <mac> [--iface=0]")
        return

    iface = next(
        (int(arg.split("=", 1)[1]) for arg in sys.argv if arg.startswith("--iface=")),
        0
    )
    scan_timeout = next(
        (float(arg.split("=", 1)[1]) for arg in sys.argv if arg.startswith("--scan-timeout=")),
        15.0
    )
    mac = next(arg for arg in sys.argv[1:] if not arg.startswith("--"))

    seen = False
    if scan_timeout > 0:
        print(f"scanning on hci{iface} for {scan_timeout} seconds")
        try:
            for scanned_device in Scanner(iface).scan(scan_timeout):
                if scanned_device.addr.lower() == mac.lower():
                    seen = True
                    print(f"seen {mac} rssi={scanned_device.rssi}")
                    break
        except BTLEException as error:
            print(f"scan failed on hci{iface}: {error}")

        if not seen:
            print(f"did not see {mac}; press a button on the remote and try again")
            print("not connecting because scan did not see the remote")
            return
    else:
        print("scan skipped")

    print(f"connecting on hci{iface}")
    device = Peripheral(mac, "public", iface)
    device.withDelegate(DebugDelegate())

    print("connected")
    print("relevant characteristics:")
    for characteristic in device.getCharacteristics():
        handle = characteristic.getHandle()
        if handle in (0x001d, 0x0023, 0x0028, 0x002b):
            print(
                f"handle=0x{handle:04x} uuid={characteristic.uuid} "
                f"properties={characteristic.propertiesToString()}"
            )

    writes = [
        ("battery notify", 0x0029, b"\x01\x00", True),
        ("power notify", 0x002c, b"\x01\x00", True),
        ("hid notify", 0x0024, b"\x01\x00", True),
        ("magic with response", 0x001d, b"\xaf", True),
        ("magic without response", 0x001d, b"\xaf", False),
    ]

    for name, handle, value, with_response in writes:
        try:
            print(f"write {name}: handle=0x{handle:04x} value={value.hex()} response={with_response}")
            device.writeCharacteristic(handle, value, with_response)
            print(f"ok {name}")
        except Exception as error:
            print(f"failed {name}: {error}")

        for _ in range(10):
            try:
                device.waitForNotifications(0.2)
            except Exception as error:
                print(f"notification wait failed after {name}: {error}")
                device.disconnect()
                return

    print("listening for 10 seconds; press buttons and touch the pad")
    end = time.time() + 10
    while time.time() < end:
        try:
            device.waitForNotifications(1.0)
        except Exception as error:
            print(f"notification wait failed: {error}")
            break

    device.disconnect()


if __name__ == "__main__":
    main()
