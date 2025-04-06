#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import time
import logging
import sys
from paho.mqtt.client import CallbackAPIVersion

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("mqtt_server.log")]
)
logger = logging.getLogger("MQTTServer")

# --- MQTT Configuration ---
BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC_STATUS = "robot/status"
TOPIC_COMMAND = "robot/command"

robots = {}           # Latest status per robot
position_history = {} # Position history per robot

# --- on_connect callback ---
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Connected to MQTT broker")
        client.subscribe(TOPIC_STATUS)
        logger.info("Subscribed to topic: %s", TOPIC_STATUS)
    else:
        logger.error("Connection error: code %s", rc)

# --- on_message callback ---
def on_message(client, userdata, msg):
    try:
        logger.debug("Message received on topic: %s", msg.topic)
        payload = msg.payload.decode()
        data = json.loads(payload)
        if "data" in data and "sender" in data["data"]:
            sender = data["data"]["sender"]
            location = data["data"]["msg"].get("location", {})
            obstacles = data["data"]["msg"].get("obstacles", [])
            robots[sender] = {
                "location": location,
                "obstacles": obstacles,
                "last_update": time.time()
            }
            if sender not in position_history:
                position_history[sender] = []
            if not position_history[sender] or position_history[sender][-1] != location:
                position_history[sender].append(location)
                if len(position_history[sender]) > 100:
                    position_history[sender].pop(0)
            logger.info("Robot %s: location=%s, obstacles=%s", sender, location, obstacles)
        else:
            logger.warning("Invalid message format: %s", payload)
    except Exception as e:
        logger.error("Error processing message: %s", e)

# --- MQTT Client Setup using Callback API version 2 ---
try:
    client = mqtt.Client(client_id="ServerSubscriber", protocol=mqtt.MQTTv311, callback_api_version=CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)
    client.loop_start()
    logger.info("MQTT client started and listening for messages...")
except Exception as e:
    logger.critical("Critical error starting MQTT client: %s", e)
    sys.exit(1)

try:
    last_summary = time.time()
    while True:
        if time.time() - last_summary >= 10:
            logger.info("=" * 50)
            logger.info("ROBOT STATUS SUMMARY")
            for rid, data in robots.items():
                age = time.time() - data.get("last_update", 0)
                logger.info("Robot %s: location=%s, obstacles=%s, last update: %.1f seconds ago",
                            rid, data.get("location", {}), data.get("obstacles", []), age)
                if rid in position_history:
                    logger.info("  Path length: %s positions", len(position_history[rid]))
            logger.info("=" * 50)
            last_summary = time.time()
        time.sleep(1)
except KeyboardInterrupt:
    logger.info("MQTT server manually stopped")
except Exception as e:
    logger.critical("Unexpected error: %s", e)
finally:
    client.loop_stop()
    client.disconnect()
    logger.info("MQTT server closed")
