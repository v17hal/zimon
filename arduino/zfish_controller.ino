/*
====================================================
 ZIMON Behaviour System – Arduino Mega Firmware
====================================================

PIN MAP (LOCKED):
--------------------------------
D5   → IR LED (12V MOSFET)
D6   → WHITE LED (12V MOSFET)
D9   → VIBRATION MOTOR (5V via buck)
D10  → CIRCULATION PUMP (12V)
D7   → HEATER (relay / MOSFET)

D2   → DS18B20 DATA

GND  → COMMON GROUND (ALL rails)

----------------------------------------------------
SERIAL COMMANDS (115200 baud):
----------------------------------------------------
PING               → ZIMON_OK
STATUS             → STATUS IR=x WHITE=x VIB=x PUMP=x HEAT=x
TEMP?              → TEMP_C xx.xx  (or TEMP_ERR)

IR    <0-255>      → IR_OK
WHITE <0-255>      → WHITE_OK
VIB   <0-255>      → VIB_OK
PUMP  <0-255>      → PUMP_OK
HEAT  <0-255>      → HEAT_OK

BUZZER_ON          → BUZZER_OK
BUZZER_OFF         → BUZZER_OK

All PWM outputs: 0 = off, 255 = full power.
----------------------------------------------------
*/

#include <OneWire.h>
#include <DallasTemperature.h>

/* ================= PIN DEFINITIONS ================= */
#define PIN_IR        5
#define PIN_WHITE     6
#define PIN_HEAT      7    // Heater on D7
#define PIN_VIB       9
#define PIN_PUMP      10
#define PIN_BUZZER    11   // Buzzer/tone output
#define PIN_TEMP      2    // DS18B20 data

/* ================= OBJECTS ================= */
OneWire oneWire(PIN_TEMP);
DallasTemperature tempSensor(&oneWire);

/* ================= STATE ================= */
uint8_t irLevel    = 0;
uint8_t whiteLevel = 0;
uint8_t vibLevel   = 0;
uint8_t pumpLevel  = 0;
uint8_t heatLevel  = 0;
bool    buzzerOn   = false;

/* ================= SETUP ================= */
void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(PIN_IR,     OUTPUT);
  pinMode(PIN_WHITE,  OUTPUT);
  pinMode(PIN_HEAT,   OUTPUT);
  pinMode(PIN_VIB,    OUTPUT);
  pinMode(PIN_PUMP,   OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  // Safe start — all outputs off
  analogWrite(PIN_IR,    0);
  analogWrite(PIN_WHITE, 0);
  digitalWrite(PIN_HEAT, LOW);
  analogWrite(PIN_VIB,   0);
  analogWrite(PIN_PUMP,  0);
  digitalWrite(PIN_BUZZER, LOW);

  tempSensor.begin();

  Serial.println("ZIMON_MEGA_READY");
  Serial.println("Commands: IR, WHITE, VIB, PUMP, HEAT, BUZZER_ON/OFF, TEMP?, STATUS, PING");
}

/* ================= MAIN LOOP ================= */
void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();
    processCommand(cmd);
  }
}

/* ================= COMMAND HANDLER ================= */
void processCommand(String cmd) {

  // ── Connectivity ──────────────────────────────────
  if (cmd == "PING") {
    Serial.println("ZIMON_OK");
    return;
  }

  if (cmd == "STATUS") {
    printStatus();
    return;
  }

  // ── Temperature ───────────────────────────────────
  if (cmd == "TEMP?") {
    readTemperature();
    return;
  }

  // ── IR LED ────────────────────────────────────────
  if (cmd.startsWith("IR ")) {
    irLevel = parsePWM(cmd);
    analogWrite(PIN_IR, irLevel);
    Serial.println("IR_OK");
    return;
  }

  // ── White LED ─────────────────────────────────────
  if (cmd.startsWith("WHITE ")) {
    whiteLevel = parsePWM(cmd);
    analogWrite(PIN_WHITE, whiteLevel);
    Serial.println("WHITE_OK");
    return;
  }

  // ── Vibration Motor ───────────────────────────────
  if (cmd.startsWith("VIB ")) {
    vibLevel = parsePWM(cmd);
    analogWrite(PIN_VIB, vibLevel);
    Serial.println("VIB_OK");
    return;
  }

  // ── Circulation Pump ──────────────────────────────
  if (cmd.startsWith("PUMP ")) {
    pumpLevel = parsePWM(cmd);
    analogWrite(PIN_PUMP, pumpLevel);
    Serial.println("PUMP_OK");
    return;
  }

  // ── Heater (D7) ───────────────────────────────────
  if (cmd.startsWith("HEAT ")) {
    heatLevel = parsePWM(cmd);
    // D7 is PWM-capable on Mega; use analogWrite for variable power
    analogWrite(PIN_HEAT, heatLevel);
    Serial.println("HEAT_OK");
    return;
  }

  // ── Buzzer ────────────────────────────────────────
  if (cmd == "BUZZER_ON") {
    buzzerOn = true;
    digitalWrite(PIN_BUZZER, HIGH);
    Serial.println("BUZZER_OK");
    return;
  }

  if (cmd == "BUZZER_OFF") {
    buzzerOn = false;
    digitalWrite(PIN_BUZZER, LOW);
    Serial.println("BUZZER_OK");
    return;
  }

  // ── RGB (alias — maps to WHITE for now; extend with RGB strip later) ──
  if (cmd.startsWith("RGB ")) {
    // Format: RGB r g b  (0-255 each)
    // For single-channel systems, use max of r/g/b as white level
    int s1 = cmd.indexOf(' ', 4);
    int s2 = cmd.indexOf(' ', s1 + 1);
    if (s1 > 0 && s2 > 0) {
      int r = cmd.substring(4, s1).toInt();
      int g = cmd.substring(s1+1, s2).toInt();
      int b = cmd.substring(s2+1).toInt();
      whiteLevel = (uint8_t)max(max(r, g), b);
      analogWrite(PIN_WHITE, whiteLevel);
    }
    Serial.println("RGB_OK");
    return;
  }

  Serial.println("UNKNOWN_CMD");
}

/* ================= HELPERS ================= */
uint8_t parsePWM(String cmd) {
  int idx = cmd.indexOf(' ');
  if (idx < 0) return 0;
  int val = cmd.substring(idx + 1).toInt();
  return (uint8_t)constrain(val, 0, 255);
}

void readTemperature() {
  tempSensor.requestTemperatures();
  float t = tempSensor.getTempCByIndex(0);
  if (t == DEVICE_DISCONNECTED_C) {
    Serial.println("TEMP_ERR");
  } else {
    Serial.print("TEMP_C ");
    Serial.println(t, 2);
  }
}

void printStatus() {
  Serial.print("STATUS ");
  Serial.print("IR=");    Serial.print(irLevel);
  Serial.print(" WHITE=");Serial.print(whiteLevel);
  Serial.print(" VIB=");  Serial.print(vibLevel);
  Serial.print(" PUMP="); Serial.print(pumpLevel);
  Serial.print(" HEAT="); Serial.print(heatLevel);
  Serial.print(" BUZZ="); Serial.println(buzzerOn ? 1 : 0);
}
