#!/usr/bin/env python3
"""
Webots robot controller voor Connected Systems.
Deze controller:
- Beweegt de robot naar de doelpositie
- Detecteert obstakels met sensoren
- Communiceert via MQTT met de server
- Handelt MOVE en EMERGENCY_STOP commando's af
"""
import paho.mqtt.client as mqtt
import json
import time
import random
import logging
import sys
from controller import Supervisor

# --- Logging configuratie ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("robot_controller.log")]
)
logger = logging.getLogger("RobotController")

# --- Webots initialisatie ---
try:
    robot = Supervisor()
    supervisorNode = robot.getSelf()
    timestep = int(robot.getBasicTimeStep())
    logger.info("Webots robot succesvol geïnitialiseerd")
except Exception as e:
    logger.error("Fout bij initialisatie van Webots robot: %s", e)
    sys.exit(1)

# --- Constanten en configuratie ---
STEP_SIZE = 0.1  # Beweegstap in Webots (0.1 per iteratie)
OBSTACLE_THRESHOLD = 450  # Drempelwaarde voor obstakeldetectie
MIN_BOUND, MAX_BOUND = 0.0, 0.9  # Bewegingsgrenzen in de Webots-wereld
START_POS = [0.0, 0.0, 0.0]  # Startpositie [x, y, z]
# Willekeurige startdoelpositie binnen grenzen
TARGET_POS = [
    round(random.uniform(0.3, 0.7), 1),
    round(random.uniform(0.3, 0.7), 1)
]
# Globale variabele voor noodstop
emergency_stop = False
# Robot ID (kan worden aangepast indien nodig)
ROBOT_ID = "bot1"

logger.info("Configuratie: START_POS=%s, TARGET_POS=%s", START_POS, TARGET_POS)

# --- Positie en rotatie instellen ---
try:
    trans = supervisorNode.getField("translation")
    rot = supervisorNode.getField("rotation")
    trans.setSFVec3f(START_POS)
    rot.setSFRotation([0, 0, 1, 0])
    logger.info("Positie en rotatie succesvol ingesteld")
except Exception as e:
    logger.error("Fout bij instellen positie/rotatie: %s", e)
    sys.exit(1)

# --- MQTT instellingen ---
BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC_PUBLISH = "robot/status"
TOPIC_COMMAND = "robot/command"

# --- Sensoren en LEDs initialiseren ---
try:
    # Sensoren
    sensor_N = robot.getDevice("DS_N")
    sensor_E = robot.getDevice("DS_E")
    sensor_S = robot.getDevice("DS_S")
    sensor_W = robot.getDevice("DS_W")
    sensor_N.enable(timestep)
    sensor_E.enable(timestep)
    sensor_S.enable(timestep)
    sensor_W.enable(timestep)
    
    # LEDs
    led_N = robot.getDevice("RED")
    led_E = robot.getDevice("BLUE")
    led_S = robot.getDevice("YELLOW")
    led_W = robot.getDevice("GREEN")
    logger.info("Sensoren en LED's succesvol geïnitialiseerd")
except Exception as e:
    logger.error("Fout bij initialisatie sensoren/LED's: %s", e)
    sys.exit(1)

# --- Validatiefuncties ---
def validate_coordinates(x, y):
    """
    Valideer en corrigeer coördinaten:
    - Omzetten naar positieve waarden
    - Binnen grenzen houden
    - Afronden op 1 decimaal voor consistente stappen
    """
    # Coördinaten nooit negatief
    x = abs(x)
    y = abs(y)
    # Binnen grenzen houden
    x = min(max(x, MIN_BOUND), MAX_BOUND)
    y = min(max(y, MIN_BOUND), MAX_BOUND)
    # Afronden op 1 decimaal voor consistente stappen
    x = round(x, 1)
    y = round(y, 1)
    
    logger.debug("Coördinaten gevalideerd: (%f, %f) -> (%f, %f)", x, y, x, y)
    return x, y

# --- MQTT verbinding opzetten ---
mqtt_connected = False
try:
    client = mqtt.Client(client_id=f"WebotsRobot_{ROBOT_ID}", protocol=mqtt.MQTTv311)
    client.connect(BROKER, PORT)
    mqtt_connected = True
    logger.info("Verbonden met MQTT-broker %s:%d", BROKER, PORT)
except Exception as e:
    logger.error("Fout bij verbinden met MQTT-broker: %s", e)

# --- MQTT commando verwerking functie ---
def on_command(client, userdata, msg):
    """
    Verwerk inkomende MQTT commando's:
    - EMERGENCY_STOP: Zet noodstop aan
    - RESUME: Zet noodstop uit
    - MOVE: Verplaats naar nieuwe positie (als er geen noodstop actief is)
    """
    global TARGET_POS, emergency_stop
    
    try:
        logger.info("MQTT bericht ontvangen op %s", msg.topic)
        # Bericht decoderen en parsen
        payload = msg.payload.decode()
        logger.debug("Ontvangen payload: %s", payload)
        
        command_data = json.loads(payload)
        logger.info("MQTT commando ontvangen: %s", command_data)
        
        if "data" in command_data:
            # Controleer of dit commando voor deze robot is bedoeld
            target = command_data["data"].get("target")
            if target not in [ROBOT_ID, "all"]:
                logger.info("Commando niet voor deze robot (target: %s)", target)
                return
                
            # Haal bericht uit commando
            msg_content = command_data["data"].get("msg")
            
            # Verwerk EMERGENCY_STOP commando (hoogste prioriteit)
            if msg_content == "EMERGENCY_STOP":
                logger.warning("NOODSTOP GEACTIVEERD - robot stopt onmiddellijk")
                emergency_stop = True
                # Zet doelpositie op huidige positie om stil te staan
                pos = trans.getSFVec3f()
                TARGET_POS = [round(pos[0], 1), round(pos[1], 1)]
                # Leds uit
                turn_leds_off()
                return
            
            # Verwerk RESUME commando (om noodstop op te heffen)
            if msg_content == "RESUME":
                logger.info("NOODSTOP gedeactiveerd - robot kan weer bewegen")
                emergency_stop = False
                return
                
            # Verwerk MOVE commando (alleen als er geen noodstop actief is)
            if not emergency_stop and isinstance(msg_content, dict) and msg_content.get("command") == "MOVE":
                target_pos = msg_content.get("target")
                if target_pos and "x" in target_pos and "y" in target_pos:
                    try:
                        # Valideer de doelcoördinaten
                        x = float(target_pos["x"])
                        y = float(target_pos["y"])
                        x, y = validate_coordinates(x, y)
                        
                        logger.info("MOVE commando ontvangen - nieuwe doelpositie: (%f, %f)", x, y)
                        TARGET_POS = [x, y]
                    except ValueError as ve:
                        logger.error("Ongeldige coördinaten in MOVE commando: %s", ve)
                    return
    except json.JSONDecodeError as je:
        logger.error("Ongeldig JSON formaat in MQTT bericht: %s", je)
    except Exception as e:
        logger.error("Fout bij verwerken van MQTT commando: %s", e)

if mqtt_connected:
    # Abonneer op commando topic en start MQTT loop
    client.subscribe(TOPIC_COMMAND)
    client.message_callback_add(TOPIC_COMMAND, on_command)
    client.loop_start()
    logger.info("Geabonneerd op topic: %s", TOPIC_COMMAND)

# Bijhouden van laatste verzonden positie
last_sent_position = None

# --- Detecteer obstakels met sensoren ---
def detect_obstacles():
    """
    Lees sensorwaarden en bepaal in welke richtingen obstakels zijn.
    Geeft een lijst terug met richting ("N", "E", "S", "W") voor elke geblokkeerde richting.
    """
    try:
        obstacles = []
        # Lees sensorwaarden
        dN = sensor_N.getValue()
        dE = sensor_E.getValue()
        dS = sensor_S.getValue()
        dW = sensor_W.getValue()
        
        # Bepaal per richting of er een obstakel is
        if dN < OBSTACLE_THRESHOLD:
            obstacles.append("N")
        if dE < OBSTACLE_THRESHOLD:
            obstacles.append("E")
        if dS < OBSTACLE_THRESHOLD:
            obstacles.append("S")
        if dW < OBSTACLE_THRESHOLD:
            obstacles.append("W")
            
        logger.debug("Sensorwaarden -> N: %.2f, E: %.2f, S: %.2f, W: %.2f", dN, dE, dS, dW)
        return obstacles
    except Exception as e:
        logger.error("Fout bij obstakeldetectie: %s", e)
        return []

# --- Schakel alle LEDs uit ---
def turn_leds_off():
    """Schakel alle LED-indicators uit"""
    try:
        led_N.set(0)
        led_E.set(0)
        led_S.set(0)
        led_W.set(0)
        logger.debug("Alle LED's uitgeschakeld")
    except Exception as e:
        logger.error("Fout bij uitschakelen LED's: %s", e)

# --- Stuur status via MQTT ---
def send_status():
    """
    Stuur de huidige robotstatus naar de MQTT broker.
    Verstuurt alleen als de positie is veranderd sinds laatste keer.
    """
    global last_sent_position
    
    if not mqtt_connected:
        logger.warning("Kan status niet versturen: geen MQTT verbinding")
        return
        
    try:
        # Huidige positie ophalen
        pos = trans.getSFVec3f()  # [x, y, z]
        x_pos = round(pos[0], 1)
        y_pos = round(pos[1], 1)
        current_pos = (x_pos, y_pos)
        
        # Alleen versturen als positie is veranderd
        if last_sent_position == current_pos:
            logger.debug("Positie ongewijzigd, geen update verstuurd")
            return
            
        last_sent_position = current_pos
        
        # Status bericht samenstellen
        status_message = {
            "protocolVersion": 1.0,
            "data": {
                "sender": ROBOT_ID,
                "target": "server",
                "msg": {
                    "location": {"x": x_pos, "y": y_pos},
                    "obstacles": detect_obstacles(),
                    "emergency": emergency_stop
                }
            }
        }
        
        # Naar JSON en versturen
        payload = json.dumps(status_message)
        client.publish(TOPIC_PUBLISH, payload)
        logger.info("Statusbericht verzonden: positie=(%f, %f), noodstop=%s", 
                   x_pos, y_pos, emergency_stop)
    except Exception as e:
        logger.error("Fout bij verzenden status: %s", e)

# --- Stel positie in ---
def set_position(x, y):
    """
    Stel de positie van de robot in.
    Valideert coördinaten en houdt de robot binnen de grenzen.
    """
    try:
        # Valideer en rond af
        new_x = round(x, 1)
        new_y = round(y, 1)
        
        # Houd binnen grenzen
        new_x = min(max(new_x, MIN_BOUND), MAX_BOUND)
        new_y = min(max(new_y, MIN_BOUND), MAX_BOUND)
        
        # Behoud huidige z-coördinaat
        current = trans.getSFVec3f()
        trans.setSFVec3f([new_x, new_y, current[2]])
        
        # Behoud rotatie (kijkend naar boven)
        rot.setSFRotation([0, 0, 1, 0])
        
        logger.debug("Positie ingesteld: (%f, %f)", new_x, new_y)
        return True
    except Exception as e:
        logger.error("Fout bij instellen positie: %s", e)
        return False

# --- Kies alternatieve richting als primaire richting geblokkeerd is ---
def choose_alternative_direction(primary, obstacles):
    """
    Kies een alternatieve richting als de primaire richting geblokkeerd is.
    Als horizontale beweging geblokkeerd is, probeer verticaal en vice versa.
    """
    if primary in ["E", "W"]:  # Horizontaal geblokkeerd, probeer verticaal
        if "N" not in obstacles:
            return "N"
        elif "S" not in obstacles:
            return "S"
    elif primary in ["N", "S"]:  # Verticaal geblokkeerd, probeer horizontaal
        if "E" not in obstacles:
            return "E"
        elif "W" not in obstacles:
            return "W"
    return None  # Geen alternatief gevonden

# --- Beweeg naar doelpositie ---
def move_to_target():
    """
    Beweeg de robot stapsgewijs naar de doelpositie.
    Zoekt een pad, vermijdt obstakels, en zorgt voor exacte stappen.
    """
    # Als noodstop actief is, beweeg niet
    if emergency_stop:
        logger.info("NOODSTOP actief - geen beweging toegestaan")
        return
        
    try:
        # Huidige positie en doelpositie
        pos = trans.getSFVec3f()
        current_x = round(pos[0], 1)
        current_y = round(pos[1], 1)
        target_x, target_y = TARGET_POS
        
        # Controleer of doel bereikt is
        if abs(current_x - target_x) < STEP_SIZE and abs(current_y - target_y) < STEP_SIZE:
            logger.info("Doel bereikt! (%f, %f)", target_x, target_y)
            turn_leds_off()
            return
            
        # Bepaal bewegingsrichting
        dx = target_x - current_x
        dy = target_y - current_y
        
        # Kies primaire richting (grote afstand eerst)
        if abs(dx) >= abs(dy):
            primary = "E" if dx > 0 else "W"
        else:
            primary = "N" if dy > 0 else "S"
            
        # Detecteer obstakels
        obstacles = detect_obstacles()
        
        # Kies richting (primair of alternatief)
        chosen_direction = primary
        if primary in obstacles:
            alt = choose_alternative_direction(primary, obstacles)
            if alt:
                logger.info("Primaire richting %s geblokkeerd, alternatief %s gekozen", primary, alt)
                chosen_direction = alt
            else:
                logger.warning("Geen vrije richting beschikbaar; geen beweging mogelijk")
                return
                
        # Bereken nieuwe positie (precies 1 stap)
        new_x, new_y = current_x, current_y
        if chosen_direction == "E":
            new_x += STEP_SIZE
        elif chosen_direction == "W":
            new_x -= STEP_SIZE
        elif chosen_direction == "N":
            new_y += STEP_SIZE
        elif chosen_direction == "S":
            new_y -= STEP_SIZE
            
        # Positie instellen
        if set_position(new_x, new_y):
            # LED's weergeven om bewegingsrichting aan te geven
            led_N.set(1 if chosen_direction == "N" else 0)
            led_E.set(1 if chosen_direction == "E" else 0)
            led_S.set(1 if chosen_direction == "S" else 0)
            led_W.set(1 if chosen_direction == "W" else 0)
            logger.info("Beweeg %s: nieuwe positie = (%.1f, %.1f)", chosen_direction, new_x, new_y)
    except Exception as e:
        logger.error("Fout tijdens bewegen: %s", e)

# --- Hoofdlus ---
logger.info("Simulatie gestart")
last_movement_time = time.time()

try:
    while robot.step(timestep) != -1:
        current_time = time.time()
        # Elke seconde bewegen en status versturen
        if current_time - last_movement_time >= 1.0:
            move_to_target()
            send_status()
            last_movement_time = current_time
        # Korte pauze voor CPU belasting
        time.sleep(0.1)
except KeyboardInterrupt:
    logger.info("Simulatie handmatig gestopt")
except Exception as e:
    logger.critical("Onverwachte fout: %s", e)
finally:
    # Cleanup bij afsluiten
    if mqtt_connected:
        client.loop_stop()
        client.disconnect()
        logger.info("MQTT verbinding afgesloten")
    logger.info("Simulatie beëindigd")
    