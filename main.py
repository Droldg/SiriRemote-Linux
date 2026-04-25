import sys
import os
from remote.remote import SiriRemote, RemoteListener
from input.hid_input import Input

hid_input = Input()


class Callback(RemoteListener):
    def __init__(self, generation: str):
        self.generation = generation

    def event_connected(self):
        print("Fjernbetjening forbundet", flush=True)

    def event_disconnected(self, reason: str = None):
        if reason:
            print("Fjernbetjening ikke forbundet:", reason, flush=True)
        else:
            print("Fjernbetjening ikke forbundet", flush=True)

    def event_error(self, message: str):
        print("Debug:", message, flush=True)

    def event_battery(self, percent: int):
        pass

    def event_power(self, charging: bool):
        pass

    def event_button(self, button: int):
        handle_button_event(button, self.generation)

    def event_touchpad(self, data, pressed: bool):
        if len(data) == 2 and data[0][2] == 0:  # "ghost" finger with pressure 0
            handle_touchpad_event(data[1])
        else:
            handle_touchpad_event(data[0])


prevXY = [None, None]


def handle_touchpad_event(data):
    sensi = 8
    x = data[0] * sensi
    y = data[1] * - sensi
    p = data[2]

    if prevXY[0] is not None and prevXY[1] is not None:
        hid_input.move_cursor(x - prevXY[0], y - prevXY[1])

    if p == 0:
        prevXY[0] = prevXY[1] = None
    else:
        prevXY[0] = x
        prevXY[1] = y


def handle_button_event(button, generation: str):
    if button == SiriRemote.BUTTON_RELEASED:
        hid_input.release()
        return

    if generation == "gen3":
        handle_gen3_button_event(button)
        return

    if button & SiriRemote.BUTTON_AIRPLAY:
        hid_input.add_key(Input.KEY_NEXTSONG)

    if button & SiriRemote.BUTTON_VOLUME_UP:
        hid_input.add_key(Input.KEY_VOLUMEUP)

    if button & SiriRemote.BUTTON_VOLUME_DOWN:
        hid_input.add_key(Input.KEY_VOLUMEDOWN)

    if button & SiriRemote.BUTTON_PLAY_PAUSE:
        hid_input.add_key(Input.KEY_PLAYPAUSE)

    # if button & SiriRemote.BUTTON_SIRI:
    #     print("Siri")

    if button & SiriRemote.BUTTON_MENU:
        hid_input.add_key(Input.KEY_PREVIOUSSONG)

    if button & SiriRemote.BUTTON_TOUCHPAD_2:
        hid_input.add_key(Input.BTN_RIGHT)

    if button & SiriRemote.BUTTON_TOUCHPAD:
        hid_input.add_key(Input.BTN_LEFT)

    hid_input.press()


def handle_gen3_button_event(button):
    if button & 2:  # volume up
        hid_input.add_key(Input.KEY_VOLUMEUP)

    if button & 4:  # volume down
        hid_input.add_key(Input.KEY_VOLUMEDOWN)

    if button & 8:  # touchpad click
        hid_input.add_key(Input.BTN_LEFT)

    if button & 64:  # back
        hid_input.add_key(Input.KEY_PREVIOUSSONG)

    if button & 256:  # play/pause
        hid_input.add_key(Input.KEY_PLAYPAUSE)

    hid_input.press()


if __name__ == '__main__':
    try:
        if len(sys.argv) > 1:
            if "--debug" in sys.argv:
                os.environ["SIRIREMOTE_DEBUG"] = "1"

            generation = "gen3" if "--gen3" in sys.argv else "gen1"
            magic_with_response = "--no-magic-response" not in sys.argv
            addr_type = "random" if "--addr-type=random" in sys.argv else "public"
            magic_value = next(
                (bytes.fromhex(arg.split("=", 1)[1]) for arg in sys.argv if arg.startswith("--magic=")),
                None
            )
            mac = next(arg for arg in sys.argv[1:] if not arg.startswith("--"))
            SiriRemote(
                mac,
                Callback(generation),
                generation,
                magic_with_response,
                addr_type,
                5.0,
                magic_value
            )
        else:
            print("error: no mac address")
    except KeyboardInterrupt:
        hid_input.close()
        exit()
