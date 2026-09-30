"""test_rumble.py - Rumble-Motoren pruefen, Schwellen finden, Modi vergleichen.

Laeuft auf dem Pico. Im REPL nach Strg+C:

    import test_rumble as t

    t.rampe(0)          # aufwaerts: Losbrechschwelle (ohne Kickstart)
    t.runter(0)         # abwaerts:  Abfallschwelle  (mit Kickstart)
    t.modus("brake")    # anderes Ansteuerverfahren, dann nochmal runter()
    t.puls(0)           # einzelner Stoss: Kick, halten, aktiv bremsen
    t.folge(0, an_ms=40, aus_ms=40)   # Impulsfolge mit 12 Hz
    t.beide()           # beide gleichzeitig - Netzteiltest
    t.aus()

Gesucht sind zwei Werte pro Kanal:

  Losbrechschwelle - ab hier laeuft er aus dem Stand an. Hoch, weil die
                     Unwucht aus der Ruhelage gehoben werden muss.
  Abfallschwelle   - bis hierher laeuft er weiter, wenn er einmal dreht.
                     Deutlich niedriger, und das ist der Wert, der die
                     Dynamik bestimmt. Deshalb der Kickstart.
"""

import time

import board
import digitalio
import pwmio

# --- Anpassen ----------------------------------------------------------------

# Die tatsaechlich am Treiber gemessene Spannung, nicht die Aufschrift.
# Bei einem USB-PD-Board bitte wirklich nachmessen.
VERSORGUNG = 15.0

# Nennspannung der Motoren.
MOTOR_NENN = 12.0

# (Name, IN1, IN2)
#
# WICHTIG fuer den Modus "brake": die beiden Pins muessen auf derselben
# PWM-Einheit des RP2040 liegen, sonst laufen die Signale auseinander.
# Das ist genau dann der Fall, wenn der erste Pin gerade ist und der zweite
# direkt darauf folgt - also GP4/GP5, GP6/GP7, GP8/GP9 und so weiter.
KANAELE = (
    ("Bremse", "GP4", "GP5"),
    ("Gas",    "GP6", "GP7"),
)

PWM_HZ  = 20000         # ueber dem Hoerbereich
KICK_MS = 50            # Laenge des Anlaufimpulses

# "coast" - PWM auf IN1, IN2 dauerhaft aus. Zwischen den Impulsen laeuft der
#           Motor frei. Einfach, aber im unteren Bereich schwach.
# "brake" - IN1 dauerhaft an, PWM invertiert auf IN2. Zwischen den Impulsen
#           wird der Motor kurzgeschlossen. Der Strom bricht dadurch weniger
#           ein, das Drehmoment bei kleinem Duty ist hoeher und die Kennlinie
#           gleichmaessiger. Meist die bessere Wahl - aber messen, nicht raten.
MODUS = "coast"

# --- Ab hier nichts mehr aendern ---------------------------------------------

VOLL = 65535

# Deckel, damit ein 12-V-Motor an 15 V im Mittel seine 12 V bekommt.
# Bei VERSORGUNG = MOTOR_NENN wird daraus 65535, also gar kein Deckel.
DECKEL = int(VOLL * MOTOR_NENN / VERSORGUNG)
if DECKEL > VOLL:
    DECKEL = VOLL

_in1 = []
_in2 = []
_warnung = []

for _name, _p1, _p2 in KANAELE:
    _in1.append(pwmio.PWMOut(getattr(board, _p1),
                             frequency=PWM_HZ, duty_cycle=0))
    _in2.append(pwmio.PWMOut(getattr(board, _p2),
                             frequency=PWM_HZ, duty_cycle=0))
    _n1 = int(_p1[2:])
    _n2 = int(_p2[2:])
    if not (_n1 % 2 == 0 and _n2 == _n1 + 1):
        _warnung.append("%s: %s/%s liegen nicht auf derselben PWM-Einheit,"
                        " Modus 'brake' kann zappeln" % (_name, _p1, _p2))


def _kanaele(k):
    return range(len(KANAELE)) if k is None else (k,)


def _fahre(k, duty):
    """Rohe Ansteuerung, ohne Deckel. duty 0..65535."""
    if duty < 0:
        duty = 0
    elif duty > VOLL:
        duty = VOLL
    if MODUS == "brake":
        # IN1 fest an, IN2 invertiert: Motor laeuft, wenn IN2 unten ist.
        _in1[k].duty_cycle = VOLL
        _in2[k].duty_cycle = VOLL - duty
    else:
        _in1[k].duty_cycle = duty
        _in2[k].duty_cycle = 0


def modus(m):
    """Zwischen 'coast' und 'brake' umschalten. Motoren gehen dabei aus."""
    global MODUS
    if m not in ("coast", "brake"):
        print("Nur 'coast' oder 'brake'")
        return
    aus()
    MODUS = m
    print("Modus:", m)


def aus(k=None):
    """Auslaufen lassen. Ohne Argument alle Kanaele."""
    for i in _kanaele(k):
        _in1[i].duty_cycle = 0
        _in2[i].duty_cycle = 0


def bremsen(k=None, ms=100):
    """Motor kurzschliessen - die Unwucht steht fast sofort.

    Beide Eingaenge hoch schaltet beim DRV8871 die unteren Schalter ein.
    Bei rund 100 g rotierender Masse ist der Unterschied zum Auslaufen
    deutlich hoerbar und macht einzelne Stoesse erst knackig.
    """
    for i in _kanaele(k):
        _in1[i].duty_cycle = VOLL
        _in2[i].duty_cycle = VOLL
    time.sleep(ms / 1000)
    aus(k)


def _kick(k):
    _fahre(k, VOLL)             # der Kick darf ueber den Deckel
    time.sleep(KICK_MS / 1000)


def dauer(k, prozent, sekunden=None, kick=True):
    """Dauerlauf. prozent bezieht sich auf den Deckel, nicht auf die Rohspannung."""
    d = int(DECKEL * prozent / 100)
    if kick:
        _kick(k)
    _fahre(k, d)
    print("%s [%s]: %d%%  ->  duty %d von %d"
          % (KANAELE[k][0], MODUS, prozent, d, DECKEL))
    if sekunden:
        time.sleep(sekunden)
        aus(k)


def rampe(k, schritt=2, halten=0.7, von=0, bis=100):
    """Aufwaerts aus dem Stand: sucht die LOSBRECHSCHWELLE.

    Notier den Wert, bei dem er zuverlaessig anlaeuft - nicht den, bei dem
    er nur brummt. Zweimal machen, die Schwelle streut.
    """
    print("--- %s [%s]: %d -> %d %%, Strg+C bricht ab"
          % (KANAELE[k][0], MODUS, von, bis))
    try:
        for p in range(von, bis + 1, schritt):
            _fahre(k, int(DECKEL * p / 100))
            print("   %3d %%" % p)
            time.sleep(halten)
    finally:
        aus(k)
        print("--- aus")


def runter(k, schritt=2, halten=0.8, von=100, bis=0):
    """Abwaerts mit Kickstart: sucht die ABFALLSCHWELLE.

    Der interessantere der beiden Werte. Er sagt, wie leise du den Effekt
    fahren kannst, ohne dass der Motor stehenbleibt - und damit, wie gross
    die Spanne zwischen zartem Vibrieren und hartem Schlag ist.
    """
    print("--- %s [%s]: Kickstart, dann %d -> %d %%"
          % (KANAELE[k][0], MODUS, von, bis))
    try:
        _kick(k)
        for p in range(von, bis - 1, -schritt):
            _fahre(k, int(DECKEL * p / 100))
            print("   %3d %%" % p)
            time.sleep(halten)
    finally:
        aus(k)
        print("--- aus")


def puls(k, staerke=70, ms=120, kick_ms=None):
    """Ein einzelner Stoss: Kickstart, halten, aktiv bremsen.

    ACHTUNG: ms ist die Haltezeit NACH dem Kickstart. Die Gesamtlaenge ist
    kick_ms + ms. Wer wirklich kurze Impulse messen will, muss also auch den
    Kickstart herunterdrehen:

        t.puls(0, ms=1, kick_ms=5)      # 6 ms gesamt
        t.puls(0, ms=1, kick_ms=0)      # ohne Kick, nur die Haltezeit
    """
    kk = KICK_MS if kick_ms is None else kick_ms
    if kk > 0:
        _fahre(k, VOLL)
        time.sleep(kk / 1000)
    _fahre(k, int(DECKEL * staerke / 100))
    time.sleep(ms / 1000)
    bremsen(k)


def folge(k, n=12, an_ms=60, aus_ms=60, staerke=100, mit_bremse=True):
    """Impulsfolge - so wuerde sich ein ABS-Rattern anfuehlen.

    Die Frequenz ist 1000 / (an_ms + aus_ms). Damit findest du heraus, wie
    schnell dein Aufbau noch EINZELNE Schlaege liefert und ab wann daraus ein
    durchgehendes Brummen wird. Unterhalb dieser Grenze lohnt es sich nicht,
    in SimHub feiner einzustellen.

        t.folge(0, an_ms=100, aus_ms=100)   #  5 Hz
        t.folge(0, an_ms= 60, aus_ms= 60)   #  8 Hz
        t.folge(0, an_ms= 40, aus_ms= 40)   # 12 Hz - ABS-Bereich
        t.folge(0, an_ms= 25, aus_ms= 25)   # 20 Hz

    mit_bremse=False zum Vergleich: dann trudelt die Unwucht zwischen den
    Impulsen aus, statt aktiv gestoppt zu werden. Der Unterschied ist der
    eigentliche Grund, warum kurze Stoesse ueberhaupt funktionieren.
    """
    hz = 1000.0 / (an_ms + aus_ms)
    print("%s: %d Impulse, %d ms an / %d ms aus  ->  %.1f Hz%s"
          % (KANAELE[k][0], n, an_ms, aus_ms, hz,
             "" if mit_bremse else "  (ohne aktives Bremsen)"))
    try:
        for _ in range(n):
            _fahre(k, int(DECKEL * staerke / 100))
            time.sleep(an_ms / 1000)
            if mit_bremse:
                _in1[k].duty_cycle = VOLL       # beide hoch = kurzgeschlossen
                _in2[k].duty_cycle = VOLL
            else:
                _in1[k].duty_cycle = 0          # beide aus = freier Auslauf
                _in2[k].duty_cycle = 0          # (_fahre(k,0) waere im Modus
                                                #  "brake" ebenfalls Bremsen!)
            time.sleep(aus_ms / 1000)
    finally:
        aus(k)


def beide(prozent=70, sekunden=3, versatz_ms=40):
    """Beide Motoren gleichzeitig - der eigentliche Netzteiltest.

    Die Kickstarts sind versetzt, damit sich die Anlaufspitzen nicht
    addieren. Verliert dein USB-PD-Board beim Anlauf den Vertrag, faellt es
    auf 5 V zurueck und beide bleiben stehen - dann brauchst du mehr
    Pufferkondensator oder mehr Versatz.
    """
    for i in range(len(KANAELE)):
        _kick(i)
        _fahre(i, int(DECKEL * prozent / 100))
        if i + 1 < len(KANAELE):
            time.sleep(versatz_ms / 1000)
    print("beide auf %d%% [%s] fuer %s s" % (prozent, MODUS, sekunden))
    time.sleep(sekunden)
    bremsen()


def vergleich(k, prozent=40, sekunden=2):
    """Denselben Sollwert einmal in jedem Modus - zum Fuehlen und Hoeren."""
    global MODUS
    alt = MODUS
    for m in ("coast", "brake"):
        MODUS = m
        print("\n>>> %s bei %d %%" % (m, prozent))
        dauer(k, prozent, sekunden)
        time.sleep(0.5)
    MODUS = alt
    print("\nzurueck auf", MODUS)


print("test_rumble bereit.")
print("  Versorgung %.1f V, Motor %.1f V  ->  Deckel %d von %d (%.0f %%)"
      % (VERSORGUNG, MOTOR_NENN, DECKEL, VOLL, DECKEL * 100 / VOLL))
if VERSORGUNG > MOTOR_NENN * 1.05:
    print("  Der Deckel ist aktiv: 100 %% heisst %.1f V am Motor."
          % MOTOR_NENN)
print("  Modus:", MODUS)
for _i, _k in enumerate(KANAELE):
    print("  Kanal %d = %-7s  IN1 %s   IN2 %s" % (_i, _k[0], _k[1], _k[2]))
for _w in _warnung:
    print("  ACHTUNG:", _w)
aus()
