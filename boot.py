# boot.py - muss im Root des Pico W liegen
#
# Gegenueber der alten Version gibt es einen Notausgang:
# Wird der WLAN-Taster (GP3) beim Einstecken gedrueckt gehalten, bleibt das
# USB-Laufwerk CIRCUITPY sichtbar. Dann kannst du Dateien am PC bearbeiten,
# ohne den Umweg ueber die serielle Konsole. Ohne gedrueckten Taster verhaelt
# sich alles wie bisher: Laufwerk aus, Dateisystem fuer den Pico beschreibbar
# (das braucht calibration.json).

import board
import digitalio
import storage
import usb_hid

TASTER_PIN = "GP3"          # muss zu WIFI_BTN_PIN in settings.py passen

# Joystick HID Descriptor (v9.6)
# 3 Achsen (Rx, Ry, Rz) mit je 8 bit (-127 bis 127), 16 Buttons
#
# Bewusst KEIN Gamepad und KEINE Achsen X/Y: Spiele wie Automobilista 2 und
# Project CARS steuern ihr Menue ueber X/Y von Gamepads. Ein losgelassenes
# Pedal sendet -127 (Anschlag), das Menue scrollte dadurch von selbst.
GAMEPAD_DESCRIPTOR = bytes((
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x04,        # Usage (Joystick)
    0xA1, 0x01,        # Collection (Application)
    0x85, 0x04,        #   Report ID (4)
    # Buttons (16 Stueck, je 1 bit)
    0x05, 0x09,        #   Usage Page (Button)
    0x19, 0x01,        #   Usage Minimum (1)
    0x29, 0x10,        #   Usage Maximum (16)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x10,        #   Report Count (16)
    0x81, 0x02,        #   Input (Data, Variable, Absolute)
    # Achsen Rx, Ry, Rz (je 8 bit, -127 bis 127)
    0x05, 0x01,        #   Usage Page (Generic Desktop)
    0x15, 0x81,        #   Logical Minimum (-127)
    0x25, 0x7F,        #   Logical Maximum (127)
    0x09, 0x33,        #   Usage (Rx)  Gas
    0x09, 0x34,        #   Usage (Ry)  Bremse
    0x09, 0x35,        #   Usage (Rz)  Kupplung
    0x75, 0x08,        #   Report Size (8)
    0x95, 0x03,        #   Report Count (3)
    0x81, 0x02,        #   Input (Data, Variable, Absolute)
    0xC0,              # End Collection
))

gamepad = usb_hid.Device(
    report_descriptor=GAMEPAD_DESCRIPTOR,
    usage_page=0x01,         # Generic Desktop
    usage=0x04,              # Joystick (muss zu code.py passen)
    report_ids=(4,),
    in_report_lengths=(5,),  # 2 Byte Buttons + 3 Byte Achsen
    out_report_lengths=(0,),
)

usb_hid.enable((gamepad,))

# Taster gegen GND: gedrueckt = False
taster = digitalio.DigitalInOut(getattr(board, TASTER_PIN))
taster.direction = digitalio.Direction.INPUT
taster.pull = digitalio.Pull.UP
wartungsmodus = not taster.value
taster.deinit()             # Pin freigeben, code.py braucht ihn gleich

if wartungsmodus:
    # Laufwerk bleibt sichtbar. Der Pico kann dann NICHT selbst speichern,
    # code.py meldet das in der Weboberflaeche.
    print("Wartungsmodus: CIRCUITPY sichtbar, Speichern deaktiviert")
else:
    # Normalbetrieb: Laufwerk aus. Damit wird CIRCUITPY fuer den Pico selbst
    # beschreibbar, calibration.json kann gespeichert werden.
    storage.disable_usb_drive()
