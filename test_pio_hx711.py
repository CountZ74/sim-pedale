"""Test des PIO-HX711-Readers - auf dem Pico laufen lassen, nicht am PC.

So benutzen:
  1. Datei nach CIRCUITPY kopieren (irgendwohin ins Root)
  2. Serielle Konsole oeffnen, Strg+C druecken (stoppt code.py)
  3. Im REPL:  import test_pio_hx711
     Nochmal laufen lassen:  import supervisor; supervisor.reload()  ->  Strg+C
                             und erneut importieren

Erwartung nach der Loetbruecke auf 80 Hz:
  Rate      um die 80 Wandlungen pro Sekunde
  Lesezeit  Bruchteile einer Millisekunde statt 13,8 ms
  Werte     dieselbe Groessenordnung wie beim Bit-Banging, ruhig bei
            unbelasteter Zelle, deutlicher Ausschlag bei Druck aufs Pedal
"""

import time
import board
import rp2pio
import adafruit_pioasm
from array import array

import settings

DT  = getattr(settings, "HX711_DT", "GP1")
SCK = getattr(settings, "HX711_SCK", "GP0")

PROGRAMM = """
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

print("HX711 PIO-Test")
print("DT =", DT, " SCK =", SCK)

sm = rp2pio.StateMachine(
    adafruit_pioasm.assemble(PROGRAMM),
    frequency=1_000_000,
    first_in_pin=getattr(board, DT),
    in_pin_count=1,
    first_sideset_pin=getattr(board, SCK),
    sideset_pin_count=1,
    initial_sideset_pin_state=0,
    initial_sideset_pin_direction=1,
    auto_push=False,
    in_shift_right=False,
)

buf = array("I", [0] * 8)

def lesen():
    """Alle fertigen Wandlungen abholen, den neuesten Wert zurueckgeben."""
    n = sm.in_waiting
    if not n:
        return None, 0
    if n > len(buf):
        n = len(buf)
    sm.readinto(buf, end=n)
    v = buf[n - 1] & 0xFFFFFF
    if v & 0x800000:
        v -= 0x1000000
    return v, n

try:
    # --- 1. Rate ------------------------------------------------------------
    sm.clear_rxfifo()
    t0 = time.monotonic()
    gezaehlt = 0
    letzter = None
    while time.monotonic() - t0 < 3.0:
        v, n = lesen()
        if n:
            gezaehlt += n
            letzter = v
    rate = gezaehlt / 3.0
    print("Rate:      {:.1f} Wandlungen/s".format(rate))
    print("Letzter Wert:", letzter)

    # --- 2. Lesezeit --------------------------------------------------------
    sm.clear_rxfifo()
    while not sm.in_waiting:
        pass
    ges = 0
    for _ in range(30):
        while not sm.in_waiting:
            pass
        t = time.monotonic_ns()
        lesen()
        ges += time.monotonic_ns() - t
    print("Lesezeit:  {:.4f} ms".format(ges / 30 / 1e6))

    # --- 3. Werte ansehen ---------------------------------------------------
    print("\n5 Sekunden lang Werte - jetzt aufs Pedal druecken:")
    sm.clear_rxfifo()
    t0 = time.monotonic()
    naechste = t0
    kleinster = None
    groesster = None
    while time.monotonic() - t0 < 5.0:
        v, n = lesen()
        if n:
            if kleinster is None or v < kleinster:
                kleinster = v
            if groesster is None or v > groesster:
                groesster = v
            if time.monotonic() >= naechste:
                print("   ", v)
                naechste += 0.5
    print("Spanne:", kleinster, "bis", groesster,
          "=", (groesster - kleinster) if kleinster is not None else "-")

    print("\nBewertung:")
    if rate > 60:
        print("  Rate ok - die Loetbruecke sitzt und PIO holt jede Wandlung ab.")
    elif rate > 20:
        print("  Rate um 40: der Chip laeuft auf 80 Hz, aber es geht noch etwas")
        print("  verloren. Ungewoehnlich fuer PIO - bitte melden.")
    else:
        print("  Rate um 10: der Chip laeuft noch auf 10 Hz.")
        print("  Dann sitzt die Loetbruecke nicht richtig.")

finally:
    sm.deinit()
    print("\nPIO freigegeben. Fuer den Normalbetrieb: Strg+D")
