#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import random
import time
import logging
import sys
from paho.mqtt.client import CallbackAPIVersion

# ===============================
# Logging instellen (console + logfile)
# ===============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("mqtt_server.log")]
)
logger = logging.getLogger("MQTTServer")

# ===============================
# MQTT Configuratie
# ===============================
BROKER = "mosquitto"  # Use the service name defined in docker-compose.yml
PORT = 1883           # Default MQTT port
TOPIC_STATUS = "robot/status"
TOPIC_COMMAND = "robot/command"

robots = {}           # Laatste status per robot
position_history = {} # Historie van robotposities

# ===============================
# Callback: Verbinden met de broker
# Deze callback accepteert nu vijf parameters (properties is optioneel) om de deprecated-warning te vermijden.
# ===============================
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Verbonden met MQTT-broker")
        client.subscribe(TOPIC_STATUS)
        logger.info("Geabonneerd op topic: %s", TOPIC_STATUS)
    else:
        logger.error("Verbindingsfout, code: %s", rc)

# ===============================
# Callback: Binnenkomende berichten verwerken
# ===============================
def on_message(client, userdata, msg):
    try:
        logger.debug("Bericht ontvangen op topic: %s", msg.topic)
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
            logger.info("Robot %s: locatie=%s, obstakels=%s", sender, location, obstacles)
            
            # Kies een vrije richting en stuur een commando terug
            direction = choose_direction(sender)
            send_command(sender, direction)
        else:
            logger.warning("Ongeldig berichtformaat: %s", payload)
    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s", e)
    except Exception as e:
        logger.error("Fout bij verwerken bericht: %s", e)

# ===============================
# Functie: Beschikbare richting kiezen op basis van obstakels
# ===============================
def choose_direction(robot_id):
    directions = ["N", "S", "E", "W"]
    if robot_id in robots:
        obs = robots[robot_id].get("obstacles", [])
        available = [d for d in directions if d not in obs]
        if available:
            return random.choice(available)
        else:
            logger.warning("Robot %s heeft geen vrije richting", robot_id)
            return ""
    else:
        return random.choice(directions)

# ===============================
# Functie: Commando versturen naar een robot
# ===============================
def send_command(bot_id, direction):
    try:
        if not direction:
            return
        command = {
            "protocolVersion": 1.0,
            "data": {
                "sender": "server",
                "target": bot_id,
                "msg": {"direction": direction}
            }
        }
        payload = json.dumps(command)
        result = client.publish(TOPIC_COMMAND, payload)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info("Commando verzonden naar %s: Beweeg %s", bot_id, direction)
        else:
            logger.error("Fout bij verzenden commando naar %s: rc=%s", bot_id, result.rc)
    except Exception as e:
        logger.error("Fout bij verzenden commando: %s", e)

# ===============================
# Functie: Periodieke samenvatting van robotstatus tonen
# ===============================
def show_robot_summary():
    logger.info("=" * 50)
    logger.info("SAMENVATTING ROBOTSTATUS")
    logger.info("=" * 50)
    for rid, data in robots.items():
        age = time.time() - data.get("last_update", 0)
        logger.info("Robot %s: locatie=%s, obstakels=%s, laatste update: %.1f seconden geleden", 
                    rid, data.get("location", {}), data.get("obstacles", []), age)
        if rid in position_history:
            logger.info("  Afgelegde pad: %s posities", len(position_history[rid]))
    logger.info("=" * 50)

# ===============================
# MQTT Client Setup met Callback API versie 2 (om deprecated warnings te vermijden)
# ===============================
try:
    client = mqtt.Client(client_id="ServerSubscriber", protocol=mqtt.MQTTv311, callback_api_version=CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)
    client.loop_start()
    logger.info("MQTT client gestart en luistert naar berichten...")
except Exception as e:
    logger.critical("Kritieke fout bij starten MQTT-client: %s", e)
    sys.exit(1)

# ===============================
# Hoofdlus: Toon elke 10 seconden een samenvatting
# ===============================
try:
    last_summary = time.time()
    while True:
        if time.time() - last_summary >= 10:
            show_robot_summary()
            last_summary = time.time()
        time.sleep(1)
except KeyboardInterrupt:
    logger.info("Server handmatig gestopt")
except Exception as e:
    logger.critical("Onverwachte fout: %s", e)
finally:
    client.loop_stop()
    client.disconnect()
    logger.info("MQTT-server afgesloten")
