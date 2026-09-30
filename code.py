"""
Pico W Pedale Controller v9.6 - Wraparound-Kalibrierung + schneller Webserver
=============================================================================
v9.6: Der Pico meldet sich als Joystick mit den Achsen Rx/Ry/Rz statt als
      Gamepad mit X/Y/Z. Grund: Automobilista 2 (und Project CARS) lassen
      Gamepads das Menue steuern; das Pedal in Ruhestellung (-127) wurde als
      dauernd gedrueckte Richtung gelesen. Achszuordnung im Spiel muss nach
      dem Update neu vorgenommen werden. Aendert boot.py UND code.py.

v9.5: Der HX711 wird ueber die PIO-Einheit des RP2040 ausgelesen statt per
      Bit-Banging in Python. Die Bibliothek brauchte 13,8 ms pro Lesung - mehr
      als die 12,5 ms Wandlungsdauer bei 80 Hz, deshalb kam nur jede zweite
      Wandlung an (gemessene 42 statt 80 Hz) und der Pico verbrachte 58 % der
      Rechenzeit mit Taktimpulsen. Ueber PIO kostet eine Lesung rund 225 us.
      Zurueckschaltbar mit HX711_MODE = "bitbang" in settings.py.

v9.4: Die Abdeckungskarte fuellt die Strecke zwischen zwei Messungen mit auf.
      In v9.3 wurde nur das Feld der Messung selbst markiert - bei einem
      schnellen Durchtritt liegen aber mehrere Felder dazwischen, also blieben
      Loecher und der zusammenhaengende Bogen war nur ein paar Grad lang.
      Waehrend der Wegmessung wird ausserdem kein HID mehr gesendet, das
      erhoeht die Abtastrate.

v9.3: Der Sweep summiert keine Schritte mehr auf, sondern kreuzt nur noch an,
      welche Winkelfelder das Pedal besucht hat (256 Felder zu je 1,4 Grad).
      Diese Karte kennt weder Reihenfolge noch Zeit - eine Messpause laesst
      hoechstens ein Feld leer, das der naechste Durchtritt wieder fuellt.
      Damit entfallen die Zeitgrenzen aus v9.2, die faelschlich ansprangen,
      sobald ein gc.collect() laenger als 50 ms brauchte.

v9.2: Die Sweep-Abtastung prueft jede Messung auf Plausibilitaet. Riss die
      Messung ab (z.B. weil die Hauptschleife auf einen HTTP-Request wartete)
      und das Pedal bewegte sich in dieser Pause um mehr als eine halbe
      Umdrehung, wurde der Schritt mit falschem Vorzeichen gezaehlt - der
      Zaehler lief dann auf absurde Werte wie 574 Grad. Zusaetzlich blockiert
      der Webserver die Hauptschleife nicht mehr.

v9.1: Der Sweep entfaltet den Pedalweg jetzt schrittweise statt am Stueck.
      v9.0 nahm an, dass ein Pedalweg kuerzer als eine halbe Umdrehung ist,
      und deckelte alles darueber bei 180 Grad. Pedale mit grossem Schwenk-
      bereich (z.B. 210 Grad) wurden dadurch falsch kalibriert: erst passiert
      nichts, dann springt die Anzeige auf 100 Prozent und faellt am Ende
      wieder ab. Jetzt sind Wege bis zu einer vollen Umdrehung moeglich.

Hardware (Pins ueber settings.py aenderbar):
  GP26  -> AS5600 Gas      OUT (analog)
  GP27  -> AS5600 Bremse   OUT (analog) ODER HX711 DT
  GP28  -> AS5600 Kupplung OUT (analog)
  GP0   -> HX711 SCK       (nur bei BREMSE_TYP = "hx711")
  GP3   -> Taster WLAN (gegen GND)
  GP16  -> Status-LED (ueber 330 Ohm gegen GND)

Neu gegenueber v8
-----------------
1. Wraparound. Der AS5600 springt am Nulldurchgang von 65535 auf 0. Statt
   min/max wird jetzt ein Nullpunkt ("start") und ein vorzeichenbehafteter
   Weg ("span") gespeichert und modulo 65536 gerechnet. Der Pedalweg darf
   die Grenze beliebig oft ueberqueren.

2. Sweep-Kalibrierung. Nullpunkt setzen, Pedal ein paar Mal voll durchtreten,
   fertig. Die Firmware verfolgt die groesste Auslenkung in beide Richtungen
   und leitet Weg und Richtung daraus ab. Kein "Umkehren"-Flag mehr noetig.

3. Webserver. Die Oberflaeche liegt als statische index.html im Flash und
   wird gechunkt gesendet (der Browser cacht sie). Alle Aktionen laufen ueber
   kleine JSON-Endpunkte statt ueber 302-Redirects mit komplettem Seitenneubau.

4. HX711 blockiert nicht mehr. Gelesen wird nur, wenn der DT-Pin Bereitschaft
   meldet, sonst kommt der letzte Wert zurueck. Die Hauptschleife laeuft damit
   unabhaengig von der HX711-Datenrate weiter.

5. HID laeuft auch bei aktivem WLAN weiter (in v8 waren die Pedale im
   WLAN-Modus tot). Abschaltbar ueber HID_IM_WLAN = False.

Dateien auf CIRCUITPY
---------------------
  code.py            diese Datei
  index.html         die Weboberflaeche
  settings.py        deine Konfiguration
  calibration.json   wird automatisch angelegt/migriert
  lib/adafruit_debouncer.mpy
  lib/adafruit_ticks.mpy
  lib/adafruit_hx711/        (nur bei BREMSE_TYP = "hx711")

Optionale Eintraege in settings.py (alle mit sinnvollen Defaults)
-----------------------------------------------------------------
  GAS_PIN            = "GP26"
  BREMSE_PIN         = "GP27"
  KUPPLUNG_PIN       = "GP28"
  DEADZONE_PCT       = 1.5    Totzone am Pedalanfang gegen Sensorrauschen
  SWEEP_MARGIN_PCT   = 2.0    Weg wird um diesen Anteil verkuerzt, damit
                              100 % sicher erreicht wird
  HX711_MAX_DEFAULT  = 50000  Startwert fuer die Waegezelle
  HID_IM_WLAN        = True
"""

import board, time, analogio, digitalio, usb_hid, json, wifi, socketpool, gc, os
from adafruit_debouncer import Debouncer
import settings

# --- Konstanten --------------------------------------------------------------

CALIBRATION_FILE = "/calibration.json"
INDEX_FILE       = "/index.html"

ADC_SPAN      = 65536          # Wertebereich des ADC, entspricht 360 Grad
HALF_SPAN     = ADC_SPAN // 2
DEBOUNCE_MS   = 0.05
DEFAULT_CURVE = [[0, 0], [25, 25], [50, 50], [75, 75], [100, 100]]
BREMSE_IDX    = 1

CAL_IDLE  = "idle"
CAL_ZERO  = "zero"
CAL_SWEEP = "sweep"
CAL_DONE  = "done"

# Ein Sweep unter diesem Weg gilt als Fehlbedienung (Pedal nicht bewegt).
MIN_SPAN_ADC = 300
MIN_SPAN_HX  = 1000

# Aufloesung der Sweep-Abdeckungskarte: 256 Felder zu je 1,4 Grad.
SWEEP_FELDER = 256
SWEEP_SHIFT  = 8                       # 65536 >> 8 = 256
SWEEP_BREITE = ADC_SPAN // SWEEP_FELDER

# Groesster Sprung zwischen zwei Messungen, der noch als durchgehende Bewegung
# aufgefuellt wird: 64 Felder = 90 Grad. Ein echter Messfehler durch eine zu
# lange Pause zeigt sich immer als scheinbarer Sprung von mehr als
# (360 Grad minus Pedalweg), bei 210 Grad Weg also mehr als 150 Grad.
# 90 Grad liegt sicher darunter und laesst trotzdem sehr schnelle Bewegungen zu.
SWEEP_FUELL_MAX = 64

DEADZONE     = getattr(settings, "DEADZONE_PCT", 1.5) / 100.0
SWEEP_MARGIN = getattr(settings, "SWEEP_MARGIN_PCT", 2.0) / 100.0
HX_MAX_DEF   = getattr(settings, "HX711_MAX_DEFAULT", 50000)
HID_IM_WLAN  = getattr(settings, "HID_IM_WLAN", True)

_PINS = getattr(settings, "ADC_PINS", ["GP26", "GP27", "GP28"])
GAS_PIN      = _PINS[0]
BREMSE_PIN   = _PINS[1]
KUPPLUNG_PIN = _PINS[2]

BREMSE_TYP = getattr(settings, "BREMSE_TYP", "adc")

# --- Hardware ----------------------------------------------------------------

adc_gas      = analogio.AnalogIn(getattr(board, GAS_PIN))
adc_kupplung = analogio.AnalogIn(getattr(board, KUPPLUNG_PIN))
adc_bremse   = None            # v8-Bug: wurde nie angelegt, aber gelesen

hx711      = None
hx_channel = None
hx_data    = None
hx_sm      = None
hx_buf     = None
hx_tare    = 0
hx_last    = 0
hx_modus   = "-"
hx_count   = 0            # Wandlungen seit der letzten Sekunde
hx_rate    = 0            # zuletzt gemessene Wandlungen pro Sekunde
hx_rate_t  = 0.0

# PIO-Programm fuer den HX711.
#
# Die PIO-Einheit des RP2040 gibt die 25 Taktimpulse in Hardware aus und legt
# die 24 Bit fertig in eine FIFO. Statt 13,8 ms Bit-Banging in Python kostet
# eine Lesung damit rund 225 Mikrosekunden, und die Hauptschleife blockiert
# dabei ueberhaupt nicht.
#
#   wait 0 pin 0   DOUT wird low, sobald eine Wandlung fertig ist
#   24x            SCK high, Bit einlesen, SCK low
#   1x             25. Impuls, waehlt Kanal A mit Gain 128 fuer die naechste
#                  Wandlung (das schreibt das Datenblatt so vor)
#   push           Wort in die FIFO
#
# Wichtig: SCK ist an jeder Stelle, an der das Programm warten kann (wait und
# push), auf low gesetzt. Bleibt SCK laenger als 60 Mikrosekunden high, schaltet
# sich der HX711 naemlich ab.
HX711_PIO_QUELLE = """
.program hx711
.side_set 1
    wait 0 pin 0        side 0
    set  x, 23          side 0
bitloop:
    nop                 side 1 [3]
    in   pins, 1        side 1
    jmp  x-- bitloop    side 0 [3]
    nop                 side 1 [3]
    nop                 side 0 [3]
    push                side 0
"""

if BREMSE_TYP == "hx711":
    hx_modus = getattr(settings, "HX711_MODE", "pio")

    if hx_modus == "pio":
        try:
            import rp2pio
            import adafruit_pioasm
            from array import array

            hx_sm = rp2pio.StateMachine(
                adafruit_pioasm.assemble(HX711_PIO_QUELLE),
                frequency=1_000_000,          # 1 Zyklus = 1 us, SCK ca. 111 kHz
                first_in_pin=getattr(board, settings.HX711_DT),
                in_pin_count=1,
                first_sideset_pin=getattr(board, settings.HX711_SCK),
                sideset_pin_count=1,
                initial_sideset_pin_state=0,
                initial_sideset_pin_direction=1,
                auto_push=False,
                in_shift_right=False,         # MSB zuerst, so liefert der HX711
            )
            hx_buf = array("I", [0] * 8)
        except Exception as e:
            print("PIO nicht moeglich, weiter mit Bit-Banging:", e)
            if hx_sm is not None:
                try:
                    hx_sm.deinit()
                except Exception:
                    pass
                hx_sm = None
            hx_modus = "bitbang"

    if hx_modus == "pio":

        def hx_poll():
            """Nicht blockierend: holt alles, was die FIFO hergibt."""
            global hx_last, hx_count
            n = hx_sm.in_waiting
            if n:
                hx_count += n
                if n > len(hx_buf):
                    n = len(hx_buf)
                hx_sm.readinto(hx_buf, end=n)     # blockiert nicht, n ist da
                v = hx_buf[n - 1] & 0xFFFFFF
                if v & 0x800000:                  # 24-Bit Zweierkomplement
                    v -= 0x1000000
                hx_last = v
            return hx_last

        def hx_roh():
            """Blockierend: wartet auf einen frischen Wert."""
            ende = time.monotonic() + 0.5
            while time.monotonic() < ende:
                if hx_sm.in_waiting:
                    return hx_poll()
            return hx_last

    else:
        from adafruit_hx711.hx711 import HX711
        from adafruit_hx711.analog_in import AnalogIn as HX_AnalogIn

        hx_data = digitalio.DigitalInOut(getattr(board, settings.HX711_DT))
        hx_data.direction = digitalio.Direction.INPUT
        hx_clk = digitalio.DigitalInOut(getattr(board, settings.HX711_SCK))
        hx_clk.direction = digitalio.Direction.OUTPUT

        hx711      = HX711(hx_data, hx_clk)
        hx_channel = HX_AnalogIn(hx711, HX711.CHAN_A_GAIN_128)

        def hx_roh():
            """Blockierend: wartet auf den naechsten Wandlungswert."""
            v = hx_channel.value
            if v & 0x80000000:                   # 24-Bit Zweierkomplement
                v = v - 0x80000000 - 0x80000000
            return v

        def hx_poll():
            """Nicht blockierend: liest nur, wenn DT Bereitschaft meldet."""
            global hx_last, hx_count
            if not hx_data.value:                # DT low = Daten bereit
                try:
                    hx_last = hx_roh()
                    hx_count += 1
                except Exception:
                    pass
            return hx_last

    time.sleep(0.5)
    for _ in range(5):
        hx_tare = hx_roh()
        time.sleep(0.2)
    hx_last = hx_tare
    print("HX711 bereit (" + hx_modus + "), Nullpunkt:", hx_tare)
else:
    adc_bremse = analogio.AnalogIn(getattr(board, BREMSE_PIN))

    def hx_roh():
        return 0

    def hx_poll():
        return 0

# --- Achsen lesen ------------------------------------------------------------

def achse_raw(idx):
    """Ein einzelner Rohwert. Bei der Waegezelle bereits tariert und >= 0."""
    if idx == 0:
        return adc_gas.value
    if idx == 2:
        return adc_kupplung.value
    if BREMSE_TYP == "hx711":
        v = hx_poll() - hx_tare
        return v if v > 0 else 0
    return adc_bremse.value

def achse_lesen(idx, n=4):
    """Gemittelter Wert. Fuer die Waegezelle ohne Mittelung, die ist langsam.

    Wichtig: bei einer Kreisgroesse darf man Rohwerte nicht einfach mitteln.
    Liegen die Samples um den Nulldurchgang herum (65500 und 30), waere das
    Mittel 32765 - also genau gegenueber. Deshalb wird um das erste Sample
    herum entfaltet, gemittelt und wieder in den Bereich zurueckgeklappt.
    """
    if idx == 1 and BREMSE_TYP == "hx711":
        return achse_raw(1)
    basis = achse_raw(idx)
    summe = 0
    for _ in range(n - 1):
        d = (achse_raw(idx) - basis) % ADC_SPAN
        if d > HALF_SPAN:
            d -= ADC_SPAN
        summe += d
    return (basis + summe // n) % ADC_SPAN

# --- Taster und LED ----------------------------------------------------------

def make_button(pin_name):
    p = digitalio.DigitalInOut(getattr(board, pin_name))
    p.direction = digitalio.Direction.INPUT
    p.pull = digitalio.Pull.UP
    return Debouncer(p, interval=DEBOUNCE_MS)

wifi_btn = make_button(settings.WIFI_BTN_PIN)

led = digitalio.DigitalInOut(getattr(board, settings.LED_PIN))
led.direction = digitalio.Direction.OUTPUT
led.value = False

def led_blink(n, an=100, aus=100):
    for _ in range(n):
        led.value = True
        time.sleep(an / 1000)
        led.value = False
        time.sleep(aus / 1000)

# --- HID ---------------------------------------------------------------------

gamepad_device = None
for device in usb_hid.devices:
    if device.usage == 0x04 and device.usage_page == 0x01:   # Joystick, siehe boot.py
        gamepad_device = device
        break

_report      = bytearray(5)
_last_report = bytearray(5)

def gamepad_senden(x, y, z, buttons=0):
    if not gamepad_device:
        return
    b = buttons & 0xFFFF
    _report[0] = b & 0xFF
    _report[1] = (b >> 8) & 0xFF
    for i, v in enumerate((x, y, z)):
        v = -127 if v < -127 else (127 if v > 127 else v)
        _report[2 + i] = v if v >= 0 else 256 + v
    if _report == _last_report:          # unveraenderte Reports sparen wir uns
        return
    _last_report[:] = _report
    try:
        gamepad_device.send_report(_report, 4)
    except OSError:
        pass

# --- Kalibrierung: Datenmodell ----------------------------------------------
#
# Pro Achse wird gespeichert:
#   typ    "adc"   Kreisgroesse 0..65535, entspricht 0..360 Grad
#          "hx711" lineare Groesse, 0 = kein Druck
#   start  Rohwert bei losgelassenem Pedal (bei hx711 immer 0)
#   span   Weg in Rohwerten, VORZEICHENBEHAFTET.
#          span > 0  Rohwert steigt beim Treten
#          span < 0  Rohwert faellt beim Treten
#   curve  Stuetzpunkte der Kennlinie in Prozent

def cal_default(idx):
    if idx == BREMSE_IDX and BREMSE_TYP == "hx711":
        return {"typ": "hx711", "start": 0, "span": HX_MAX_DEF,
                "curve": [list(p) for p in DEFAULT_CURVE]}
    return {"typ": "adc", "start": 0, "span": ADC_SPAN - 1,
            "curve": [list(p) for p in DEFAULT_CURVE]}

def cal_defaults():
    return [cal_default(i) for i in range(3)]

def cal_migrieren(d, idx):
    """Alten v8-Datensatz (min/max/invert) in start/span umrechnen."""
    if "span" in d and "start" in d:
        return d
    mn = int(d.get("min", 0))
    mx = int(d.get("max", ADC_SPAN - 1))
    if mx < mn:
        mn, mx = mx, mn
    weite = mx - mn
    if weite <= 0:
        return cal_default(idx)
    if d.get("invert", False):
        start, span = mx, -weite
    else:
        start, span = mn, weite
    return {"typ": d.get("typ", "adc"), "start": start, "span": span,
            "curve": d.get("curve", [list(p) for p in DEFAULT_CURVE])}

def cal_laden():
    try:
        with open(CALIBRATION_FILE, "r") as f:
            daten = json.load(f)
        if isinstance(daten, list) and len(daten) == 3:
            out = []
            for i, d in enumerate(daten):
                d = cal_migrieren(d, i)
                d.setdefault("curve", [list(p) for p in DEFAULT_CURVE])
                # Typ folgt immer der Hardware, falls umgebaut wurde
                d["typ"] = BREMSE_TYP if i == BREMSE_IDX else "adc"
                if d["typ"] == "hx711":
                    d["start"] = 0
                    if d["span"] <= 0:
                        d["span"] = HX_MAX_DEF
                out.append(d)
            print("Kalibrierung geladen")
            return out
    except (OSError, ValueError, KeyError) as e:
        print("Kalibrierung nicht lesbar:", e)
    print("Defaults")
    return cal_defaults()

def cal_speichern(cal):
    try:
        with open(CALIBRATION_FILE, "w") as f:
            json.dump(cal, f)
        print("Gespeichert")
        return True
    except OSError as e:
        # Tritt auf, wenn boot.py das Dateisystem nicht beschreibbar gemountet hat
        print("Speichern fehlgeschlagen:", e)
        return False

# --- Kalibrierung: Umrechnung ------------------------------------------------

def kurve_anwenden(x, punkte):
    x = 0 if x < 0 else (100 if x > 100 else x)
    if not punkte or len(punkte) < 2:
        return x
    if x <= punkte[0][0]:
        return punkte[0][1]
    if x >= punkte[-1][0]:
        return punkte[-1][1]
    for i in range(len(punkte) - 1):
        x0, y0 = punkte[i]
        x1, y1 = punkte[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0) if x1 != x0 else 0
            return y0 + t * (y1 - y0)
    return x

def raw_to_norm(raw, c):
    """Rohwert -> 0.0 .. 1.0, wraparound-fest.

    Der genutzte Bogen laeuft von start ueber span. Alles ausserhalb liegt im
    ungenutzten Rest des Kreises. Dort entscheidet die kuerzere Distanz:
    naeher am Startpunkt -> Pedal losgelassen (0.0), naeher am Endpunkt ->
    Pedal durchgetreten (1.0). So kippt ein zitternder Sensor an der 0-Grad-
    Grenze nicht mehr von 0 auf 100 Prozent.
    """
    span = c["span"]
    if span == 0:
        return 0.0

    if c.get("typ") == "hx711":
        n = raw / span if span > 0 else 0.0
    else:
        start = c["start"]
        if span > 0:
            d = (raw - start) % ADC_SPAN
            s = span
        else:
            d = (start - raw) % ADC_SPAN
            s = -span
        if d <= s:
            n = d / s
        elif (ADC_SPAN - d) <= (d - s):
            return 0.0                     # knapp vor dem Nullpunkt
        else:
            n = 1.0                        # jenseits des Endpunkts

    if n <= DEADZONE:
        return 0.0
    if n >= 1.0:
        return 1.0
    return (n - DEADZONE) / (1.0 - DEADZONE)

def norm_to_axis(n):
    return int(n * 254) - 127

def raw_to_axis(raw, c):
    return norm_to_axis(raw_to_norm(raw, c))

def pct_out(raw, c):
    return int(raw_to_norm(raw, c) * 100)

def pct_in(raw, c):
    """Prozent vor der Kennlinie - fuer die Anzeige im Kurveneditor."""
    return int(raw_to_norm(raw, c) * 100)

def pct_kurve(raw, c):
    """Prozent nach der Kennlinie."""
    return int(kurve_anwenden(raw_to_norm(raw, c) * 100,
                              c.get("curve", DEFAULT_CURVE)))

def achse_wert(raw, c):
    """Endgueltiger HID-Wert inklusive Kennlinie."""
    p = kurve_anwenden(raw_to_norm(raw, c) * 100, c.get("curve", DEFAULT_CURVE))
    p = 0.0 if p < 0 else (100.0 if p > 100 else p)
    return int(p / 100 * 254) - 127

# --- Zustand -----------------------------------------------------------------

cal               = cal_laden()
cal_zustand       = CAL_IDLE
aktive_achse      = None
cal_meldung       = ""
sweep_zero        = 0     # Rohwert am Nullpunkt
sweep_hx          = 0     # groesster Rohwert (nur Waegezelle)
sweep_feld        = 0     # zuletzt markiertes Feld
sweep_cover       = bytearray(SWEEP_FELDER)   # besuchte Winkelfelder
wlan_aktiv        = False
sock              = None
pool              = None
wlan_stoppen_flag = False
led_timer         = 0.0
led_state         = False

# --- Sweep -------------------------------------------------------------------

def sweep_start():
    """Nullpunkt setzen und Wegmessung zuruecksetzen."""
    global sweep_zero, sweep_hx, sweep_feld, hx_tare, cal_zustand
    idx = aktive_achse
    if idx == BREMSE_IDX and BREMSE_TYP == "hx711":
        time.sleep(0.2)
        hx_tare = hx_poll()
        sweep_zero = 0
    else:
        sweep_zero = achse_lesen(idx, 16)
    sweep_hx = 0
    for i in range(SWEEP_FELDER):
        sweep_cover[i] = 0
    sweep_feld = sweep_zero >> SWEEP_SHIFT
    sweep_cover[sweep_feld] = 1
    cal_zustand = CAL_SWEEP
    print("Sweep gestartet, Null =", sweep_zero)

def sweep_update():
    """Besuchte Winkelfelder markieren. Wird moeglichst oft aufgerufen.

    Statt Schritte aufzusummieren wird angekreuzt, WO das Pedal ueberall war -
    der Kreis ist dafuer in 256 Felder zu je 1,4 Grad geteilt.

    Zwischen zwei Messungen liegen mehrere Felder, denn die Hauptschleife
    schafft keine 1000 Messungen pro Sekunde. Deshalb wird die Strecke seit
    der letzten Messung mitmarkiert - sonst blieben Loecher, und der
    zusammenhaengende Bogen waere nur ein paar Grad lang.

    Ist der Sprung groesser als SWEEP_FUELL_MAX, war die Pause zu lang, um die
    Richtung sicher zu kennen. Dann wird nur der Endpunkt markiert. Anders als
    ein aufsummierender Zaehler schleppt die Karte so einen Fehler nicht mit:
    es bleibt hoechstens ein Loch, das der naechste Durchtritt wieder fuellt.
    """
    global sweep_hx, sweep_feld
    idx = aktive_achse
    if idx is None:
        return
    raw = achse_raw(idx)
    if idx == BREMSE_IDX and BREMSE_TYP == "hx711":
        if raw > sweep_hx:
            sweep_hx = raw
        return

    feld = raw >> SWEEP_SHIFT
    d    = (feld - sweep_feld) % SWEEP_FELDER
    if d == 0:
        return
    if d <= SWEEP_FUELL_MAX:                   # aufwaerts, Strecke fuellen
        i = sweep_feld
        for _ in range(d):
            i = (i + 1) % SWEEP_FELDER
            sweep_cover[i] = 1
    elif SWEEP_FELDER - d <= SWEEP_FUELL_MAX:  # abwaerts, Strecke fuellen
        i = sweep_feld
        for _ in range(SWEEP_FELDER - d):
            i = (i - 1) % SWEEP_FELDER
            sweep_cover[i] = 1
    else:                                      # zu grosser Sprung
        sweep_cover[feld] = 1
    sweep_feld = feld

def sweep_wege():
    """Laengster zusammenhaengender Bogen ab dem Nullpunkt, je Richtung.

    Rueckgabe in Rohzaehlern: (aufwaerts, abwaerts).
    """
    null = sweep_zero >> SWEEP_SHIFT
    vor = 0
    i = null
    while vor < SWEEP_FELDER - 1:
        i = (i + 1) % SWEEP_FELDER
        if not sweep_cover[i]:
            break
        vor += 1
    rueck = 0
    i = null
    while rueck < SWEEP_FELDER - 1:
        i = (i - 1) % SWEEP_FELDER
        if not sweep_cover[i]:
            break
        rueck += 1
    return vor * SWEEP_BREITE, rueck * SWEEP_BREITE

def sweep_finish():
    """Richtung und Weg aus der Abdeckungskarte ableiten und speichern."""
    global cal_zustand, aktive_achse, cal_meldung
    idx = aktive_achse
    ist_hx = (idx == BREMSE_IDX and BREMSE_TYP == "hx711")

    if ist_hx:
        weg, vorwaerts = sweep_hx, True
    else:
        auf, ab = sweep_wege()
        if auf >= ab:
            weg, vorwaerts = auf, True
        else:
            weg, vorwaerts = ab, False

    minimum = MIN_SPAN_HX if ist_hx else MIN_SPAN_ADC
    if weg < minimum:
        cal_meldung = "Zu wenig Bewegung erkannt - Pedal voll durchtreten"
        return False

    # Etwas Reserve, damit das Pedal am Anschlag sicher 100 Prozent erreicht
    weg = int(weg * (1.0 - SWEEP_MARGIN))
    if weg < 1:
        weg = 1

    neu = {
        "typ":   "hx711" if ist_hx else "adc",
        "start": 0 if ist_hx else sweep_zero,
        "span":  weg if vorwaerts else -weg,
        "curve": cal[idx].get("curve", [list(p) for p in DEFAULT_CURVE]),
    }
    cal[idx] = neu
    gespeichert = cal_speichern(cal)
    cal_zustand  = CAL_DONE
    cal_meldung  = "{}: Weg {} {}".format(
        settings.ACHS_NAMEN[idx], abs(neu["span"]),
        "aufwaerts" if neu["span"] > 0 else "abwaerts")
    if not gespeichert:
        cal_meldung += " (nur im RAM, Dateisystem schreibgeschuetzt)"
    aktive_achse = None
    print(cal_meldung)
    return True

# --- HTTP --------------------------------------------------------------------

def _send_all(conn, data):
    """Senden auf einem nicht blockierenden Socket, Sweep laeuft nebenher."""
    mv   = memoryview(data)
    ende = time.monotonic() + 5.0
    while len(mv):
        try:
            n = conn.send(mv)
        except OSError:
            n = 0                           # Sendepuffer voll, gleich nochmal
        if n:
            mv = mv[n:]
        elif time.monotonic() > ende:
            break                           # Gegenstelle weg
        elif cal_zustand == CAL_SWEEP:
            sweep_update()

def http_send(conn, status, ctype, body, cache=None):
    if isinstance(body, str):
        body = body.encode()
    h = ["HTTP/1.1 " + status,
         "Content-Type: " + ctype,
         "Content-Length: " + str(len(body)),
         "Connection: close"]
    if cache:
        h.append("Cache-Control: " + cache)
    _send_all(conn, ("\r\n".join(h) + "\r\n\r\n").encode())
    _send_all(conn, body)

def http_json(conn, obj):
    http_send(conn, "200 OK", "application/json", json.dumps(obj),
              "no-store")

def http_datei(conn, pfad, ctype, cache="max-age=86400"):
    """Datei gechunkt aus dem Flash senden - spart RAM und ist schneller."""
    try:
        groesse = os.stat(pfad)[6]
    except OSError:
        http_send(conn, "404 Not Found", "text/plain", "not found")
        return
    kopf = ("HTTP/1.1 200 OK\r\n"
            "Content-Type: " + ctype + "\r\n"
            "Content-Length: " + str(groesse) + "\r\n"
            "Cache-Control: " + cache + "\r\n"
            "Connection: close\r\n\r\n")
    _send_all(conn, kopf.encode())
    buf = bytearray(1024)
    with open(pfad, "rb") as f:
        while True:
            n = f.readinto(buf)
            if not n:
                break
            _send_all(conn, memoryview(buf)[:n])

def _recv_warten(conn, buf, frist):
    """Nicht blockierend auf Daten warten und dabei den Sweep weiter abtasten.

    Browser oeffnen gern Verbindungen auf Vorrat und schicken erst spaeter
    (oder nie) etwas. Ein blockierendes recv wuerde die Hauptschleife so lange
    anhalten - und genau in dieser Pause verliert die Sweep-Messung den
    Anschluss ans Pedal. Deshalb wird hier gepollt statt gewartet.
    """
    ende = time.monotonic() + frist
    while time.monotonic() < ende:
        try:
            n = conn.recv_into(buf)
            if n:
                return n
        except OSError:
            pass                            # noch nichts da
        if cal_zustand == CAL_SWEEP:
            sweep_update()
    return 0

def request_lesen(conn):
    buf = bytearray(1024)
    n = _recv_warten(conn, buf, 1.0)
    if not n:
        return "", ""
    text = bytes(buf[:n]).decode("utf-8", "ignore")
    kopf, _, body = text.partition("\r\n\r\n")

    laenge = 0
    for zeile in kopf.split("\r\n"):
        if zeile[:15].lower() == "content-length:":
            try:
                laenge = int(zeile.split(":", 1)[1])
            except ValueError:
                laenge = 0
            break
    while len(body) < laenge:
        n = _recv_warten(conn, buf, 0.5)
        if not n:
            break
        body += bytes(buf[:n]).decode("utf-8", "ignore")
    return kopf, body

def pfad_holen(kopf):
    try:
        return kopf.split("\r\n")[0].split(" ")[1]
    except IndexError:
        return "/"

def query_param(pfad, key):
    if "?" not in pfad:
        return None
    for p in pfad.split("?", 1)[1].split("&"):
        if "=" in p:
            k, v = p.split("=", 1)
            if k == key:
                return v
    return None

# --- Request-Verarbeitung ----------------------------------------------------

def zustand_json():
    roh = [achse_lesen(i) for i in range(3)]
    return {
        "r":  roh,
        "i":  [pct_in(roh[i], cal[i]) for i in range(3)],
        "o":  [pct_kurve(roh[i], cal[i]) for i in range(3)],
        "c":  [[cal[i]["start"], cal[i]["span"]] for i in range(3)],
        "st": cal_zustand,
        "ax": aktive_achse,
        "sw": ([sweep_hx, 0] if (aktive_achse == BREMSE_IDX
                                 and BREMSE_TYP == "hx711")
               else list(sweep_wege())) if cal_zustand == CAL_SWEEP else [0, 0],
        "m":  cal_meldung,
        "fs": cal_schreibbar,
        "hz": hx_rate,
    }

def handle(conn):
    global cal_zustand, aktive_achse, cal_meldung
    global wlan_stoppen_flag, hx_tare

    kopf, body = request_lesen(conn)
    if not kopf:
        return
    pfad = pfad_holen(kopf)

    if pfad == "/" or pfad.startswith("/?") or pfad == "/index.html":
        http_datei(conn, INDEX_FILE, "text/html; charset=utf-8", "max-age=3600")

    elif pfad == "/init":
        http_json(conn, {
            "n":  list(settings.ACHS_NAMEN),
            "cv": [c.get("curve", [list(p) for p in DEFAULT_CURVE]) for c in cal],
            "t":  [c.get("typ", "adc") for c in cal],
        })

    elif pfad == "/data":
        http_json(conn, zustand_json())

    elif pfad.startswith("/cal_start"):
        a = query_param(pfad, "achse")
        if a in ("0", "1", "2"):
            aktive_achse = int(a)
            cal_zustand  = CAL_ZERO
            cal_meldung  = ""
        http_json(conn, zustand_json())

    elif pfad == "/cal_zero":
        if aktive_achse is not None and cal_zustand == CAL_ZERO:
            sweep_start()
        http_json(conn, zustand_json())

    elif pfad == "/cal_finish":
        if aktive_achse is not None and cal_zustand == CAL_SWEEP:
            sweep_finish()
        http_json(conn, zustand_json())

    elif pfad == "/cal_abort":
        aktive_achse = None
        cal_zustand  = CAL_IDLE
        cal_meldung  = ""
        http_json(conn, zustand_json())

    elif pfad.startswith("/cal_reset"):
        a = query_param(pfad, "achse")
        if a in ("0", "1", "2"):
            i = int(a)
            kurve = cal[i].get("curve")
            cal[i] = cal_default(i)
            if kurve:
                cal[i]["curve"] = kurve
            cal_speichern(cal)
            cal_meldung = settings.ACHS_NAMEN[i] + " zurueckgesetzt"
        http_json(conn, zustand_json())

    elif pfad == "/cal_flip":
        # Richtung umkehren, ohne neu zu kalibrieren:
        # Endpunkt wird zum neuen Startpunkt, Vorzeichen dreht sich.
        a = query_param(pfad, "achse")
        if a in ("0", "1", "2"):
            i = int(a)
            c = cal[i]
            if c.get("typ") != "hx711" and c["span"]:
                c["start"] = (c["start"] + c["span"]) % ADC_SPAN
                c["span"]  = -c["span"]
                cal_speichern(cal)
        http_json(conn, zustand_json())

    elif pfad == "/tare":
        if BREMSE_TYP == "hx711":
            time.sleep(0.2)
            hx_tare = hx_poll()
            cal_meldung = "Waegezelle tariert: " + str(hx_tare)
        http_json(conn, zustand_json())

    elif pfad == "/kurve":
        try:
            d = json.loads(body)
            i = int(d["achse"])
            k = d["curve"]
            if 0 <= i <= 2 and isinstance(k, list) and len(k) >= 2:
                cal[i]["curve"] = k
                http_json(conn, {"ok": cal_speichern(cal)})
            else:
                http_json(conn, {"ok": False})
        except (ValueError, KeyError, TypeError) as e:
            print("Kurve fehlerhaft:", e)
            http_json(conn, {"ok": False})

    elif pfad == "/wlan_aus":
        http_json(conn, {"ok": True})
        wlan_stoppen_flag = True

    elif pfad == "/favicon.ico":
        _send_all(conn, b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n"
                        b"Connection: close\r\n\r\n")

    else:
        http_send(conn, "404 Not Found", "text/plain", "404")

# --- Start -------------------------------------------------------------------

# Einmal pruefen, ob das Dateisystem beschreibbar ist. Das haengt an boot.py:
# ohne storage.remount("/", readonly=False) kann der Pico nichts speichern.
try:
    with open(CALIBRATION_FILE, "a"):
        pass
    cal_schreibbar = True
except OSError:
    cal_schreibbar = False
    print("Achtung: Dateisystem schreibgeschuetzt, Kalibrierung nur im RAM")

led_blink(3, an=150, aus=150)
print("Pico W Pedale v9.6 bereit - Bremse:", BREMSE_TYP, hx_modus,
      "- HID:", "ja" if gamepad_device else "NEIN")
time.sleep(1.0)

# --- Hauptschleife -----------------------------------------------------------

while True:
    now = time.monotonic()
    wifi_btn.update()

    if BREMSE_TYP == "hx711" and now - hx_rate_t >= 1.0:
        hx_rate   = hx_count       # tatsaechlich erreichte Wandlungen pro Sekunde
        hx_count  = 0
        hx_rate_t = now

    if wifi_btn.fell:
        if not wlan_aktiv:
            print("Starte AP ...")
            wifi.radio.start_ap(
                ssid=settings.AP_SSID,
                password=settings.AP_PASSWORD if settings.AP_PASSWORD else None,
                channel=settings.AP_CHANNEL,
            )
            pool = socketpool.SocketPool(wifi.radio)
            sock = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
            sock.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", settings.WEB_PORT))
            sock.listen(4)          # v8 hatte 1 - Browser oeffnen mehrere
            sock.setblocking(False)
            wlan_aktiv = True
            led_blink(2, an=100, aus=100)
            print("Webserver: http://192.168.4.1")
        else:
            wlan_stoppen_flag = True

    if wlan_aktiv:
        # Beim Sweep schneller blinken - sichtbares Feedback am Pedal
        takt = 0.08 if cal_zustand == CAL_SWEEP else 0.25
        if now - led_timer > takt:
            led_state = not led_state
            led.value = led_state
            led_timer = now

        if cal_zustand == CAL_SWEEP:
            sweep_update()

        conn = None
        try:
            conn, addr = sock.accept()
        except OSError:
            pass

        if conn:
            conn.setblocking(False)   # blockiert sonst die Sweep-Abtastung
            try:
                handle(conn)
            except Exception as e:
                print("Request-Fehler:", e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            gc.collect()

        if wlan_stoppen_flag:
            cal_speichern(cal)
            try:
                sock.close()
                wifi.radio.stop_ap()
            except Exception:
                pass
            sock              = None
            wlan_aktiv        = False
            wlan_stoppen_flag = False
            cal_zustand       = CAL_IDLE
            aktive_achse      = None
            cal_meldung       = ""
            led.value         = False
            led_blink(3, an=150, aus=150)
            print("HID Modus")
    else:
        led.value = False

    if cal_zustand == CAL_SWEEP:
        # Waehrend der Wegmessung nichts anderes tun - jede eingesparte
        # Rechnung erhoeht die Abtastrate und damit die Aufloesung der Karte.
        # Ausserdem gelangen so keine Zufallswerte ins Spiel.
        sweep_update()
    elif not wlan_aktiv or HID_IM_WLAN:
        gamepad_senden(achse_wert(achse_raw(0), cal[0]),
                       achse_wert(achse_raw(1), cal[1]),
                       achse_wert(achse_raw(2), cal[2]))
        if not wlan_aktiv:
            time.sleep(0.001)
