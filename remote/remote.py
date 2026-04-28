import os
import time
from bluepy.btle import BTLEDisconnectError, BTLEException
from . import bt


class RemoteListener:
    def event_connected(self):
        pass

    def event_disconnected(self, reason: str = None):
        pass

    def event_error(self, message: str):
        pass

    def event_battery(self, percent: int):
        pass

    def event_power(self, charging: bool):
        pass

    def event_button(self, button: int):
        pass

    def event_touchpad(self, data, pressed: bool):
        pass


class SiriRemote:
    __PROFILE_GEN1 = {
        "mtu": 104,
        "handle_input": 35,
        "handle_touch": 35,
        "handle_battery": 40,
        "handle_power": 43,
        "notify_input": (0x0024,),
        "notify_battery": 0x0029,
        "notify_power": 0x002c,
        "magic_handle": 0x001d,
        "magic_value": b'\xAF',
    }
    __PROFILE_GEN3 = {
        "mtu": 247,
        "handle_input": 57,
        "handle_touch": 61,
        "handle_battery": 46,
        "handle_power": 49,
        "notify_input": (0x003a, 0x003e),
        "notify_battery": 0x002f,
        "notify_power": 0x0032,
        "magic_handle": 0x004d,
        "magic_value": b'\xF0\x00',
    }
    __TOUCH_EVENT = 50

    __POWER_CHARGING = 171
    __POWER_DISCHARGING = 175
    __POWER_PLUGGED_IN = 187

    BUTTON_RELEASED = 0
    BUTTON_AIRPLAY = 1
    BUTTON_VOLUME_UP = 2
    BUTTON_VOLUME_DOWN = 4
    BUTTON_PLAY_PAUSE = 8
    BUTTON_SIRI = 16
    BUTTON_MENU = 32
    BUTTON_TOUCHPAD_2 = 64  # custom: 2 finger click
    BUTTON_TOUCHPAD = 128

    __lastButton = 0

    def __init__(
            self,
            mac,
            listener: RemoteListener,
            generation: str = "gen1",
            magic_with_response: bool = True,
            addr_type: str = "public",
            scan_timeout: float = 5.0,
            magic_value: bytes = None,
            iface: int = 0
    ):
        self.__mac = mac
        self.__addr_type = addr_type
        self.__scan_timeout = scan_timeout
        self.__iface = iface
        self.__device = None
        self.__listener = listener
        self.__generation = generation
        self.__profile = self.__get_profile(generation)
        self.__magic_with_response = magic_with_response
        self.__magic_value = magic_value or self.__profile["magic_value"]
        self.__connected = None
        self.__last_disconnect_reason = None
        self.__same_disconnect_count = 0
        self.__debug = os.environ.get("SIRIREMOTE_DEBUG") == "1"
        self.__setup()

    @classmethod
    def __get_profile(cls, generation: str):
        if generation == "gen1":
            return cls.__PROFILE_GEN1
        if generation == "gen3":
            return cls.__PROFILE_GEN3

        raise ValueError(f"unsupported Siri Remote generation: {generation}")

    def __setup(self):
        while True:
            setup_step = "connecting"
            try:
                self.__debug_log("connecting")
                self.__device = bt.Device(self.__mac, self.__addr_type, self.__scan_timeout, self.__iface)
                self.__device.connect()
                self.__debug_log("connected")
                setup_step = "setting mtu"
                self.__debug_log("setting mtu")
                self.__device.set_mtu(self.__profile["mtu"])
                self.__device.set_listener(self.__handle_notification)
                setup_step = "enabling battery notifications"
                self.__debug_log("enabling battery notifications")
                self.__device.enable_notifications(self.__profile["notify_battery"])  # battery service
                self.__drain_notifications()
                setup_step = "enabling power notifications"
                self.__debug_log("enabling power notifications")
                self.__device.enable_notifications(self.__profile["notify_power"])  # power service
                self.__drain_notifications()
                setup_step = "enabling hid notifications"
                self.__debug_log("enabling hid notifications")
                for handle in self.__profile["notify_input"]:
                    self.__device.enable_notifications(handle)  # hid service
                    self.__drain_notifications()
                setup_step = "sending magic byte"
                self.__debug_log("sending magic byte")
                self.__device.write_characteristic(
                    self.__profile["magic_handle"],
                    self.__magic_value,
                    self.__magic_with_response
                )  # "magic" byte
                self.__drain_notifications()
                setup_step = "listening"
                self.__debug_log("listening")
                self.__set_connected(True)
                self.__device.loop()
            except (BTLEDisconnectError, BTLEException) as error:
                reason = f"{setup_step}: {error}"
                self.__debug_log(f"bluetooth error: {reason}")
                if self.__device:
                    self.__device.disconnect()
                self.__set_connected(False, reason)
                self.__listener.event_button(0)  # release all keys
                time.sleep(0.5)

    def __set_connected(self, connected: bool, reason: str = None):
        if self.__connected == connected:
            if not connected and reason and reason != self.__last_disconnect_reason:
                self.__last_disconnect_reason = reason
                self.__same_disconnect_count = 1
                self.__listener.event_disconnected(reason)
            elif not connected and reason:
                self.__same_disconnect_count += 1
                if self.__same_disconnect_count % 10 == 0:
                    self.__listener.event_disconnected(
                        f"{reason} (gentaget {self.__same_disconnect_count} gange)"
                    )
            return

        self.__connected = connected
        if connected:
            self.__last_disconnect_reason = None
            self.__same_disconnect_count = 0
            self.__listener.event_connected()
        else:
            self.__last_disconnect_reason = reason
            self.__same_disconnect_count = 1
            self.__listener.event_disconnected(reason)

    def __debug_log(self, message: str):
        if self.__debug:
            self.__listener.event_error(message)

    def __drain_notifications(self):
        for _ in range(5):
            self.__device.wait_for_notifications(0.05)

    def __handle_notification(self, handle, data):
        self.__debug_log(f"notification handle={handle} data={data.hex()}")

        if handle == self.__profile["handle_battery"]:
            self.__handle_battery(data)
        elif handle == self.__profile["handle_power"]:
            self.__handle_power(data)
        elif handle == self.__profile["handle_input"]:
            self.__handle_input(data)
        elif handle == self.__profile["handle_touch"]:
            self.__handle_touchpad(data)

    def __handle_battery(self, data):
        self.__listener.event_battery(data[0])

    def __handle_power(self, data):
        if data[0] == self.__POWER_CHARGING:
            self.__listener.event_power(True)
        elif data[0] == self.__POWER_DISCHARGING:
            self.__listener.event_power(False)

    def __handle_input(self, data):
        self.__debug_log(f"input data={data.hex()}")

        if self.__generation == "gen3":
            button = int.from_bytes(data, byteorder='little')

            if button != self.__lastButton:
                self.__lastButton = button
                self.__listener.event_button(button)

            return

        button = data[1]
        if data[0] == 2 and button & self.BUTTON_TOUCHPAD:
            button += self.BUTTON_TOUCHPAD_2 - self.BUTTON_TOUCHPAD

        if button != self.__lastButton:
            self.__lastButton = button
            self.__listener.event_button(button)

        if len(data) >= 3 and data[2] == self.__TOUCH_EVENT:
            self.__handle_touchpad(data)

    def __handle_touchpad(self, data):
        self.__debug_log(f"touch data={data.hex()}")

        if self.__generation == "gen3":
            if len(data) == 11:
                self.__listener.event_touchpad([self.__decode_finger(data[4:11])], False)

            return

        pressed = data[1] & self.BUTTON_TOUCHPAD
        if len(data) == 13:
            self.__listener.event_touchpad([self.__decode_finger(data[6:13])], pressed)
        elif len(data) == 20:
            self.__listener.event_touchpad([self.__decode_finger(data[6:13]),
                                            self.__decode_finger(data[13:20])], pressed)

    @staticmethod
    def __decode_finger(data):
        x = int((data[0] + 255 * (data[1] & 7) - 230) / 15)
        if x < 0:
            x = x + 150
        y = (data[2] if data[2] & 128 else data[2] + 255) - 188
        p = data[5]
        return x, y, p
