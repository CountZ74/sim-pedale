# Pico W Pedale Controller

Firmware für einen selbstgebauten Pedalsatz fürs Sim-Racing. Läuft mit
CircuitPython auf einem Raspberry Pi Pico W und meldet sich am PC als
USB-Joystick mit drei Achsen (Rx, Ry, Rz).

## Hardware

| Pin  | Anschluss |
|------|-----------|
| GP26 | AS5600 Gas, Analogausgang |
| GP27 | AS5600 Bremse, Analogausgang (oder HX711 DT) |
| GP28 | AS5600 Kupplung, Analogausgang |
| GP0  | HX711 SCK |
| GP1  | HX711 DT |
| GP3  | Taster WLAN, gegen GND |
| GP16 | Status-LED, über 330 Ω gegen GND |

Gas und Kupplung messen den Winkel mit einem AS5600. Der Magnet sitzt auf einer
Zahnriemenscheibe, die über einen federgespannten Riemen am Pedalarm hängt —
dadurch sieht der Sensor mehr Weg als das Pedal und die Auflösung steigt.

Die Bremse arbeitet wahlweise genauso oder über eine Wägezelle am HX711
(`BREMSE_TYP` in `settings.py`). Kraftmessung entspricht dem Verhalten einer
echten Bremse deutlich besser als Wegmessung.

## Dateien

| Datei | Zweck |
|-------|-------|
| `code.py` | Firmware |
| `boot.py` | HID-Descriptor, USB-Laufwerk, Wartungsmodus |
| `settings.py` | Konfiguration |
| `index.html` | Weboberfläche, wird aus dem Flash ausgeliefert |
| `test_wrap.py` | Prüft die Kalibriermathematik, **läuft am PC** |
| `test_pio_hx711.py` | Prüft den PIO-Reader, läuft auf dem Pico |

Alles außer `test_wrap.py` gehört ins Root von CIRCUITPY, nicht nach `lib/`.

## Abhängigkeiten in `lib/`

```
adafruit_debouncer.mpy
adafruit_ticks.mpy
adafruit_pioasm.mpy          # nur bei HX711_MODE = "pio"
adafruit_hx711/              # nur bei HX711_MODE = "bitbang"
```

## Bedienung

Taster an GP3 startet den Access Point (`Pico-Pedale`). Weboberfläche unter
http://192.168.4.1 — Kalibrierung und Kennlinien. Taster nochmal drücken
beendet den AP.

Kalibriert wird per Sweep: Nullpunkt bei losgelassenem Pedal setzen, dann
zwei-, dreimal voll durchtreten, fertig. Weg und Richtung ergeben sich von
selbst.

## Wartungsmodus

`boot.py` blendet das USB-Laufwerk CIRCUITPY aus, damit der Pico seine
`calibration.json` selbst schreiben kann. Beides gleichzeitig geht nicht.

Um an die Dateien zu kommen: **GP3-Taster beim Einstecken gedrückt halten.**
Dann bleibt das Laufwerk sichtbar — der Pico kann dann allerdings nicht
speichern, die Weboberfläche weist oben darauf hin.

## Zwei Dinge, die nicht offensichtlich sind

**Wraparound.** Der AS5600 springt am Nulldurchgang von 65535 auf 0. Läuft der
Pedalweg über diese Grenze, ist eine min/max-Kalibrierung wertlos. Deshalb wird
ein Nullpunkt und ein vorzeichenbehafteter Weg gespeichert und modulo 65536
gerechnet. Wege bis zu einer vollen Umdrehung sind möglich, die Grenze darf
beliebig oft überquert werden.

**HX711-Datenrate.** Ab Werk laufen die Module mit 10 Messungen pro Sekunde —
für ein Bremspedal unbrauchbar. Die Lötbrücke auf dem Board schaltet auf 80 Hz.
Danach ist die Bibliothek der Engpass: sie klopft die 25 Taktimpulse einzeln in
Python aus und braucht 13,8 ms, mehr als die 12,5 ms Wandlungsdauer. Deshalb
liest die Firmware den HX711 über die PIO-Einheit des RP2040 aus, das kostet
rund 225 µs.

## Tests

```bash
python3 test_wrap.py     # am PC, prüft die Kalibriermathematik
```

Auf dem Pico, im REPL nach Strg+C:

```python
import test_pio_hx711    # misst Datenrate und Lesezeit des HX711
```
