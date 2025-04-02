/*
  tinbot.ino
  (ESP32 code)
  TINCOS project
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include "credentials.h" // your WiFi SSID/PASS

#define BOT_ID "tinbot1_physical"
#define BROKER "broker.emqx.io"
#define TOPIC  "TINCOSProject/comms"

WiFiClient espClient;
PubSubClient client(espClient);

// Pins
#define LED_N 32
#define LED_E 14
#define LED_S 33
#define LED_W 25
#define BTN_STOP 2

bool emergencyStop = false;

void setup() {
  Serial.begin(115200);
  pinMode(LED_N, OUTPUT);
  pinMode(LED_E, OUTPUT);
  pinMode(LED_S, OUTPUT);
  pinMode(LED_W, OUTPUT);
  pinMode(BTN_STOP, INPUT_PULLUP);

  connectWifi();
  client.setServer(BROKER, 1883);
  client.setCallback(callback);

  // optional: calibrateLEDs();
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // check button
  if (digitalRead(BTN_STOP) == LOW && !emergencyStop) {
    // user pressed emergency stop
    emergencyStop = true;
    publishEmergency();
  }
  delay(50); // small cooldown
}

void callback(char* topic, byte* message, unsigned int length) {
  String msg;
  for (int i = 0; i < length; i++) {
    msg += (char)message[i];
  }
  // parse JSON
  // check if "target" = BOT_ID, then read "direction"/"ledStatus"
  // update LEDS
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(MY_SSID, MY_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  Serial.println("Wifi connected.");
}

void reconnect() {
  while (!client.connected()) {
    if (client.connect(BOT_ID)) {
      client.subscribe(TOPIC);
    } else {
      delay(1000);
    }
  }
}

void publishEmergency() {
  String message = "{\"protocolVersion\":1.0,\"data\":{\"sender\":\"";
  message += BOT_ID;
  message += "\",\"emergency\":1}}";
  client.publish(TOPIC, message.c_str());
}

