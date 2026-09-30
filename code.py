"""
Pico W Pedale Controller v9.7 - Wraparound-Kalibrierung + schneller Webserver
=============================================================================
v9.7: Rumble. Zwei Vibrationsmotoren an je einem DRV8871, angesteuert im
      slow-decay-Verfahren (IN1 fest an, invertierte PWM auf IN2). Am realen
      Aufbau gemessen sinkt die Abfallschwelle dadurch von 60 auf 6 Prozent -
      Faktor zehn mehr Regelbereich als mit der naheliegenden Variante.
      Die Effekte rechnet der Pico NICHT selbst aus: SimHubs ShakeIt-Motoren
      koennen ihren Ausgangswert als Property exportieren, und die geht ueber
      den seriellen Kanal hierher. Die Effektbibliothek dort ist besser als
      alles, was in diese Firmware passen wuerde.
      Dazu ein gleitender Mittelwert auf der Waegezelle: ein Motor am Bremspad
      erzeugt im Kraftfluss eine echte Wechselkraft, die sich bei 50 Hz Motor
      und 80 Hz Abtastrate als 30-Hz-Zappeln in den Bremswert faltet.

v9.6: Die HID-Achsen haben 16 statt 8 bit. Vorher gingen 255 Stufen ans
      Spiel, obwohl der AS5600 ueber einen typischen Pedalweg rund 1200 bis
      2400 unterscheidbare Werte liefert und die Waegezelle noch mehr - der
      Descriptor war die Engstelle, nicht die Mechanik. Spuerbar wird das vor
      allem, wenn ein Spiel eine eigene Kennlinie darueberlegt: die spreizt
      den unteren Bereich und damit auch die Quantisierungsstufen.
      Dazu wird im Ausgabepfad ueber HID_MITTEL Messungen gemittelt, sonst
      traegt ein Teil der neuen Bits nur ADC-Rauschen.
      ACHTUNG: geaenderter Descriptor und eigene USB-PID - Windows sieht ein
      neues Geraet, alle Achszuweisungen im Spiel muessen einmal neu gesetzt
      werden.

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
import pwmio
from adafruit_debouncer import Debouncer
import settings

# --- Konstanten --------------------------------------------------------------

CALIBRATION_FILE = "/calibration.json"
INDEX_FILE       = "/index.html"

ADC_SPAN      = 65536          # Wertebereich des ADC, entspricht 360 Grad
HALF_SPAN     = ADC_SPAN // 2
DEBOUNCE_MS   = 0.05

# Groesster Wert einer HID-Achse. Muss zum Descriptor in boot.py passen:
# 16 bit unsigned, Logical Maximum 65535.
AXIS_MAX      = 65535

# Wieviele ADC-Messungen fuer einen HID-Wert gemittelt werden. Mit 8-bit-Achsen
# war das egal - eine Stufe war so grob, dass Rauschen darin verschwand. Bei
# 16 bit sieht man es, also mitteln wir. Vier Messungen halbieren das Rauschen
# und kosten keine spuerbare Verzoegerung, weil sie unmittelbar hintereinander
# genommen werden (kein gleitender Mittelwert, keine Traegheit).
# 1 schaltet die Mittelung ab.
HID_MITTEL    = 4
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

# Gleitender Mittelwert ueber die Waegezelle.
#
# Sitzt ein Rumble-Motor am Bremspad, erzeugt er im Kraftfluss zwischen Pad und
# Rahmen eine echte Wechselkraft - die Waegezelle misst sie zu Recht mit. Bei
# rund 50 Hz Motorfrequenz und 80 Hz Abtastrate faltet sich das als 30-Hz-
# Zappeln in den Bremswert. Gemittelt wird ueber echte Wandlungen, erkennbar an
# hx_count; ohne diese Bedingung wuerde derselbe Wert mehrfach einlaufen und
# der Filter waere wirkungslos.
HX_FILTER = getattr(settings, "HX_FILTER", 8)
if HX_FILTER < 1:
    HX_FILTER = 1

_hxf_buf   = [0] * HX_FILTER
_hxf_i     = 0
_hxf_summe = 0
_hxf_count = -1
_hxf_init  = False

def hx_glaetten(v):
    global _hxf_i, _hxf_summe, _hxf_count, _hxf_init
    if HX_FILTER <= 1:
        return v
    if not _hxf_init:
        for i in range(HX_FILTER):
            _hxf_buf[i] = v
        _hxf_summe = v * HX_FILTER
        _hxf_count = hx_count
        _hxf_init  = True
        return v
    if hx_count != _hxf_count:
        _hxf_count  = hx_count
        _hxf_summe += v - _hxf_buf[_hxf_i]
        _hxf_buf[_hxf_i] = v
        _hxf_i = (_hxf_i + 1) % HX_FILTER
    return _hxf_summe // HX_FILTER

def achse_raw(idx):
    """Ein einzelner Rohwert. Bei der Waegezelle bereits tariert und >= 0."""
    if idx == 0:
        return adc_gas.value
    if idx == 2:
        return adc_kupplung.value
    if BREMSE_TYP == "hx711":
        v = hx_glaetten(hx_poll() - hx_tare)
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
    if device.usage == 0x05 and device.usage_page == 0x01:
        gamepad_device = device
        break

_report      = bytearray(8)
_last_report = bytearray(8)

def gamepad_senden(x, y, z, buttons=0):
    """Report zusammenbauen: 2 Byte Buttons, dann 3 Achsen zu je 16 bit.

    Alles little endian, unsigned 0..65535 - passend zum Descriptor in boot.py.
    """
    if not gamepad_device:
        return
    b = buttons & 0xFFFF
    _report[0] = b & 0xFF
    _report[1] = (b >> 8) & 0xFF
    for i, v in enumerate((x, y, z)):
        v = 0 if v < 0 else (AXIS_MAX if v > AXIS_MAX else int(v))
        _report[2 + 2 * i] = v & 0xFF
        _report[3 + 2 * i] = (v >> 8) & 0xFF
    if _report == _last_report:          # unveraenderte Reports sparen wir uns
        return
    _last_report[:] = _report
    try:
        gamepad_device.send_report(_report, 4)
    except OSError:
        pass

# --- Rumble ------------------------------------------------------------------
#
# Zwei Vibrationsmotoren an je einem DRV8871. Angesteuert wird im "slow decay"-
# Verfahren: IN1 liegt fest an, IN2 bekommt die INVERTIERTE PWM. Zwischen den
# Impulsen wird die Wicklung dadurch kurzgeschlossen statt geoeffnet, der Strom
# bricht weniger ein und das Drehmoment bei kleinem Duty ist viel hoeher.
#
# Am realen Aufbau gemessen: die Abfallschwelle sinkt damit von 60 auf 6
# Prozent. Faktor zehn mehr Regelbereich, fuer zwei Zeilen Code.
#
# Voraussetzung: IN1 und IN2 eines Kanals muessen auf derselben PWM-Einheit des
# RP2040 liegen, sonst laufen die Signale auseinander. Das ist genau dann der
# Fall, wenn der erste Pin gerade ist und der zweite direkt darauf folgt -
# GP4/GP5, GP6/GP7, GP8/GP9. Die Firmware prueft das und meckert sonst.

RUMBLE_DATEI = "/rumble.json"

# Alles per getattr, damit eine aeltere settings.py den Start nicht verhindert.
RB_PINS   = getattr(settings, "RUMBLE_PINS", [])
RB_NAMEN  = getattr(settings, "RUMBLE_NAMEN", ["Kanal 1", "Kanal 2"])
RB_VERS   = getattr(settings, "RUMBLE_VERSORGUNG", 12.0)
RB_NENN   = getattr(settings, "RUMBLE_MOTOR_NENN", 12.0)
RB_HZ     = getattr(settings, "RUMBLE_PWM_HZ", 20000)
RB_KICK   = getattr(settings, "RUMBLE_KICK_MS", 50)
RB_BREMS  = getattr(settings, "RUMBLE_BREMS_MS", 80)
RB_BREMS_VERZUG = getattr(settings, "RUMBLE_BREMS_VERZUG_MS", 120)
TELE_NAMEN   = getattr(settings, "TELE_NAMEN", ["bremse", "gas"])
TELE_MAX     = getattr(settings, "TELE_MAX", 100.0) or 1.0
TELE_TIMEOUT = getattr(settings, "TELE_TIMEOUT", 2.0)

# Deckel, damit ein 12-V-Motor an einer hoeheren Versorgung im Mittel nur seine
# Nennspannung sieht. Bei gleicher Versorgung wird daraus 65535, also kein
# Deckel. Der Kickstart darf bewusst darueber gehen.
RUMBLE_DECKEL = int(AXIS_MAX * RB_NENN / RB_VERS)
if RUMBLE_DECKEL > AXIS_MAX:
    RUMBLE_DECKEL = AXIS_MAX

RUMBLE_N = len(RB_PINS)

_rb_in1 = []
_rb_in2 = []

for _p1, _p2 in RB_PINS:
    try:
        _rb_in1.append(pwmio.PWMOut(getattr(board, _p1),
                                    frequency=RB_HZ,
                                    duty_cycle=0))
        _rb_in2.append(pwmio.PWMOut(getattr(board, _p2),
                                    frequency=RB_HZ,
                                    duty_cycle=0))
        if not (int(_p1[2:]) % 2 == 0 and int(_p2[2:]) == int(_p1[2:]) + 1):
            print("Rumble: %s/%s nicht auf derselben PWM-Einheit -"
                  " der untere Regelbereich wird schlecht" % (_p1, _p2))
    except Exception as e:
        print("Rumble-Pins %s/%s nicht nutzbar: %s" % (_p1, _p2, e))
        _rb_in1.append(None)
        _rb_in2.append(None)

rumble_da = any(x is not None for x in _rb_in1)

# Sollwert 0.0 .. 1.0 je Kanal, plus Zustandsmaschine fuer Kick und Bremsen
_rb_soll   = [0.0] * RUMBLE_N
_rb_ist    = [0.0] * RUMBLE_N          # nur fuer die Anzeige
_rb_phase  = ["aus"] * RUMBLE_N        # aus | kick | lauf | brems
_rb_bis    = [0.0] * RUMBLE_N          # Ende der aktuellen Phase
_rb_test   = [None] * RUMBLE_N         # Handbetrieb aus der Weboberflaeche
_rb_test_bis = [0.0] * RUMBLE_N        # Totmannschaltung je Kanal
_rb_seq    = -1                        # hoechste gesehene Anforderungsnummer
_rb_sperre = 0.0                       # nach dem Not-Aus kurz nichts annehmen

# Ein Testwert verfaellt nach dieser Zeit, wenn ihn niemand erneuert. Die
# Weboberflaeche schickt waehrend eines Tests alle 400 ms ein Lebenszeichen.
# Bricht die Verbindung ab, schliesst der Browser oder haengt das WLAN, steht
# der Motor also nach gut einer Sekunde - und nicht erst, wenn jemand den
# Stecker zieht.
RB_TEST_TTL = 1.2

def rumble_default():
    return [{"schwelle": 4, "min": 8, "max": 100, "kick": 12, "gain": 100,
             "brems": RB_BREMS_VERZUG, "an": True}
            for _ in range(RUMBLE_N)]

def rumble_laden():
    cfg = rumble_default()
    try:
        with open(RUMBLE_DATEI) as f:
            d = json.load(f)
        for i in range(RUMBLE_N):
            if i < len(d) and isinstance(d[i], dict):
                cfg[i].update(d[i])
    except Exception:
        pass
    return cfg

def rumble_speichern():
    try:
        with open(RUMBLE_DATEI, "w") as f:
            json.dump(rumble_cfg, f)
        return True
    except Exception as e:
        print("Rumble-Einstellungen nicht speicherbar:", e)
        return False

rumble_cfg = rumble_laden()

def _rb_roh(k, duty):
    """Rohe Ansteuerung ohne Deckel. duty 0..65535."""
    if _rb_in1[k] is None:
        return
    if duty < 0:
        duty = 0
    elif duty > AXIS_MAX:
        duty = AXIS_MAX
    _rb_in1[k].duty_cycle = AXIS_MAX
    _rb_in2[k].duty_cycle = AXIS_MAX - duty

def _rb_frei(k):
    """Auslaufen lassen: beide Eingaenge aus."""
    if _rb_in1[k] is None:
        return
    _rb_in1[k].duty_cycle = 0
    _rb_in2[k].duty_cycle = 0

def _rb_bremsen(k):
    """Beide Eingaenge an: Motor kurzgeschlossen, die Unwucht steht sofort."""
    if _rb_in1[k] is None:
        return
    _rb_in1[k].duty_cycle = AXIS_MAX
    _rb_in2[k].duty_cycle = AXIS_MAX

def _rb_schwelle(c, e):
    """Schwelle anwenden und den Rest auf 0..1 spreizen.

    Ohne das fuehrt jeder Effektwert ueber null sofort zur Mindestdrehzahl -
    ein Fahrbahneffekt, der staendig bei zwei, drei Prozent rauscht, laesst den
    Motor dann die ganze Runde brummen. Kein Kontrast mehr, und der Motor
    laeuft dauernd. Mit Schwelle bleibt er unten wirklich aus.

    Uebernommen von SimHubs Motorausgang, der genau diese zwei Regler hat:
    Threshold (hier) und Minimum force (unser "min"). Die Schwelle wirkt
    zuerst, die Untergrenze danach.
    """
    schw = c.get("schwelle", 0) / 100.0
    if schw <= 0.0:
        return e
    if e <= schw:
        return 0.0
    if schw >= 1.0:
        return 1.0
    return (e - schw) / (1.0 - schw)

def _rb_duty(k, e):
    """Effektstaerke 0..1 -> Duty. Unterhalb von min passiert nichts Sinnvolles,
    deshalb wird der Bereich min..max gespreizt statt bei null anzufangen."""
    c = rumble_cfg[k]
    p = c["min"] + e * (c["max"] - c["min"])
    if p < 0:
        p = 0
    elif p > 100:
        p = 100
    return int(RUMBLE_DECKEL * p / 100)

def rumble_soll(k, e):
    """Sollwert setzen, 0.0 .. 1.0."""
    if e < 0:
        e = 0.0
    elif e > 1:
        e = 1.0
    _rb_soll[k] = e

def rumble_test_setz(k, v, seq=None):
    """Handbetrieb aus der Weboberflaeche. v in Prozent, negativ beendet ihn.

    seq ist eine aufsteigende Nummer des Browsers. Ein Schieberegler erzeugt
    viele Anforderungen kurz hintereinander; wenn der Pico nicht hinterherkommt,
    stauen sie sich und werden verspaetet abgearbeitet. Ohne Reihenfolgeschutz
    ueberschreibt dann eine alte Anforderung das spaetere "aus" - der Motor
    laeuft mit einem Wert weiter, den niemand mehr haben will. Genau das ist
    beim ersten Test passiert.
    """
    global _rb_seq
    if k < 0 or k >= RUMBLE_N:
        return
    if time.monotonic() < _rb_sperre:      # Not-Aus hat Vorrang
        return
    if seq is not None:
        if seq <= _rb_seq:
            return                          # ueberholte Anforderung, verwerfen
        _rb_seq = seq
    if v is None or v < 0:
        _rb_test[k]     = None
        _rb_test_bis[k] = 0.0
    else:
        _rb_test[k]     = min(1.0, v / 100.0)
        _rb_test_bis[k] = time.monotonic() + RB_TEST_TTL

def rumble_not_aus():
    """Alles sofort aus und fuer zwei Sekunden nichts mehr annehmen.

    Die Sperre ist wichtig: ohne sie koennte eine noch in der Warteschlange
    steckende Anforderung den Motor direkt wieder anwerfen.
    """
    global _rb_sperre
    _rb_sperre = time.monotonic() + 2.0
    rumble_alles_aus()

def rumble_alles_aus():
    for k in range(RUMBLE_N):
        _rb_soll[k]     = 0.0
        _rb_test[k]     = None
        _rb_test_bis[k] = 0.0

def rumble_step():
    """Muss in jeder Runde der Hauptschleife laufen. Blockiert nie."""
    if not rumble_da:
        return
    now = time.monotonic()

    for k in range(RUMBLE_N):
        if _rb_in1[k] is None:
            continue
        # Totmannschaltung: kein Lebenszeichen mehr, also aus.
        if _rb_test[k] is not None and now > _rb_test_bis[k]:
            _rb_test[k]     = None
            _rb_test_bis[k] = 0.0
        c = rumble_cfg[k]
        e = _rb_soll[k] if _rb_test[k] is None else _rb_test[k]
        if not c.get("an", True):
            e = 0.0
        e = _rb_schwelle(c, e)
        _rb_ist[k] = e          # nach der Schwelle, damit der Balken zum Motor passt
        phase = _rb_phase[k]

        if e <= 0.004:                       # aus
            # "brems" je Kanal entscheidet, wie lange eine Nullphase
            # ausgelaufen wird, bevor aktiv gestoppt wird. Das ist ein
            # Charakterregler, kein Stellwert fuer die Staerke:
            #
            #   0 ms   jeder Impuls wird sofort gestoppt. Die Schlaege sind
            #          klar voneinander getrennt - ABS, Randstein, Schaltruck.
            #   hoch   kurze Luecken laufen aus, die Impulse verschmelzen zu
            #          durchgehender Vibration - Fahrbahn, Radschlupf.
            #
            # Am Rig nachgemessen, beide Varianten sind brauchbar.
            if phase in ("kick", "lauf"):
                _rb_frei(k)
                _rb_phase[k] = "leer"
                _rb_bis[k]   = now + c.get("brems", RB_BREMS_VERZUG) / 1000
            elif phase == "leer" and now >= _rb_bis[k]:
                _rb_bremsen(k)
                _rb_phase[k] = "brems"
                _rb_bis[k]   = now + RB_BREMS / 1000
            elif phase == "brems" and now >= _rb_bis[k]:
                _rb_frei(k)
                _rb_phase[k] = "aus"
            continue

        if phase == "leer":
            # Der Motor dreht noch - direkt weiterfahren, kein Kickstart.
            _rb_roh(k, _rb_duty(k, e))
            _rb_phase[k] = "lauf"
        elif phase in ("aus", "brems"):
            # Aus dem Stand: nur kicken, wenn der Sollwert unter der
            # Losbrechschwelle liegt. Darueber laeuft er von selbst an.
            ziel = c["min"] + e * (c["max"] - c["min"])
            if ziel < c.get("kick", 0):
                _rb_roh(k, AXIS_MAX)
                _rb_phase[k] = "kick"
                _rb_bis[k]   = now + RB_KICK / 1000
            else:
                _rb_roh(k, _rb_duty(k, e))
                _rb_phase[k] = "lauf"
        elif phase == "kick":
            if now >= _rb_bis[k]:
                _rb_roh(k, _rb_duty(k, e))
                _rb_phase[k] = "lauf"
        else:
            _rb_roh(k, _rb_duty(k, e))

# --- Telemetrie von SimHub ---------------------------------------------------
#
# Format wie bei der Buttonbox: name=wert;name=wert und ein Zeilenumbruch.
# Der Pico rechnet hier nichts aus - die Effekte kommen fertig aus SimHubs
# ShakeIt-Motoren, dort ist die Effektbibliothek ohnehin besser als alles,
# was hier hineinpassen wuerde.

try:
    import usb_cdc
    tele_port = usb_cdc.data
except Exception:
    tele_port = None

tele        = {}
tele_zeit   = 0.0
tele_bytes  = 0
tele_zeilen = 0
tele_roh    = ""
_tele_puffer = ""
_tele_letzte = 0.0

def _tele_zeile(zeile, now):
    global tele, tele_zeit, tele_zeilen
    zeile = zeile.strip()
    if not zeile:
        return
    neu = {}
    for teil in zeile.replace(",", ";").split(";"):
        if "=" not in teil:
            continue
        name, _, wert = teil.partition("=")
        name = name.strip().lower()
        if not name:
            continue
        try:
            neu[name] = float(wert.strip())
        except ValueError:
            s = wert.strip().lower()
            neu[name] = 1.0 if s in ("true", "yes", "on") else 0.0
    if neu:
        tele.update(neu)
        tele_zeit = now
        tele_zeilen += 1

def tele_lesen():
    """Nicht blockierend. Muss in jeder Runde laufen."""
    global tele, _tele_puffer, tele_bytes, tele_roh, _tele_letzte
    now = time.monotonic()
    if tele_port is not None:
        try:
            n = tele_port.in_waiting
            if n:
                roh = tele_port.read(n)
                tele_bytes += len(roh)
                _tele_letzte = now
                text = roh.decode("utf-8", "ignore") if roh else ""
                tele_roh = (tele_roh + text)[-80:]
                _tele_puffer += text.replace("\r", "\n")
                while "\n" in _tele_puffer:
                    zeile, _tele_puffer = _tele_puffer.split("\n", 1)
                    _tele_zeile(zeile, now)
                if len(_tele_puffer) > 200:       # Muell, nie ein Zeilenende
                    _tele_puffer = _tele_puffer[-200:]
        except Exception:
            pass
    # Rettungsanker: Daten kommen an, aber ohne Zeilenumbruch. Passiert, wenn
    # in SimHub das \n in der Formel fehlt - der haeufigste Anfaengerfehler.
    if _tele_puffer and (now - _tele_letzte) > 0.5:
        _tele_zeile(_tele_puffer, now)
        _tele_puffer = ""

    if tele and (now - tele_zeit) > TELE_TIMEOUT:
        # SimHub weg oder Spiel beendet: Motoren aus, nicht im letzten
        # Zustand haengen lassen.
        tele.clear()
        for k in range(RUMBLE_N):
            _rb_soll[k] = 0.0

    # Telemetrie auf die Kanaele legen
    if tele:
        skala = TELE_MAX
        for k in range(RUMBLE_N):
            name = TELE_NAMEN[k] if k < len(TELE_NAMEN) else ""
            v = tele.get(name)
            if v is None:
                continue
            rumble_soll(k, v / skala * rumble_cfg[k].get("gain", 100) / 100.0)

def tele_zustand():
    """0 = nichts empfangen, 1 = Daten ohne Zeile, 2 = verbunden."""
    if tele_bytes == 0:
        return 0
    if tele_zeilen == 0:
        return 1
    return 2

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
    """0.0 .. 1.0 -> 0 .. 65535 (unsigned, wie im Descriptor)."""
    v = int(n * AXIS_MAX + 0.5)
    return 0 if v < 0 else (AXIS_MAX if v > AXIS_MAX else v)

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
    """Endgueltiger HID-Wert inklusive Kennlinie, 0 .. 65535.

    Die Kennlinie rechnet in Prozent, aber als Fliesskomma - zwischen den
    Stuetzpunkten wird linear interpoliert. Es geht also nichts verloren,
    obwohl die Stuetzpunkte selbst ganze Prozent sind.
    """
    p = kurve_anwenden(raw_to_norm(raw, c) * 100, c.get("curve", DEFAULT_CURVE))
    p = 0.0 if p < 0 else (100.0 if p > 100 else p)
    return norm_to_axis(p / 100.0)

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
    rumble_alles_aus()          # waehrend der Wegmessung nicht ruetteln
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
            continue
        rumble_step()                       # auch hier: bis zu 5 s Wartezeit
        if time.monotonic() > ende:
            break                           # Gegenstelle weg
        if cal_zustand == CAL_SWEEP:
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
        rumble_step()               # Totmannschaltung darf nie stehenbleiben
        if cal_zustand == CAL_SWEEP:
            sweep_update()
        else:
            tele_lesen()
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
        "rb": [int(_rb_ist[k] * 100) for k in range(RUMBLE_N)],
        "tz": tele_zustand(),
        "tb": tele_bytes,
        "tl": tele_zeilen,
        "tr": tele_roh[-40:],
        "tv": {n: tele.get(n) for n in TELE_NAMEN if n in tele},
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
            "rn": list(RB_NAMEN[:RUMBLE_N]),
            "rc": rumble_cfg,
            "rt": list(TELE_NAMEN[:RUMBLE_N]),
            "rd": rumble_da,
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

    elif pfad == "/rumble_set":
        try:
            d = json.loads(body)
            for i in range(RUMBLE_N):
                if i < len(d) and isinstance(d[i], dict):
                    for feld in ("schwelle", "min", "max", "kick",
                                 "gain", "brems"):
                        if feld in d[i]:
                            v = int(d[i][feld])
                            grenze = 1000 if feld == "brems" else 200
                            rumble_cfg[i][feld] = (0 if v < 0
                                                   else (grenze if v > grenze else v))
                    if "an" in d[i]:
                        rumble_cfg[i]["an"] = bool(d[i]["an"])
            ok = rumble_speichern()
        except Exception as e:
            print("Rumble-Einstellungen fehlerhaft:", e)
            ok = False
        http_json(conn, {"ok": ok, "rc": rumble_cfg})

    elif pfad.startswith("/rumble_test"):
        k = query_param(pfad, "k")
        v = query_param(pfad, "v")
        q = query_param(pfad, "s")
        try:
            rumble_test_setz(int(k), float(v),
                             int(q) if q is not None else None)
        except (TypeError, ValueError):
            pass
        http_json(conn, {"ok": True})

    elif pfad.startswith("/rumble_stop"):
        rumble_not_aus()
        http_json(conn, {"ok": True})

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
print("Pico W Pedale v9.5 bereit - Bremse:", BREMSE_TYP, hx_modus,
      "- HID:", "ja" if gamepad_device else "NEIN")
time.sleep(1.0)

# --- Hauptschleife -----------------------------------------------------------

while True:
    now = time.monotonic()
    wifi_btn.update()

    # Beides muss in jeder Runde laufen und blockiert nie.
    tele_lesen()
    rumble_step()

    if BREMSE_TYP == "hx711" and now - hx_rate_t >= 1.0:
        hx_rate   = hx_count       # tatsaechlich erreichte Wandlungen pro Sekunde
        hx_count  = 0
        hx_rate_t = now

    if wifi_btn.fell:
        # Der Taster ist immer zuerst Not-Aus. Das ist der einzige Weg, der
        # ohne Browser, ohne WLAN und ohne PC funktioniert.
        rumble_not_aus()
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
            rumble_not_aus()        # ohne Oberflaeche kein Handbetrieb mehr
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
        # achse_lesen mittelt ueber HID_MITTEL Messungen und ist dabei
        # wraparound-fest. Die Waegezelle wird darin automatisch uebersprungen,
        # die ist von sich aus langsam genug.
        gamepad_senden(achse_wert(achse_lesen(0, HID_MITTEL), cal[0]),
                       achse_wert(achse_lesen(1, HID_MITTEL), cal[1]),
                       achse_wert(achse_lesen(2, HID_MITTEL), cal[2]))
        if not wlan_aktiv:
            time.sleep(0.001)
