# Pico W Pedale Controller v3

> **Neu:** Unter [`firmware/`](firmware/README.md) liegt die universelle Firmware fuer
> Pedale, Buttonbox und Lenkrad (konfigurierbar im Browser, nach dem Vorbild von FreeJoy).
> Die Dateien hier im Hauptordner sind die bisherige Pedal-Firmware.
FreeJoy-Ersatz mit WLAN-Konfigurator im Browser

## Hardware

| Bauteil | Anzahl |
|---|---|
| Raspberry Pi Pico **W** | 1 |
| AS5600 (analog OUT) | 3 |
| Taster (Momentary) | 1 |
| LED | 1 |
| Widerstand 330Ω | 1 |

## Verkabelung

```
Pico GP26  ──── AS5600 Gas      OUT
Pico GP27  ──── AS5600 Bremse   OUT
Pico GP28  ──── AS5600 Kupplung OUT

Pico GP3   ──── Taster ──── GND

Pico GP16  ──── 330Ω ──── LED ──── GND

Pico 3V3   ──── AS5600 VCC (alle drei)
Pico GND   ──── AS5600 GND (alle drei)
```

## Dateien auf den Pico W kopieren

```
/ (Root)
├── boot.py
├── code.py
├── settings.py
└── lib/
    ├── adafruit_hid/
    └── adafruit_debouncer.mpy
```

CircuitPython für Pico W: https://circuitpython.org/board/raspberry_pi_pico_w/
Libraries: https://circuitpython.org/libraries

## Bedienung

### Normalbetrieb (HID-Modus)
- Pico läuft als USB Gamepad
- LED aus
- Taster kurz drücken → WLAN startet

### WLAN/Kalibrierungs-Modus
- LED blinkt schnell
- Mit Handy oder PC mit WLAN **"Pico-Pedale"** verbinden
  Passwort: `pedale123` (änderbar in settings.py)
- Browser öffnen: **http://192.168.4.1**
- Achse kalibrieren:
  1. "Kalibrieren" bei gewünschter Achse klicken
  2. Pedal vollständig loslassen
  3. "Startpunkt setzen" klicken
  4. Pedal vollständig durchtreten
  5. "Endpunkt setzen" klicken → automatisch gespeichert ✅
- Taster kurz drücken **oder** "WLAN aus" im Browser → zurück zu HID

### LED-Signale
| Muster | Bedeutung |
|---|---|
| 3× langsam beim Start | Bereit |
| Schnelles Dauerblinken | WLAN aktiv |
| 2× kurz | WLAN gestartet |
| 3× kurz | Kalibrierung gespeichert |
| 3× langsam | Zurück zu HID |

## Dateien bearbeiten (Thonny empfohlen)
Da boot.py den USB-Massenspeicher deaktiviert:
- **Thonny IDE** verwenden (verbindet über serielle Schnittstelle)
- Oder: Pico mit gedrücktem **BOOTSEL** einstecken → erscheint als RPI-RP2

## settings.py anpassen
```python
AP_SSID     = "Pico-Pedale"   # WLAN-Name
AP_PASSWORD = "pedale123"     # Passwort (min. 8 Zeichen)
AP_CHANNEL  = 6               # WLAN-Kanal
```
