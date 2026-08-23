"""Testet die Wraparound-Mathematik und die Sweep-Erkennung aus code.py.

Laeuft mit normalem Python auf dem PC, nicht auf dem Pico.
"""

ADC_SPAN  = 65536
HALF_SPAN = ADC_SPAN // 2
DEADZONE  = 0.0          # fuer die Tests abgeschaltet, sonst verzerrt es
SWEEP_MARGIN = 0.0

SWEEP_FELDER = 256
SWEEP_SHIFT  = 8
SWEEP_BREITE = ADC_SPAN // SWEEP_FELDER


# --- Nachbildungen aus code.py ----------------------------------------------

def raw_to_norm(raw, c):
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
            return 0.0
        else:
            n = 1.0
    if n <= DEADZONE:
        return 0.0
    if n >= 1.0:
        return 1.0
    return (n - DEADZONE) / (1.0 - DEADZONE)


def kreis_mittel(samples):
    """Nachbildung von achse_lesen: Mittelung ueber den Nulldurchgang."""
    basis = samples[0]
    summe = 0
    for s in samples[1:]:
        d = (s - basis) % ADC_SPAN
        if d > HALF_SPAN:
            d -= ADC_SPAN
        summe += d
    return (basis + summe // len(samples)) % ADC_SPAN


SWEEP_FUELL_MAX = 64


def sweep_karte(zero, verlauf):
    """sweep_update: besuchte Winkelfelder ankreuzen, Strecke dazwischen fuellen."""
    cover = bytearray(SWEEP_FELDER)
    letztes = zero >> SWEEP_SHIFT
    cover[letztes] = 1
    for raw in verlauf:
        feld = raw >> SWEEP_SHIFT
        d = (feld - letztes) % SWEEP_FELDER
        if d == 0:
            continue
        if d <= SWEEP_FUELL_MAX:
            i = letztes
            for _ in range(d):
                i = (i + 1) % SWEEP_FELDER
                cover[i] = 1
        elif SWEEP_FELDER - d <= SWEEP_FUELL_MAX:
            i = letztes
            for _ in range(SWEEP_FELDER - d):
                i = (i - 1) % SWEEP_FELDER
                cover[i] = 1
        else:
            cover[feld] = 1
        letztes = feld
    return cover


def sweep_wege(zero, cover):
    """sweep_wege: laengster zusammenhaengender Bogen je Richtung."""
    null = zero >> SWEEP_SHIFT

    def lauf(schritt):
        n, i = 0, null
        while n < SWEEP_FELDER - 1:
            i = (i + schritt) % SWEEP_FELDER
            if not cover[i]:
                break
            n += 1
        return n * SWEEP_BREITE

    return lauf(1), lauf(-1)


def sweep(zero, verlauf):
    """sweep_start + sweep_update + sweep_finish in einem."""
    auf, ab = sweep_wege(zero, sweep_karte(zero, verlauf))
    if auf >= ab:
        weg, vorwaerts = auf, True
    else:
        weg, vorwaerts = ab, False
    weg = int(weg * (1.0 - SWEEP_MARGIN)) or 1
    return {"typ": "adc", "start": zero,
            "span": weg if vorwaerts else -weg}


def pedalfahrt(von, bis, abwaerts, schritt=40):
    """Dichter Rohwertverlauf zwischen zwei Winkeln, wie beim echten Treten."""
    weg, r = [], von
    strecke = (von - bis) % ADC_SPAN if abwaerts else (bis - von) % ADC_SPAN
    gefahren = 0
    while gefahren < strecke:
        weg.append(r % ADC_SPAN)
        gefahren += schritt
        r = r - schritt if abwaerts else r + schritt
    weg.append(bis)
    return weg


# --- Testgeruest -------------------------------------------------------------

fehler = []

def pruefe(name, ist, soll, tol=0.02):
    ok = abs(ist - soll) <= tol
    if not ok:
        fehler.append(name)
    print(f"{'ok  ' if ok else 'FEHL'} {name:<52} ist={ist:.3f} soll={soll:.3f}")

def melde(name, ok):
    if not ok:
        fehler.append(name)
    print(f"{'ok  ' if ok else 'FEHL'} {name}")


print("--- 1. Normalfall ohne Grenzueberschreitung -----------------")
c = {"typ": "adc", "start": 10000, "span": 6000}
pruefe("losgelassen", raw_to_norm(10000, c), 0.0)
pruefe("halb", raw_to_norm(13000, c), 0.5)
pruefe("voll", raw_to_norm(16000, c), 1.0)
pruefe("knapp unter Null -> 0 (Rauschen)", raw_to_norm(9950, c), 0.0)
pruefe("Ueberhub jenseits Endpunkt -> 100", raw_to_norm(20000, c), 1.0)

print("\n--- 2. Pedalweg laeuft ueber die 0-Grad-Grenze --------------")
c = {"typ": "adc", "start": 63000, "span": 6000}
pruefe("Nullpunkt 63000", raw_to_norm(63000, c), 0.0)
pruefe("kurz vor der Grenze 65535", raw_to_norm(65535, c), 2535 / 6000)
pruefe("genau auf der Grenze 0", raw_to_norm(0, c), 2536 / 6000)
pruefe("hinter der Grenze 2000", raw_to_norm(2000, c), 4536 / 6000)
pruefe("Endpunkt 3464", raw_to_norm(3464, c), 1.0)
pruefe("Zittern unter Null 62900 -> 0", raw_to_norm(62900, c), 0.0)
pruefe("Ueberhub 10000 -> 100", raw_to_norm(10000, c), 1.0)

print("\n--- 3. Umgekehrte Richtung ueber die Grenze -----------------")
c = {"typ": "adc", "start": 3000, "span": -6000}
pruefe("Nullpunkt 3000", raw_to_norm(3000, c), 0.0)
pruefe("halb 0", raw_to_norm(0, c), 0.5)
pruefe("hinter der Grenze 64536", raw_to_norm(64536, c), 4000 / 6000)
pruefe("Endpunkt 62536", raw_to_norm(62536, c), 1.0)
pruefe("Zittern ueber Null 3100 -> 0", raw_to_norm(3100, c), 0.0)

print("\n--- 4. Alter v8-Ansatz zum Vergleich ------------------------")
mn, mx = 3464, 63000
alt = (65535 - mn) / (mx - mn)
print(f"     v8 bei Rohwert 65535: {alt*100:.1f}%  (richtig waeren 42.3%)")
print("     -> genau der Sprung, der die Kalibrierung unbrauchbar macht")

print("\n--- 5. Mittelung ueber den Nulldurchgang --------------------")
m = kreis_mittel([65500, 65520, 10, 30])
print(f"     Samples 65500/65520/10/30 -> Mittel {m}")
melde("Mittel liegt am Nulldurchgang, nicht bei 32768", m > 65000 or m < 500)

print("\n--- 6. Sweep, kleiner Weg ueber die Grenze ------------------")
hin = pedalfahrt(63000, 3400, abwaerts=False)
c = sweep(63000, hin + list(reversed(hin)))
print(f"     erkannt: start={c['start']} span={c['span']}")
pruefe("Endpunkt ergibt 100%", raw_to_norm(3400, c), 1.0, 0.03)
pruefe("Nullpunkt ergibt 0%", raw_to_norm(63000, c), 0.0)
melde("Richtung als aufwaerts erkannt", c["span"] > 0)

hin = pedalfahrt(3000, 62600, abwaerts=True)
c = sweep(3000, hin + list(reversed(hin)))
print(f"     erkannt: start={c['start']} span={c['span']}")
pruefe("rueckwaerts: Endpunkt = 100%", raw_to_norm(62600, c), 1.0, 0.03)
melde("Richtung als abwaerts erkannt", c["span"] < 0)

print("\n--- 7. Waegezelle (linear, kein Kreis) ----------------------")
c = {"typ": "hx711", "start": 0, "span": 50000}
pruefe("kein Druck", raw_to_norm(0, c), 0.0)
pruefe("halbe Kraft", raw_to_norm(25000, c), 0.5)
pruefe("volle Kraft", raw_to_norm(50000, c), 1.0)
pruefe("Ueberlast", raw_to_norm(80000, c), 1.0)

print("\n--- 8. Vollstaendiger Durchlauf aller Rohwerte --------------")
c = {"typ": "adc", "start": 63000, "span": 6000}
werte = [raw_to_norm(r, c) for r in range(ADC_SPAN)]
print(f"     Minimum {min(werte):.3f}  Maximum {max(werte):.3f}")
melde("kein Wert verlaesst 0..1",
      min(werte) == 0.0 and max(werte) == 1.0 and all(0 <= v <= 1 for v in werte))
spruenge = [r for r in range(1, ADC_SPAN) if abs(werte[r] - werte[r-1]) > 0.01]
print(f"     Unstetigkeiten: {len(spruenge)} bei Rohwert(en) {spruenge[:5]}")
melde("genau eine Kante, und zwar mittig im toten Bogen", len(spruenge) == 1)

print("\n--- 9. Sebis Gaspedal: 6800 abwaerts ueber 0 bis 34000 ------")
# 38336 Zaehler = 210 Grad, also MEHR als eine halbe Umdrehung.
hin  = pedalfahrt(6800, 34000, abwaerts=True)
zur  = list(reversed(hin))
echt = (6800 - 34000) % ADC_SPAN
c = sweep(6800, hin + zur + hin + zur)
print(f"     echter Weg  {echt} Zaehler = {echt/ADC_SPAN*360:.1f} Grad")
print(f"     erkannt     span={c['span']} = {abs(c['span'])/ADC_SPAN*360:.1f} Grad")
melde("Richtung abwaerts, Weg auf 2 Prozent genau",
      c["span"] < 0 and abs(abs(c["span"]) - echt) < echt * 0.02)

pruefe("Nullpunkt 6800 -> 0%", raw_to_norm(6800, c), 0.0)
pruefe("nach 1/4 Weg (raw 57000)", raw_to_norm(57000, c), 15336/echt, 0.03)
pruefe("nach halbem Weg (raw 52500)", raw_to_norm(52500, c), 19836/echt, 0.03)
pruefe("nach 3/4 Weg (raw 43000)", raw_to_norm(43000, c), 29336/echt, 0.03)
pruefe("Endpunkt 34000 -> 100%", raw_to_norm(34000, c), 1.0, 0.03)
pruefe("Ueberhub 33000 -> 100%", raw_to_norm(33000, c), 1.0)
pruefe("Rauschen ueber Null (7000) -> 0%", raw_to_norm(7000, c), 0.0)

werte = [raw_to_norm(r, c) for r in hin]
rueck = [i for i in range(1, len(werte)) if werte[i] < werte[i-1] - 0.001]
print(f"     Ruecksprünge auf dem Pedalweg: {len(rueck)}")
melde("steigt ueber den ganzen Weg monoton an", not rueck)

print("\n--- 10. Abtastluecke waehrend des Sweeps --------------------")
# Genau der Fall, an dem der aufsummierende Zaehler gescheitert ist:
# waehrend des Tretens fehlen 900 Messwerte am Stueck.
luecke_ab, luecke_n = 30, 900
mit_luecke = hin[:luecke_ab] + hin[luecke_ab + luecke_n:]

# So haette der alte Zaehler (v9.1/v9.2) gerechnet
last, pos, smax, smin = 6800, 0, 0, 0
for raw in mit_luecke + list(reversed(mit_luecke)):
    d = (raw - last) % ADC_SPAN
    if d > HALF_SPAN:
        d -= ADC_SPAN
    last = raw
    pos += d
    smax, smin = max(smax, pos), min(smin, pos)
zaehler_weg = max(smax, -smin)

karte = sweep_karte(6800, mit_luecke)
auf1, ab1 = sweep_wege(6800, karte)
print(f"     1. Durchtritt mit Luecke:")
print(f"        aufsummierender Zaehler {zaehler_weg}"
      f" ({zaehler_weg/ADC_SPAN*360:.1f} Grad)  <- laeuft weg")
print(f"        Abdeckungskarte         {max(auf1, ab1)}"
      f" ({max(auf1, ab1)/ADC_SPAN*360:.1f} Grad)  <- zu kurz, aber ehrlich")
melde("Karte ueberschaetzt nie", max(auf1, ab1) <= echt)
melde("Zaehler liefert einen falschen Weg",
      abs(zaehler_weg - echt) > echt * 0.05)

# Zweiter, vollstaendiger Durchtritt fuellt die Luecke
karte = sweep_karte(6800, mit_luecke + list(reversed(hin)))
auf2, ab2 = sweep_wege(6800, karte)
weg2 = max(auf2, ab2)
print(f"     2. Durchtritt fuellt die Luecke: {weg2}"
      f" ({weg2/ADC_SPAN*360:.1f} Grad)")
melde("nach dem zweiten Durchtritt wieder korrekt",
      abs(weg2 - echt) < echt * 0.02)

print("\n--- 11. Realistische Abtastraten ----------------------------")
# Die Hauptschleife schafft keine 1000 Messungen pro Sekunde. Bei einem
# schnellen Durchtritt liegen mehrere Felder zwischen zwei Messungen.
for rate, name in [(40, "sehr dicht (Testideal)"),
                   (640, "ca. 300 Messungen/s"),
                   (2600, "ca. 75 Messungen/s, schneller Tritt"),
                   (5200, "ca. 37 Messungen/s, sehr schneller Tritt")]:
    h = pedalfahrt(6800, 34000, abwaerts=True, schritt=rate)
    c2 = sweep(6800, h + list(reversed(h)))
    abw = abs(abs(c2["span"]) - echt)
    ok = abw <= SWEEP_BREITE * 2
    print(f"{'ok  ' if ok else 'FEHL'} {name:<38}"
          f" {len(h):>4} Messungen -> {abs(c2['span'])/ADC_SPAN*360:6.1f} Grad")
    if not ok:
        fehler.append("abtastrate " + name)

# Ohne Fuellen der Zwischenstrecke: so sah v9.3 aus
def sweep_ohne_fuellen(zero, verlauf):
    cover = bytearray(SWEEP_FELDER)
    cover[zero >> SWEEP_SHIFT] = 1
    for raw in verlauf:
        cover[raw >> SWEEP_SHIFT] = 1
    return max(sweep_wege(zero, cover))

h = pedalfahrt(6800, 34000, abwaerts=True, schritt=640)
ohne = sweep_ohne_fuellen(6800, h + list(reversed(h)))
print(f"     v9.3 ohne Fuellen bei 300 Messungen/s:"
      f" {ohne/ADC_SPAN*360:.1f} Grad statt {echt/ADC_SPAN*360:.1f}")
melde("ohne Fuellen bleibt der Bogen viel zu kurz", ohne < echt / 4)

print("\n--- 12. Aufloesung der Abdeckungskarte ----------------------")
print(f"     Feldbreite {SWEEP_BREITE} Zaehler = {SWEEP_BREITE/ADC_SPAN*360:.2f} Grad")
c = sweep(6800, hin + zur)
abw = abs(abs(c["span"]) - echt)
print(f"     Abweichung vom echten Weg: {abw} Zaehler"
      f" = {abw/ADC_SPAN*360:.2f} Grad")
melde("Abweichung bleibt unter einer Feldbreite", abw <= SWEEP_BREITE)

print("\n" + "=" * 62)
print("ALLE TESTS BESTANDEN" if not fehler else f"FEHLER: {fehler}")
