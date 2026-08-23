# settings.py - Konfiguration Pico W Pedale Controller v9

# WLAN Access Point
AP_SSID     = "Pico-Pedale"
AP_PASSWORD = "pedale123"   # min. 8 Zeichen, leer = offenes Netz
AP_CHANNEL  = 6

# Webserver
WEB_PORT    = 80

# LED-Pin
LED_PIN     = "GP16"

# WLAN-Taster Pin (muss zu TASTER_PIN in boot.py passen)
WIFI_BTN_PIN = "GP3"

# ADC Pins: [Gas, Bremse, Kupplung]
ADC_PINS   = ["GP26", "GP27", "GP28"]
ACHS_NAMEN = ["Gas", "Bremse", "Kupplung"]

# Bremsentyp: "adc" = AS5600 analog, "hx711" = Waegezelle
BREMSE_TYP = "hx711"

# HX711 Pins (nur relevant wenn BREMSE_TYP = "hx711")
HX711_DT  = "GP1"   # Daten-Pin
HX711_SCK = "GP0"   # Clock-Pin

# Wie der HX711 ausgelesen wird:
#   "pio"     ueber die PIO-Einheit des RP2040. Eine Lesung kostet rund 225 us
#             statt 13,8 ms, damit kommen alle 80 Wandlungen pro Sekunde an und
#             die Hauptschleife blockiert nicht. Braucht adafruit_pioasm in lib/.
#   "bitbang" die alte Variante ueber adafruit_hx711. Nur als Rueckfallebene.
# Bei "pio" schaltet die Firmware automatisch auf "bitbang" um, wenn die
# PIO-Einheit nicht verfuegbar ist - die Konsole sagt dann, warum.
HX711_MODE = "pio"

# ---------------------------------------------------------------------------
# Neu in v9 - alle optional, die Werte hier sind die Defaults
# ---------------------------------------------------------------------------

# Totzone am Pedalanfang in Prozent. Faengt Sensorrauschen ab, damit das
# losgelassene Pedal sicher bei 0 steht. Hoeher setzen, wenn die Anzeige im
# Ruhezustand zappelt; niedriger, wenn das Pedal zu spaet anspricht.
DEADZONE_PCT = 1.5

# Sicherheitsreserve beim Sweep in Prozent. Der gemessene Weg wird um diesen
# Anteil verkuerzt, damit das Pedal am mechanischen Anschlag zuverlaessig
# 100 Prozent erreicht und nicht bei 98 haengen bleibt.
SWEEP_MARGIN_PCT = 2.0

# Startwert fuer die Waegezelle, bevor zum ersten Mal kalibriert wurde.
HX711_MAX_DEFAULT = 50000

# HID auch senden, waehrend der Access Point laeuft. In v8 waren die Pedale
# im WLAN-Modus tot. Auf False setzen, wenn beim Kalibrieren keine Achswerte
# ins Spiel gelangen sollen.
HID_IM_WLAN = True
