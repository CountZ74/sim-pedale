"""Testet die Rumble-Kennlinie, die Zustandsmaschine und den Zeilenparser.

Laeuft mit normalem Python auf dem PC, nicht auf dem Pico. Nachbildung der
entsprechenden Teile aus code.py - die Hardware laesst sich hier nicht
nachstellen, die Logik davor schon.
"""

AXIS_MAX = 65535

VERSORGUNG = 15.0
MOTOR_NENN = 12.0
DECKEL = min(AXIS_MAX, int(AXIS_MAX * MOTOR_NENN / VERSORGUNG))

KICK_MS  = 50
BREMS_MS = 80
BREMS_VERZUG = 120
TELE_MAX = 100.0
TELE_TIMEOUT = 2.0

fehler = []


def melde(name, ok):
    print(("ok   " if ok else "FEHL ") + name)
    if not ok:
        fehler.append(name)


# --- Nachbildung: Kennlinie --------------------------------------------------

def schwelle(c, e):
    """Schwelle anwenden und spreizen - wie _rb_schwelle in code.py."""
    sw = c.get("schwelle", 0) / 100.0
    if sw <= 0.0:
        return e
    if e <= sw:
        return 0.0
    if sw >= 1.0:
        return 1.0
    return (e - sw) / (1.0 - sw)


def duty(c, e):
    p = c["min"] + e * (c["max"] - c["min"])
    p = 0 if p < 0 else (100 if p > 100 else p)
    return int(DECKEL * p / 100)


# --- Nachbildung: Zustandsmaschine ------------------------------------------

class Kanal:
    """Bildet _rb_phase/_rb_bis aus code.py nach und protokolliert die Ausgabe."""

    def __init__(self, cfg):
        self.c = cfg
        self.phase = "aus"
        self.bis = 0.0
        self.ausgabe = None          # None = frei, "brems", sonst Duty
        self.verlauf = []

    def _setz(self, was):
        self.ausgabe = was
        self.verlauf.append((self.phase, was))

    def step(self, e, now):
        c = self.c
        if e <= 0.004:
            if self.phase in ("kick", "lauf"):
                self._setz(None)                 # erst auslaufen
                self.phase = "leer"
                self.bis = now + self.c.get("brems", BREMS_VERZUG) / 1000
            elif self.phase == "leer" and now >= self.bis:
                self._setz("brems")
                self.phase = "brems"
                self.bis = now + BREMS_MS / 1000
            elif self.phase == "brems" and now >= self.bis:
                self._setz(None)
                self.phase = "aus"
            return
        if self.phase == "leer":
            self._setz(duty(c, e))               # dreht noch, kein Kick
            self.phase = "lauf"
        elif self.phase in ("aus", "brems"):
            ziel = c["min"] + e * (c["max"] - c["min"])
            if ziel < c.get("kick", 0):
                self._setz(AXIS_MAX)
                self.phase = "kick"
                self.bis = now + KICK_MS / 1000
            else:
                self._setz(duty(c, e))
                self.phase = "lauf"
        elif self.phase == "kick":
            if now >= self.bis:
                self._setz(duty(c, e))
                self.phase = "lauf"
        else:
            self._setz(duty(c, e))


# --- Nachbildung: Zeilenparser ----------------------------------------------

def zeile_werten(zeile, tele):
    zeile = zeile.strip()
    if not zeile:
        return False
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
        return True
    return False


def strom_werten(stuecke, pause_nach=None):
    """Bytes stueckweise hineingeben, wie sie ueber USB eintrudeln."""
    tele, puffer, zeilen = {}, "", 0
    for st in stuecke:
        puffer += st.replace("\r", "\n")
        while "\n" in puffer:
            z, puffer = puffer.split("\n", 1)
            if zeile_werten(z, tele):
                zeilen += 1
    if puffer and pause_nach:            # Rettungsanker nach 0,5 s Stille
        if zeile_werten(puffer, tele):
            zeilen += 1
        puffer = ""
    return tele, puffer, zeilen


# =============================================================================

print("--- 1. Deckel bei 15 V --------------------------------------")
print("     Deckel %d von %d = %.0f %%" % (DECKEL, AXIS_MAX,
                                           DECKEL * 100 / AXIS_MAX))
melde("Deckel entspricht 12 von 15 Volt", abs(DECKEL / AXIS_MAX - 0.8) < 0.001)
melde("gleiche Spannung ergaebe keinen Deckel",
      min(AXIS_MAX, int(AXIS_MAX * 12.0 / 12.0)) == AXIS_MAX)

print("\n--- 2. Kennlinie min..max -----------------------------------")
c = {"min": 8, "max": 100, "kick": 12, "gain": 100, "an": True}
print("     e=0 -> %d, e=0.5 -> %d, e=1 -> %d"
      % (duty(c, 0.0), duty(c, 0.5), duty(c, 1.0)))
melde("kleinste Staerke landet auf min, nicht auf null",
      duty(c, 0.0) == int(DECKEL * 8 / 100))
melde("volle Staerke landet auf max", duty(c, 1.0) == DECKEL)
werte = [duty(c, i / 200) for i in range(201)]
melde("monoton ueber den ganzen Bereich",
      all(werte[i] >= werte[i - 1] for i in range(1, len(werte))))
melde("nie ueber den Deckel", max(werte) <= DECKEL)

print("\n--- 3. Kickstart nur, wenn noetig ---------------------------")
k = Kanal(dict(c))
k.step(1.0, 0.0)                       # volle Staerke aus dem Stand
melde("hohe Staerke laeuft ohne Kick an", k.phase == "lauf")

k = Kanal(dict(c))
k.step(0.02, 0.0)                      # Ziel 9,8 % < kick 12 %
melde("kleine Staerke bekommt einen Kick", k.phase == "kick")
melde("waehrend des Kicks volle Spannung", k.ausgabe == AXIS_MAX)
k.step(0.02, 0.02)                     # 20 ms spaeter: Kick laeuft noch
melde("Kick wird nicht vorzeitig beendet", k.phase == "kick")
k.step(0.02, 0.06)                     # 60 ms: vorbei
melde("nach dem Kick auf den Sollwert", k.phase == "lauf")
melde("Sollwert nach dem Kick ist klein", k.ausgabe == duty(c, 0.02))

print("\n--- 4. Abschalten: erst auslaufen, dann bremsen -------------")
k = Kanal(dict(c, brems=120))
k.step(0.8, 0.0)
k.step(0.0, 0.10)
melde("beim Abschalten wird zuerst nur ausgelaufen",
      k.phase == "leer" and k.ausgabe is None)
k.step(0.0, 0.20)
melde("waehrend der Auslaufzeit bleibt es dabei", k.phase == "leer")
k.step(0.0, 0.25)
melde("nach RUMBLE_BREMS_VERZUG_MS wird gebremst", k.ausgabe == "brems")
k.step(0.0, 0.40)
melde("danach frei", k.phase == "aus" and k.ausgabe is None)

print("\n--- 4b. brems = 0: Impulse bleiben getrennt -----------------")
# Am Rig gemessen: im slow-decay-Modus hat jeder einzelne Impuls genug
# Drehmoment, und das Bremsen dazwischen trennt sie sauber voneinander.
c0 = dict(c); c0["brems"] = 0
k = Kanal(c0)
tt = 0.0
gebremst = 0
for _ in range(12):
    k.step(1.0, tt); tt += 0.04
    k.step(0.0, tt); tt += 0.02
    k.step(0.0, tt); tt += 0.02
    if any(w == "brems" for _, w in k.verlauf[-2:]):
        gebremst += 1
print("     12 Impulse mit brems=0: %d mal gebremst" % gebremst)
melde("bei brems=0 wird jeder Impuls einzeln gestoppt", gebremst >= 10)

print("\n--- 4c. brems = 120: Impulse verschmelzen -------------------")
# Das ist die Messung vom Rig: eine Folge mit 12 Hz (40 ms an, 40 ms aus)
# darf zwischen den Impulsen NICHT gebremst werden, sonst faengt jeder
# Impuls bei Drehzahl null an.
c120 = dict(c); c120["brems"] = 120
k = Kanal(c120)
tt = 0.0
gebremst = kicks = 0
for _ in range(12):
    k.step(1.0, tt); tt += 0.04         # 40 ms an
    if k.phase == "kick":
        kicks += 1
    k.step(0.0, tt); tt += 0.04         # 40 ms aus
    if k.ausgabe == "brems":
        gebremst += 1
print("     12 Impulse mit 12,5 Hz und brems=120: %d mal gebremst, %d Kickstarts"
      % (gebremst, kicks))
melde("40-ms-Luecken laufen aus statt zu bremsen", gebremst == 0)
melde("und es gibt nur den einen Kickstart am Anfang", kicks <= 1)

# Nach dem letzten Impuls muss aber sauber gestoppt werden.
for i in range(6):
    k.step(0.0, tt); tt += 0.05
melde("nach dem Ende der Folge wird doch gebremst",
      any(w == "brems" for _, w in k.verlauf[-6:]))

print("\n--- 4d. Schwelle ------------------------------------------")
# Uebernommen von SimHubs Motorausgang: unterhalb der Schwelle passiert gar
# nichts, darueber wird der Rest auf den vollen Bereich gespreizt. Sonst laeuft
# der Motor bei jedem Hintergrundrauschen mit Mindestdrehzahl mit.
cs = dict(c); cs["schwelle"] = 4
melde("unter der Schwelle kommt nichts an", schwelle(cs, 0.03) == 0.0)
melde("genau auf der Schwelle noch nicht", schwelle(cs, 0.04) == 0.0)
melde("knapp darueber faengt es bei fast null an",
      0.0 < schwelle(cs, 0.05) < 0.02)
melde("volle Staerke bleibt volle Staerke",
      abs(schwelle(cs, 1.0) - 1.0) < 1e-9)
werte = [schwelle(cs, i / 200) for i in range(201)]
melde("monoton", all(werte[i] >= werte[i - 1] for i in range(1, len(werte))))

# Der Fall, um den es geht: Dauerrauschen eines Fahrbahneffekts.
c0 = dict(c); c0["schwelle"] = 0
def _zeig(cc, e):
    x = schwelle(cc, e)
    return "aus" if x <= 0.004 else ("duty %d" % duty(cc, x))

print("     Effekt rauscht bei 2 %%:  ohne Schwelle -> %s,  mit Schwelle -> %s"
      % (_zeig(c0, 0.02), _zeig(cs, 0.02)))
melde("ohne Schwelle brummt der Motor schon bei 2 Prozent mit",
      duty(c0, schwelle(c0, 0.02)) > 0)
melde("mit Schwelle bleibt er dabei aus", schwelle(cs, 0.02) == 0.0)

melde("Schwelle 0 aendert nichts", schwelle(c0, 0.37) == 0.37)

print("\n--- 5. Kanal aus -------------------------------------------")
c_aus = dict(c); c_aus["an"] = False
e = 0.9 if c_aus["an"] else 0.0
melde("abgeschalteter Kanal bekommt Staerke 0", e == 0.0)

print("\n--- 6. Zeilenparser ----------------------------------------")
t, p, n = strom_werten(["bremse=42;gas=7\n"])
print("     ->", t)
melde("beide Werte erkannt", t == {"bremse": 42.0, "gas": 7.0})
melde("Puffer leer", p == "")

t, _, _ = strom_werten(["bremse=0,gas=100\n"])
melde("Komma statt Semikolon geht auch", t == {"bremse": 0.0, "gas": 100.0})

t, _, _ = strom_werten(["Bremse=5\r\n"])
melde("Grossschreibung und CRLF", t == {"bremse": 5.0})

t, _, _ = strom_werten(["brem", "se=33;ga", "s=1\n"])
melde("ueber mehrere Lesungen zerstueckelt", t == {"bremse": 33.0, "gas": 1.0})

t, p, n = strom_werten(["bremse=50"])                 # kein \n
melde("ohne Zeilenende erst mal nichts", t == {} and n == 0)
t, p, n = strom_werten(["bremse=50"], pause_nach=True)
melde("Rettungsanker greift nach der Pause", t == {"bremse": 50.0})

t, _, _ = strom_werten(["bremse=True;gas=False\n"])
melde("True/False als Text", t == {"bremse": 1.0, "gas": 0.0})

t, _, _ = strom_werten(["muell ohne gleichheitszeichen\n"])
melde("Muell wirft nichts um", t == {})

print("\n--- 7. Telemetrie auf die Kanaele legen ---------------------")
tele = {"bremse": 75.0, "gas": 0.0}
namen = ["bremse", "gas"]
soll = [tele[namen[i]] / TELE_MAX * c["gain"] / 100.0 for i in range(2)]
print("     SimHub 75/0  ->  Staerke", soll)
melde("75 Prozent werden zu 0.75", abs(soll[0] - 0.75) < 1e-9)
melde("0 bleibt 0", soll[1] == 0.0)

c_gain = dict(c); c_gain["gain"] = 50
s50 = tele["bremse"] / TELE_MAX * c_gain["gain"] / 100.0
melde("Gain 50 halbiert", abs(s50 - 0.375) < 1e-9)

print("\n--- 8. Timeout schaltet ab ---------------------------------")
tele_zeit, now = 10.0, 10.0 + TELE_TIMEOUT + 0.1
abgelaufen = (now - tele_zeit) > TELE_TIMEOUT
melde("nach dem Timeout gelten die Werte als ungueltig", abgelaufen)
k = Kanal(dict(c, brems=120))
k.step(0.9, 0.0)
k.step(0.0, 0.1)                       # Timeout -> Soll 0
melde("Motor bekommt sofort keine Leistung mehr", k.ausgabe is None)
k.step(0.0, 0.3)
melde("und wird danach aktiv gestoppt", k.ausgabe == "brems")
k.step(0.0, 0.5)
melde("am Ende steht er still", k.phase == "aus")

print("\n--- 9. Testbetrieb: Totmann, Reihenfolge, Not-Aus ------------")

RB_TEST_TTL = 1.2


class Test:
    """Nachbildung von rumble_test_setz / der Verfallspruefung in rumble_step."""

    def __init__(self, n=2):
        self.wert = [None] * n
        self.bis = [0.0] * n
        self.seq = -1
        self.sperre = 0.0

    def setz(self, k, v, seq=None, now=0.0):
        if now < self.sperre:
            return
        if seq is not None:
            if seq <= self.seq:
                return
            self.seq = seq
        if v is None or v < 0:
            self.wert[k], self.bis[k] = None, 0.0
        else:
            self.wert[k] = min(1.0, v / 100.0)
            self.bis[k] = now + RB_TEST_TTL

    def step(self, now):
        for k in range(len(self.wert)):
            if self.wert[k] is not None and now > self.bis[k]:
                self.wert[k], self.bis[k] = None, 0.0

    def not_aus(self, now):
        self.sperre = now + 2.0
        for k in range(len(self.wert)):
            self.wert[k], self.bis[k] = None, 0.0


t = Test()
t.setz(0, 60, seq=1, now=0.0)
t.step(0.5)
melde("Testwert haelt, solange er frisch ist", t.wert[0] == 0.6)
t.step(2.0)
melde("ohne Lebenszeichen schaltet er nach der Frist ab", t.wert[0] is None)

t = Test()
for i, tt in enumerate([0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5]):
    t.setz(0, 60, seq=i + 1, now=tt)
    t.step(tt)
melde("regelmaessiges Lebenszeichen haelt ihn am Leben", t.wert[0] == 0.6)
t.step(3.0)
melde("hoert das Lebenszeichen auf, geht er aus", t.wert[0] is None)

# Genau der Fall vom ersten Test am Rig: das "aus" wird abgearbeitet, danach
# taucht eine aeltere, gestaute Anforderung mit hohem Wert auf.
t = Test()
t.setz(0, 80, seq=5, now=0.0)
t.setz(0, -1, seq=9, now=0.1)
melde("das spaetere Aus wirkt", t.wert[0] is None)
t.setz(0, 80, seq=5, now=0.2)          # ueberholte Anforderung aus dem Stau
melde("eine ueberholte Anforderung weckt ihn nicht wieder",
      t.wert[0] is None)
t.setz(0, 80, seq=6, now=0.3)          # auch aelter als 9
melde("auch eine andere alte Nummer nicht", t.wert[0] is None)
t.setz(0, 40, seq=10, now=0.4)         # frische Anforderung
melde("eine neue Anforderung geht wieder durch", t.wert[0] == 0.4)

# Not-Aus muss gewinnen, auch gegen alles, was noch in der Warteschlange steckt.
t = Test()
t.setz(0, 90, seq=1, now=0.0)
t.setz(1, 90, seq=2, now=0.0)
t.not_aus(now=0.1)
melde("Not-Aus schaltet beide Kanaele ab",
      t.wert[0] is None and t.wert[1] is None)
t.setz(0, 90, seq=3, now=0.5)
melde("waehrend der Sperre wird nichts angenommen", t.wert[0] is None)
t.setz(0, 90, seq=4, now=2.5)
melde("nach der Sperre geht es wieder", t.wert[0] == 0.9)

# Und der Kurzimpuls: selbst wenn das Aus verlorengeht, endet er von selbst.
t = Test()
t.setz(0, 100, seq=1, now=0.0)
t.step(0.14)
melde("Kurzimpuls laeuft zunaechst", t.wert[0] == 1.0)
t.step(1.5)                              # das "aus" ging verloren
melde("verlorenes Aus faengt die Totmannschaltung ab", t.wert[0] is None)

print("\n" + "=" * 62)
print("ALLE TESTS BESTANDEN" if not fehler else "FEHLER: %s" % fehler)
