#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import time
import random
import logging
import sys
from controller import Supervisor

# ===============================
# Logging instellen (console + logfile)
# ===============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("robot_controller.log")]
)
logger = logging.getLogger("RobotController")

# ===============================
# Webots initialisatie
# ===============================
try:
    robot = Supervisor()
    supervisorNode = robot.getSelf()
    timestep = int(robot.getBasicTimeStep())
    logger.info("Webots robot succesvol geïnitialiseerd")
except Exception as e:
    logger.error("Fout bij initialisatie van Webots robot: %s", e)
    sys.exit(1)

# ===============================
# Configuratieparameters
# ===============================
STEP_SIZE = 0.1                     # Stapgrootte: precies 0.1 per beweging
OBSTACLE_THRESHOLD = 500            # Als sensorwaarde < 500: obstakel
MIN_BOUND, MAX_BOUND = 0.0, 0.9      # Bewegingsbereik: 0.0 t/m 0.9
START_POS = [0.0, 0.0, 0.0]           # Startpositie (x, y, z)

# Genereer een doelpositie, afgerond op 1 decimaal
TARGET_POS = [round(random.uniform(0.3, 0.7), 1), round(random.uniform(0.3, 0.7), 1)]
logger.info("Robot startpositie: %s", START_POS)
logger.info("Robot doelpositie: %s", TARGET_POS)

# ===============================
# Positie- en rotatievelden instellen
# Zorg dat de robot altijd plat op de grond blijft (geen rotatie)
# ===============================
try:
    trans = supervisorNode.getField("translation")
    rot = supervisorNode.getField("rotation")
    trans.setSFVec3f(START_POS)
    rot.setSFRotation([0, 0, 1, 0])
    logger.info("Translation en rotatie ingesteld")
except Exception as e:
    logger.error("Fout bij instellen van positie/rotatie: %s", e)
    sys.exit(1)

# ===============================
# MQTT-instellingen
# ===============================
BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC_PUBLISH = "robot/status"
TOPIC_SUBSCRIBE = "robot/command"

# ===============================
# Sensoren en LED's initialiseren
# LED's: "RED" = noord, "BLUE" = oost, "YELLOW" = zuid, "GREEN" = west.
# ===============================
try:
    sensor_N = robot.getDevice("DS_N")
    sensor_E = robot.getDevice("DS_E")
    sensor_S = robot.getDevice("DS_S")
    sensor_W = robot.getDevice("DS_W")
    sensor_N.enable(timestep)
    sensor_E.enable(timestep)
    sensor_S.enable(timestep)
    sensor_W.enable(timestep)
    
    led_N = robot.getDevice("RED")
    led_E = robot.getDevice("BLUE")
    led_S = robot.getDevice("YELLOW")
    led_W = robot.getDevice("GREEN")
    
    logger.info("Alle sensoren en LED's succesvol geactiveerd")
except Exception as e:
    logger.error("Fout bij initialisatie van sensoren of LED's: %s", e)
    sys.exit(1)

# ===============================
# MQTT-client aanmaken en verbinden
# ===============================
mqtt_connected = False
try:
    client = mqtt.Client(client_id="WebotsRobot", protocol=mqtt.MQTTv311)
    client.connect(BROKER, PORT)
    mqtt_connected = True
    logger.info("Verbonden met MQTT-broker")
except Exception as e:
    logger.error("Fout bij verbinden met MQTT-broker: %s", e)

if mqtt_connected:
    def on_message(client, userdata, msg):
        try:
            payload = msg.payload.decode()
            logger.info("MQTT bericht ontvangen: %s", payload)
            # Hier kunnen commandos verwerkt worden indien nodig
        except Exception as e:
            logger.error("Fout in on_message: %s", e)
    client.on_message = on_message
    client.subscribe(TOPIC_SUBSCRIBE)
    client.loop_start()

last_sent_position = None

# ===============================
# Functie: Obstakeldetectie
# Leest de sensorwaarden en retourneert een lijst met richtingen (N, E, S, W) waarin een obstakel is (sensor < OBSTACLE_THRESHOLD)
# ===============================
def detect_obstacles():
    try:
        obstacles = []
        dN = sensor_N.getValue()
        dE = sensor_E.getValue()
        dS = sensor_S.getValue()
        dW = sensor_W.getValue()
        if dN < OBSTACLE_THRESHOLD:
            obstacles.append("N")
        if dE < OBSTACLE_THRESHOLD:
            obstacles.append("E")
        if dS < OBSTACLE_THRESHOLD:
            obstacles.append("S")
        if dW < OBSTACLE_THRESHOLD:
            obstacles.append("W")
        logger.info("Sensorwaarden -> N: %.2f, E: %.2f, S: %.2f, W: %.2f", dN, dE, dS, dW)
        if obstacles:
            logger.info("Obstakels gedetecteerd: %s", obstacles)
        else:
            logger.info("Geen obstakels in de buurt")
        return obstacles
    except Exception as e:
        logger.error("Fout bij obstakeldetectie: %s", e)
        return []

# ===============================
# Functie: LED's uitschakelen (alle LED's op 0)
# ===============================
def turn_leds_off():
    try:
        led_N.set(0)
        led_E.set(0)
        led_S.set(0)
        led_W.set(0)
        logger.info("Alle LED's uitgeschakeld (doel bereikt)")
    except Exception as e:
        logger.error("Fout bij uitschakelen LED's: %s", e)

# ===============================
# Functie: Statusversturing via MQTT
# Verstuurd statusupdate met de actuele positie (x,y, afgerond op 1 decimaal) en obstakeldetectie.
# Verstuur alleen als positie is gewijzigd
# ===============================
def send_status():
    global last_sent_position
    if not mqtt_connected:
        return
    try:
        pos = trans.getSFVec3f()  # [x, y, z]
        x_pos = round(pos[0], 1)
        y_pos = round(pos[1], 1)
        current_pos = (x_pos, y_pos)
        if last_sent_position == current_pos:
            return
        last_sent_position = current_pos

        statusbericht = {
            "protocolVersion": 1.0,
            "data": {
                "sender": "bot1",
                "target": "server",
                "msg": {
                    "location": {"x": x_pos, "y": y_pos},
                    "obstacles": detect_obstacles()
                }
            }
        }
        payload = json.dumps(statusbericht)
        client.publish(TOPIC_PUBLISH, payload)
        logger.info("Status update verzonden: %s", payload)
    except Exception as e:
        logger.error("Fout bij verzenden statusupdate: %s", e)

# ===============================
# Functie: Proces van binnenkomende commando's
# ===============================
def process_command(command):
    try:
        direction = command["data"]["msg"].get("direction", "")
        if direction:
            logger.info("Commando ontvangen: Beweeg naar %s", direction)
    except Exception as e:
        logger.error("Fout bij verwerken commando: %s", e)

# ===============================
# Functie: Positie instellen (alleen x en y, afgerond op 1 decimaal)
# Houdt de z-waarde en de vaste rotatie (robot blijft plat)
# ===============================
def set_position(x, y):
    try:
        new_x = round(x, 1)
        new_y = round(y, 1)
        new_x = min(max(new_x, MIN_BOUND), MAX_BOUND)
        new_y = min(max(new_y, MIN_BOUND), MAX_BOUND)
        current = trans.getSFVec3f()  # [x, y, z]
        trans.setSFVec3f([new_x, new_y, current[2]])
        rot.setSFRotation([0, 0, 1, 0])
        return True
    except Exception as e:
        logger.error("Fout bij instellen positie: %s", e)
        return False

# ===============================
# Functie: Alternatieve richting kiezen
# Als de primaire richting (gebaseerd op doel) geblokkeerd is, kies om de robot de andere as op
# ===============================
def choose_alternative_direction(primary, obstacles):
    if primary in ["E", "W"]:
        if "N" not in obstacles:
            return "N"
        elif "S" not in obstacles:
            return "S"
    elif primary in ["N", "S"]:
        if "E" not in obstacles:
            return "E"
        elif "W" not in obstacles:
            return "W"
    return None

# ===============================
# Functie: Beweeg één stap richting TARGET_POS met obstakeldetectie
# Indien het doel bereikt is, zet LED's uit (stop meldingen)
# ===============================
def move_to_target():
    try:
        pos = trans.getSFVec3f()
        current_x = round(pos[0], 1)
        current_y = round(pos[1], 1)
        target_x, target_y = TARGET_POS

        # Als binnen een stapgrootte, beschouw doel als bereikt en schakel LED's uit.
        if abs(current_x - target_x) < STEP_SIZE and abs(current_y - target_y) < STEP_SIZE:
            logger.info("Doel bereikt!")
            turn_leds_off()
            return

        dx = target_x - current_x
        dy = target_y - current_y

        # Kies primaire richting op basis van grootste afstand
        if abs(dx) >= abs(dy):
            primary = "E" if dx > 0 else "W"
        else:
            primary = "N" if dy > 0 else "S"

        obstacles = detect_obstacles()
        chosen_direction = primary
        if primary in obstacles:
            alternative = choose_alternative_direction(primary, obstacles)
            if alternative:
                logger.info("Primaire richting %s is geblokkeerd; alternatieve richting: %s", primary, alternative)
                chosen_direction = alternative
            else:
                logger.warning("Geen alternatieve richting beschikbaar; geen beweging")
                return

        new_x, new_y = current_x, current_y
        if chosen_direction == "E":
            new_x += STEP_SIZE
        elif chosen_direction == "W":
            new_x -= STEP_SIZE
        elif chosen_direction == "N":
            new_y += STEP_SIZE
        elif chosen_direction == "S":
            new_y -= STEP_SIZE

        if set_position(new_x, new_y):
            # Activeer de LED voor de gekozen richting
            led_N.set(1 if chosen_direction == "N" else 0)
            led_E.set(1 if chosen_direction == "E" else 0)
            led_S.set(1 if chosen_direction == "S" else 0)
            led_W.set(1 if chosen_direction == "W" else 0)
            logger.info("Beweeg naar %s: nieuwe positie = (%.1f, %.1f)", chosen_direction, new_x, new_y)
    except Exception as e:
        logger.error("Fout bij beweging naar doel: %s", e)

# ===============================
# Hoofdloop met timer: Één beweging + statusupdate per seconde
# ===============================
logger.info("Simulatie gestart")
last_movement_time = time.time()

try:
    while robot.step(timestep) != -1:
        current_time = time.time()
        # Voer beweging en statusupdate zodra 1 seconde verstreken is
        if current_time - last_movement_time >= 1.0:
            move_to_target()
            send_status()
            last_movement_time = current_time
        time.sleep(0.1)
except KeyboardInterrupt:
    logger.info("Simulatie handmatig onderbroken")
except Exception as e:
    logger.critical("Onverwachte fout: %s", e)
finally:
    if mqtt_connected:
        client.loop_stop()
        client.disconnect()
    logger.info("Simulatie beëindigd")
