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
    __HANDLE_INPUT = 35
    __HANDLE_BATTERY = 40
    __HANDLE_POWER = 43
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

    def __init__(self, mac, listener: RemoteListener):
        self.__mac = mac
        self.__device = None
        self.__listener = listener
        self.__connected = None
        self.__last_disconnect_reason = None
        self.__debug = os.environ.get("SIRIREMOTE_DEBUG") == "1"
        self.__setup()

    def __setup(self):
        while True:
            setup_step = "connecting"
            try:
                self.__debug_log("connecting")
                self.__device = bt.Device(self.__mac)
                self.__device.connect()
                setup_step = "setting mtu"
                self.__debug_log("setting mtu")
                self.__device.set_mtu(104)
                self.__device.set_listener(self.__handle_notification)
                setup_step = "enabling hid notifications"
                self.__debug_log("enabling hid notifications")
                self.__device.enable_notifications(0x0024)  # hid service
                setup_step = "sending magic byte"
                self.__debug_log("sending magic byte")
                self.__device.write_characteristic(0x001d, b'\xAF')  # "magic" byte
                setup_step = "enabling battery notifications"
                self.__debug_log("enabling battery notifications")
                self.__device.enable_notifications(0x0029)  # battery service
                setup_step = "enabling power notifications"
                self.__debug_log("enabling power notifications")
                self.__device.enable_notifications(0x002c)  # power service
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
                self.__listener.event_disconnected(reason)
            return

        self.__connected = connected
        if connected:
            self.__last_disconnect_reason = None
            self.__listener.event_connected()
        else:
            self.__last_disconnect_reason = reason
            self.__listener.event_disconnected(reason)

    def __debug_log(self, message: str):
        if self.__debug:
            self.__listener.event_error(message)

    def __handle_notification(self, handle, data):
        self.__debug_log(f"notification handle={handle} data={data.hex()}")

        if handle == self.__HANDLE_BATTERY:
            self.__handle_battery(data)
        elif handle == self.__HANDLE_POWER:
            self.__handle_power(data)
        elif handle == self.__HANDLE_INPUT:
            self.__handle_input(data)

    def __handle_battery(self, data):
        self.__listener.event_battery(data[0])

    def __handle_power(self, data):
        if data[0] == self.__POWER_CHARGING:
            self.__listener.event_power(True)
        elif data[0] == self.__POWER_DISCHARGING:
            self.__listener.event_power(False)

    def __handle_input(self, data):
        button = data[1]
        if data[0] == 2 and button & self.BUTTON_TOUCHPAD:
            button += self.BUTTON_TOUCHPAD_2 - self.BUTTON_TOUCHPAD

        if button != self.__lastButton:
            self.__lastButton = button
            self.__listener.event_button(button)

        if len(data) >= 3 and data[2] == self.__TOUCH_EVENT:
            self.__handle_touchpad(data)

    def __handle_touchpad(self, data):
        pressed = data[1] & self.BUTTON_TOUCHPAD
        if len(data) == 13:
            self.__listener.event_touchpad([self.__decode_finger(data[6:13])], pressed)
        elif len(data) == 20:
            self.__listener.event_touchpad([self.__decode_finger(data[6:13]),
                                            self.__decode_finger(data[13:20])], pressed)

    @staticmethod
    def __decode_finger(data):
        x = int((data[0] + 255 * (data[1] & 7) - 230) / 15)
        y = (data[2] if data[2] & 128 else data[2] + 255) - 188
        p = data[5]
        return x, y, p
