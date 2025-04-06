import paho.mqtt.client as mqtt
import json
import time
import random
import logging
import sys
from controller import Supervisor

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("robot_controller.log")]
)
logger = logging.getLogger("RobotController")

# --- Webots initialization ---
try:
    robot = Supervisor()
    supervisorNode = robot.getSelf()
    timestep = int(robot.getBasicTimeStep())
    logger.info("Webots robot succesvol geïnitialiseerd")
except Exception as e:
    logger.error("Fout bij initialisatie Webots robot: %s", e)
    sys.exit(1)

STEP_SIZE = 0.1  # Beweegstap
OBSTACLE_THRESHOLD = 450
MIN_BOUND, MAX_BOUND = 0.0, 0.9
START_POS = [0.0, 0.0, 0.0]
TARGET_POS = [
    round(random.uniform(0.3, 0.7), 1),
    round(random.uniform(0.3, 0.7), 1)
]
logger.info("Startpositie: %s", START_POS)
logger.info("Doelpositie: %s", TARGET_POS)

# --- Set translation and rotation ---
try:
    trans = supervisorNode.getField("translation")
    rot = supervisorNode.getField("rotation")
    trans.setSFVec3f(START_POS)
    rot.setSFRotation([0, 0, 1, 0])
    logger.info("Vertaling en rotatie ingesteld")
except Exception as e:
    logger.error("Fout bij instellen positie/rotatie: %s", e)
    sys.exit(1)

# --- MQTT settings ---
BROKER = "test.mosquitto.org"  # Publieke broker
PORT = 1883
TOPIC_PUBLISH = "robot/status"

# --- Initialize sensors and LEDs ---
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
    logger.info("Sensores en LED's succesvol geïnitialiseerd")
except Exception as e:
    logger.error("Fout bij initialisatie sensoren/LED's: %s", e)
    sys.exit(1)

mqtt_connected = False
try:
    client = mqtt.Client(client_id="WebotsRobot", protocol=mqtt.MQTTv311)
    client.connect(BROKER, PORT)
    mqtt_connected = True
    logger.info("Verbonden met MQTT-broker")
except Exception as e:
    logger.error("Fout bij verbinden met MQTT-broker: %s", e)

if mqtt_connected:
    client.loop_start()

last_sent_position = None

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
        return obstacles
    except Exception as e:
        logger.error("Fout bij obstakel detectie: %s", e)
        return []

def turn_leds_off():
    try:
        led_N.set(0)
        led_E.set(0)
        led_S.set(0)
        led_W.set(0)
        logger.info("Alle LED's uitgeschakeld")
    except Exception as e:
        logger.error("Fout bij uitschakelen LED's: %s", e)

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
        status_message = {
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
        letPayload = json.dumps(status_message)
        client.publish(TOPIC_PUBLISH, letPayload)
        logger.info("Statusbericht verzonden: %s", letPayload)
    except Exception as e:
        logger.error("Fout bij verzenden status: %s", e)

def set_position(x, y):
    try:
        new_x = round(x, 1)
        new_y = round(y, 1)
        new_x = min(max(new_x, MIN_BOUND), MAX_BOUND)
        new_y = min(max(new_y, MIN_BOUND), MAX_BOUND)
        current = trans.getSFVec3f()
        trans.setSFVec3f([new_x, new_y, current[2]])
        rot.setSFRotation([0, 0, 1, 0])
        return True
    except Exception as e:
        logger.error("Fout bij instellen positie: %s", e)
        return False

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

def move_to_target():
    try:
        pos = trans.getSFVec3f()
        current_x = round(pos[0], 1)
        current_y = round(pos[1], 1)
        target_x, target_y = TARGET_POS
        if abs(current_x - target_x) < STEP_SIZE and abs(current_y - target_y) < STEP_SIZE:
            logger.info("Doel bereikt!")
            turn_leds_off()
            return
        dx = target_x - current_x
        dy = target_y - current_y
        primary = "E" if abs(dx) >= abs(dy) and dx > 0 else "W" if abs(dx) >= abs(dy) else "N" if dy > 0 else "S"
        obstacles = detect_obstacles()
        chosen_direction = primary
        if primary in obstacles:
            alt = choose_alternative_direction(primary, obstacles)
            if alt:
                logger.info("Primaire richting %s geblokkeerd, alternatief %s gekozen", primary, alt)
                chosen_direction = alt
            else:
                logger.warning("Geen vrije richting beschikbaar; geen beweging")
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
            led_N.set(1 if chosen_direction == "N" else 0)
            led_E.set(1 if chosen_direction == "E" else 0)
            led_S.set(1 if chosen_direction == "S" else 0)
            led_W.set(1 if chosen_direction == "W" else 0)
            logger.info("Beweeg %s: nieuwe positie = (%.1f, %.1f)", chosen_direction, new_x, new_y)
    except Exception as e:
        logger.error("Fout tijdens bewegen: %s", e);

logger.info("Simulatie gestart");
last_movement_time = time.time()

try:
    while robot.step(timestep) != -1:
        current_time = time.time()
        if (current_time - last_movement_time >= 1.0):
            move_to_target();
            send_status();
            last_movement_time = current_time;
        time.sleep(0.1);
except KeyboardInterrupt:
    logger.info("Simulatie handmatig gestopt");
except Exception as e:
    logger.critical("Onverwachte fout: %s", e);
finally:
    if (mqtt_connected):
        client.loop_stop();
        client.disconnect();
    logger.info("Simulatie beëindigd");
