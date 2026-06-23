#include <Arduino.h>
#include <WiFi.h>
#include <LittleFS.h>
#include <ArduinoJson.h>
#include <WiFiManager.h>
#include <ESPmDNS.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include <ArduinoOTA.h>

#define SERIAL_BAUD 115200
#define MDNS_NAME "streamdeck"
#define CONFIG_FILE "/config.json"
#define MAX_CONFIG_SIZE 4096
#define LED_PIN 2
#define FACTORY_PIN 0
#define WS_MAX_CLIENTS 8

enum LedPattern { LED_OFF, LED_SOLID, LED_BLINK_FAST, LED_BLINK_SLOW, LED_BREATH, LED_PULSE_ACTION };

static LedPattern ledPattern = LED_BREATH;
static unsigned long lastLedTick = 0;
static bool ledState = false;
static unsigned long lastWsPing = 0;

AsyncWebServer server(80);
AsyncWebSocket ws("/ws");
DynamicJsonDocument configDoc(MAX_CONFIG_SIZE);

void setLedPattern(LedPattern p) {
    ledPattern = p;
}

void updateLed(unsigned long now) {
    bool newState = ledState;
    switch (ledPattern) {
        case LED_OFF:
            newState = false;
            break;
        case LED_SOLID:
            newState = true;
            break;
        case LED_BLINK_FAST:
            if (now - lastLedTick > 100) { newState = !ledState; lastLedTick = now; }
            break;
        case LED_BLINK_SLOW:
            if (now - lastLedTick > 500) { newState = !ledState; lastLedTick = now; }
            break;
        case LED_BREATH: {
            uint8_t duty = (uint8_t)((sin(now / 800.0) + 1.0) * 127.5);
            analogWrite(LED_PIN, duty);
            return;
        }
        case LED_PULSE_ACTION:
            if (now - lastLedTick > 50) {
                newState = !ledState;
                lastLedTick = now;
                if (ledState == false) {
                    setLedPattern(LED_SOLID);
                    return;
                }
            }
            break;
    }
    if (newState != ledState) {
        ledState = newState;
        digitalWrite(LED_PIN, ledState ? HIGH : LOW);
    }
}

void setupFS() {
    if (!LittleFS.begin(true)) {
        Serial.println("[FS] mount failed");
        return;
    }
    Serial.println("[FS] mounted");
    if (!LittleFS.exists(CONFIG_FILE)) {
        Serial.println("[FS] creating default config");
        File f = LittleFS.open(CONFIG_FILE, "w");
        StaticJsonDocument<1024> def;
        JsonArray arr = def.createNestedArray("buttons");
        auto add = [&](int id, const char* label, const char* action, const char* value, const char* color) {
            JsonObject b = arr.createNestedObject();
            b["id"] = id;
            b["label"] = label;
            b["action"] = action;
            b["value"] = value;
            b["color"] = color;
        };
        add(0, "Play/Pause", "PLAY_PAUSE", "", "#e74c3c");
        add(1, "Next", "NEXT_TRACK", "", "#3498db");
        add(2, "Previous", "PREV_TRACK", "", "#3498db");
        add(3, "Vol +", "VOL_UP", "", "#2ecc71");
        add(4, "Vol -", "VOL_DOWN", "", "#2ecc71");
        add(5, "Mute", "MUTE", "", "#f39c12");
        serializeJson(def, f);
        f.close();
    }
}

void loadConfig() {
    File f = LittleFS.open(CONFIG_FILE, "r");
    if (!f) return;
    deserializeJson(configDoc, f);
    f.close();
}

void saveConfig() {
    File f = LittleFS.open(CONFIG_FILE, "w");
    serializeJson(configDoc, f);
    f.close();
}

void sendSerialAction(const char* action, const char* value) {
    if (strlen(value) > 0) {
        Serial.print(action);
        Serial.print("|");
        Serial.println(value);
    } else {
        Serial.println(action);
    }
    Serial.flush();
}

void broadcastConfig() {
    String json;
    serializeJson(configDoc, json);
    ws.textAll(json);
}

void handlePress(int id) {
    JsonArray buttons = configDoc["buttons"].as<JsonArray>();
    for (JsonObject btn : buttons) {
        if (btn["id"] == id) {
            const char* action = btn["action"];
            const char* value = btn["value"] | "";
            sendSerialAction(action, value);
            setLedPattern(LED_PULSE_ACTION);
            return;
        }
    }
}

void onWsEvent(AsyncWebSocket* server, AsyncWebSocketClient* client, AwsEventType type, void* arg, uint8_t* data, size_t len) {
    if (type == WS_EVT_CONNECT) {
        String json;
        serializeJson(configDoc, json);
        client->text(json);
    } else if (type == WS_EVT_DISCONNECT) {
    } else if (type == WS_EVT_DATA) {
        AwsFrameInfo* info = (AwsFrameInfo*)arg;
        if (info->final && info->index == 0 && info->len == len) {
            DynamicJsonDocument doc(256);
            DeserializationError err = deserializeJson(doc, data, len);
            if (err) return;
            const char* type = doc["type"];
            if (!strcmp(type, "press")) {
                handlePress(doc["id"]);
            } else if (!strcmp(type, "save")) {
                JsonArray arr = doc["buttons"].as<JsonArray>();
                if (!arr.isNull()) {
                    configDoc.clear();
                    configDoc["buttons"] = arr;
                    saveConfig();
                    broadcastConfig();
                }
            } else if (!strcmp(type, "set_volume")) {
                int vol = doc["value"];
                char buf[8];
                snprintf(buf, sizeof(buf), "%d", vol);
                sendSerialAction("SET_VOLUME", buf);
            } else if (!strcmp(type, "info")) {
                DynamicJsonDocument info(256);
                info["ip"] = WiFi.localIP().toString();
                info["hostname"] = String(MDNS_NAME) + ".local";
                info["uptime"] = millis() / 1000;
                info["rssi"] = WiFi.RSSI();
                String out;
                serializeJson(info, out);
                client->text(out);
            }
        }
    }
}

void setupOTA() {
    ArduinoOTA.setHostname(MDNS_NAME);
    ArduinoOTA.onStart([]() {
        setLedPattern(LED_BLINK_FAST);
        Serial.println("[OTA] start");
    });
    ArduinoOTA.onEnd([]() {
        setLedPattern(LED_SOLID);
        Serial.println("[OTA] done");
    });
    ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
        Serial.printf("[OTA] %u%%\r", progress / (total / 100));
    });
    ArduinoOTA.onError([](ota_error_t error) {
        Serial.printf("[OTA] error %d\n", error);
        setLedPattern(LED_BLINK_SLOW);
    });
    ArduinoOTA.begin();
}

void setupWiFi() {
    WiFi.mode(WIFI_STA);
    WiFiManager wm;
    wm.setConfigPortalTimeout(180);
    wm.setAPCallback([](WiFiManager* wm) {
        setLedPattern(LED_BLINK_FAST);
        Serial.println("[WiFi] AP mode started");
    });
    bool res = wm.autoConnect("ESP_StreamDeck");
    if (!res) {
        Serial.println("[WiFi] connection failed, restarting...");
        delay(3000);
        ESP.restart();
    }
    Serial.printf("[WiFi] connected, IP: %s\n", WiFi.localIP().toString().c_str());
    setLedPattern(LED_SOLID);
}

void setupMDNS() {
    if (MDNS.begin(MDNS_NAME)) {
        MDNS.addService("http", "tcp", 80);
        MDNS.addService("ws", "tcp", 80);
        Serial.printf("[mDNS] http://%s.local\n", MDNS_NAME);
    }
}

void setupServer() {
    ws.onEvent(onWsEvent);
    server.addHandler(&ws);

    server.on("/api/press", HTTP_GET, [](AsyncWebServerRequest* request) {
        if (!request->hasParam("id")) {
            request->send(400, "text/plain", "missing id");
            return;
        }
        int id = request->getParam("id")->value().toInt();
        handlePress(id);
        request->send(200, "text/plain", "ok");
    });

    server.on("/api/buttons", HTTP_GET, [](AsyncWebServerRequest* request) {
        String json;
        serializeJson(configDoc, json);
        request->send(200, "application/json", json);
    });

    server.on("/api/buttons", HTTP_POST, [](AsyncWebServerRequest* request) {
        String body = request->arg("plain");
        DeserializationError err = deserializeJson(configDoc, body);
        if (err) {
            request->send(400, "text/plain", "invalid json");
            return;
        }
        saveConfig();
        broadcastConfig();
        request->send(200, "text/plain", "saved");
    });

    server.on("/api/info", HTTP_GET, [](AsyncWebServerRequest* request) {
        DynamicJsonDocument doc(256);
        doc["ip"] = WiFi.localIP().toString();
        doc["hostname"] = String(MDNS_NAME) + ".local";
        doc["uptime"] = millis() / 1000;
        doc["rssi"] = WiFi.RSSI();
        doc["version"] = "2.0";
        String json;
        serializeJson(doc, json);
        request->send(200, "application/json", json);
    });

    server.on("/api/restart", HTTP_POST, [](AsyncWebServerRequest* request) {
        request->send(200, "text/plain", "restarting");
        delay(100);
        ESP.restart();
    });

    server.on("/api/factory-reset", HTTP_POST, [](AsyncWebServerRequest* request) {
        LittleFS.remove(CONFIG_FILE);
        request->send(200, "text/plain", "reset, restarting");
        delay(100);
        ESP.restart();
    });

    server.serveStatic("/", LittleFS, "/").setDefaultFile("index.html");

    server.onNotFound([](AsyncWebServerRequest* request) {
        request->send(404, "text/plain", "not found");
    });
}

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(200);
    Serial.println("\n=== Stream Deck v2 ===");

    pinMode(LED_PIN, OUTPUT);
    pinMode(FACTORY_PIN, INPUT_PULLUP);

    if (digitalRead(FACTORY_PIN) == LOW) {
        Serial.println("[FACTORY] GPIO0 held, clearing config...");
        delay(2000);
        if (digitalRead(FACTORY_PIN) == LOW) {
            LittleFS.begin(true);
            LittleFS.remove(CONFIG_FILE);
            Serial.println("[FACTORY] config cleared");
        }
    }

    setupFS();
    loadConfig();
    setupWiFi();
    setupMDNS();
    setupOTA();
    setupServer();
    server.begin();

    Serial.println("[READY] Stream Deck ready!");
}

void loop() {
    unsigned long now = millis();
    updateLed(now);
    ws.cleanupClients();
    ArduinoOTA.handle();

    if (now - lastWsPing > 30000) {
        lastWsPing = now;
        ws.pingAll();
    }
}
