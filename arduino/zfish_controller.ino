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

D2   → DS18B20 DATA

GND  → COMMON GROUND (ALL rails)

----------------------------------------------------
SERIAL COMMANDS:
----------------------------------------------------
PING
STATUS
TEMP?

IR <0-255>
WHITE <0-255>
VIB <0-255>
PUMP <0-255>

ALL outputs are PWM controlled.
----------------------------------------------------
*/

#include <OneWire.h>
#include <DallasTemperature.h>

/* ================= PIN DEFINITIONS ================= */
#define PIN_IR        5
#define PIN_WHITE     6
#define PIN_VIB       9
#define PIN_PUMP      10
#define PIN_TEMP      2

/* ================= OBJECTS ================= */
OneWire oneWire(PIN_TEMP);
DallasTemperature tempSensor(&oneWire);

/* ================= STATE ================= */
uint8_t irLevel    = 0;
uint8_t whiteLevel = 0;
uint8_t vibLevel   = 0;
uint8_t pumpLevel  = 0;

/* ================= SETUP ================= */
void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(PIN_IR, OUTPUT);
  pinMode(PIN_WHITE, OUTPUT);
  pinMode(PIN_VIB, OUTPUT);
  pinMode(PIN_PUMP, OUTPUT);

  // SAFE START
  analogWrite(PIN_IR, 0);
  analogWrite(PIN_WHITE, 0);
  analogWrite(PIN_VIB, 0);
  analogWrite(PIN_PUMP, 0);

  tempSensor.begin();

  Serial.println("ZIMON_MEGA_READY");
  Serial.println("Commands: IR, WHITE, VIB, PUMP, TEMP?, STATUS");
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

  if (cmd == "PING") {
    Serial.println("ZIMON_OK");
    return;
  }

  if (cmd == "STATUS") {
    printStatus();
    return;
  }

  if (cmd == "TEMP?") {
    readTemperature();
    return;
  }

  if (cmd.startsWith("IR ")) {
    irLevel = parsePWM(cmd);
    analogWrite(PIN_IR, irLevel);
    Serial.println("IR_OK");
    return;
  }

  if (cmd.startsWith("WHITE ")) {
    whiteLevel = parsePWM(cmd);
    analogWrite(PIN_WHITE, whiteLevel);
    Serial.println("WHITE_OK");
    return;
  }

  if (cmd.startsWith("VIB ")) {
    vibLevel = parsePWM(cmd);
    analogWrite(PIN_VIB, vibLevel);
    Serial.println("VIB_OK");
    return;
  }

  if (cmd.startsWith("PUMP ")) {
    pumpLevel = parsePWM(cmd);
    analogWrite(PIN_PUMP, pumpLevel);
    Serial.println("PUMP_OK");
    return;
  }

  Serial.println("UNKNOWN_CMD");
}

/* ================= HELPERS ================= */
uint8_t parsePWM(String cmd) {
  int idx = cmd.indexOf(' ');
  if (idx < 0) return 0;

  int val = cmd.substring(idx + 1).toInt();
  return constrain(val, 0, 255);
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
  Serial.print(" PUMP="); Serial.println(pumpLevel);
}
