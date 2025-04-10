"""
Webots robot controller for Connected Systems.

This controller:
- Moves the robot to the target position
- Detects obstacles with sensors
- Communicates via MQTT with the server
- Handles MOVE and EMERGENCY_STOP commands
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import logging
import sys
import heapq
from controller import Supervisor  # type: ignore

# --- Logging configuration ---
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
    logger.info("Webots robot successfully initialized")
except Exception as e:
    logger.error("Error initializing Webots robot: %s", e)
    sys.exit(1)

# --- Constants and configuration ---
STEP_SIZE = 0.1  # Movement step in Webots (0.1 per iteration)
OBSTACLE_THRESHOLD = 400  # Threshold value for obstacle detection
MIN_BOUND, MAX_BOUND = 0.0, 0.9  # Movement boundaries in the Webots world
START_POS = [0.0, 0.0, 0.0]  # Start position [x, y, z]

# --- Grid definition (1 = path, 0 = wall) ---
GRID = [
    [1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,1,1,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,1,1,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,1,1,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,1,1,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1]
]
GRID_HEIGHT = len(GRID)
GRID_WIDTH = len(GRID[0])

# Random initial target position within boundaries
TARGET_POS = [
    round(random.uniform(0.3, 0.7), 1),
    round(random.uniform(0.3, 0.7), 1)
]

# Global variable for emergency stop
emergency_stop = False

# Robot ID (can be adjusted if needed)
ROBOT_ID = "bot2"

logger.info("Configuration: START_POS=%s, TARGET_POS=%s", START_POS, TARGET_POS)

# --- Position and rotation setup ---
try:
    trans = supervisorNode.getField("translation")
    rot = supervisorNode.getField("rotation")
    trans.setSFVec3f(START_POS)
    rot.setSFRotation([0, 0, 1, 0])
    logger.info("Position and rotation successfully set")
except Exception as e:
    logger.error("Error setting position/rotation: %s", e)
    sys.exit(1)

# --- MQTT settings ---
BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC_PUBLISH = "robot/status"
TOPIC_COMMAND = "robot/command"

# --- Initialize sensors and LEDs ---
try:
    # Sensors
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
    
    logger.info("Sensors and LEDs successfully initialized")
except Exception as e:
    logger.error("Error initializing sensors/LEDs: %s", e)
    sys.exit(1)

# --- Validation functions ---
def validate_coordinates(x, y):
    """
    Validate and correct coordinates:
    - Convert to positive values
    - Keep within boundaries
    - Round to 1 decimal for consistent steps
    """
    # Coordinates never negative
    x = abs(x)
    y = abs(y)
    
    # Keep within boundaries
    x = min(max(x, MIN_BOUND), MAX_BOUND)
    y = min(max(y, MIN_BOUND), MAX_BOUND)
    
    # Round to 1 decimal for consistent steps
    x = round(x, 1)
    y = round(y, 1)
    
    logger.debug("Coordinates validated: (%f, %f) -> (%f, %f)", x, y, x, y)
    return x, y

# --- Setup MQTT connection ---
mqtt_connected = False
try:
    client = mqtt.Client(client_id=f"WebotsRobot_{ROBOT_ID}", protocol=mqtt.MQTTv311)
    client.connect(BROKER, PORT)
    mqtt_connected = True
    logger.info("Connected to MQTT broker %s:%d", BROKER, PORT)
except Exception as e:
    logger.error("Error connecting to MQTT broker: %s", e)

# --- MQTT command processing function ---
def on_command(client, userdata, msg):
    """
    Process incoming MQTT commands:
    - EMERGENCY_STOP: Activate emergency stop
    - RESUME: Deactivate emergency stop
    - MOVE: Move to new position (if no emergency stop is active)
    """
    global TARGET_POS, emergency_stop
    
    try:
        logger.info("MQTT message received on %s", msg.topic)
        # Decode and parse message
        payload = msg.payload.decode()
        logger.debug("Received payload: %s", payload)
        command_data = json.loads(payload)
        logger.info("MQTT command received: %s", command_data)
        
        if "data" in command_data:
            # Check if this command is intended for this robot
            target = command_data["data"].get("target")
            if target not in [ROBOT_ID, "all"]:
                logger.info("Command not for this robot (target: %s)", target)
                return
                
            # Get message from command
            msg_content = command_data["data"].get("msg")
            
            # Process EMERGENCY_STOP command (highest priority)
            if msg_content == "EMERGENCY_STOP":
                logger.warning("EMERGENCY STOP ACTIVATED - robot stops immediately")
                emergency_stop = True
                # Set target position to current position to stop
                pos = trans.getSFVec3f()
                TARGET_POS = [round(pos[0], 1), round(pos[1], 1)]
                # Turn off LEDs
                turn_leds_off()
                return
                
            # Process RESUME command (to deactivate emergency stop)
            if msg_content == "RESUME":
                logger.info("EMERGENCY STOP deactivated - robot can move again")
                emergency_stop = False
                return
                
            # Process MOVE command (only if no emergency stop is active)
            if not emergency_stop and isinstance(msg_content, dict) and msg_content.get("command") == "MOVE":
                target_pos = msg_content.get("target")
                if target_pos and "x" in target_pos and "y" in target_pos:
                    try:
                        # Validate target coordinates
                        x = float(target_pos["x"])
                        y = float(target_pos["y"])
                        x, y = validate_coordinates(x, y)
                        logger.info("MOVE command received - new target position: (%f, %f)", x, y)
                        TARGET_POS = [x, y]
                    except ValueError as ve:
                        logger.error("Invalid coordinates in MOVE command: %s", ve)
    except json.JSONDecodeError as je:
        logger.error("Invalid JSON format in MQTT message: %s", je)
    except Exception as e:
        logger.error("Error processing MQTT command: %s", e)

if mqtt_connected:
    # Subscribe to command topic and start MQTT loop
    client.subscribe(TOPIC_COMMAND)
    client.message_callback_add(TOPIC_COMMAND, on_command)
    client.loop_start()
    logger.info("Subscribed to topic: %s", TOPIC_COMMAND)

# Track last sent position
last_sent_position = None

# --- Detect obstacles with sensors ---
def detect_obstacles():
    """
    Read sensor values and determine in which directions there are obstacles.
    Returns a list with direction ("N", "E", "S", "W") for each blocked direction.
    """
    try:
        obstacles = []
        # Read sensor values
        dN = sensor_N.getValue()
        dE = sensor_E.getValue()
        dS = sensor_S.getValue()
        dW = sensor_W.getValue()
        
        # Check for obstacles in each direction
        if dN < OBSTACLE_THRESHOLD:
            obstacles.append("N")
        if dE < OBSTACLE_THRESHOLD:
            obstacles.append("E")
        if dS < OBSTACLE_THRESHOLD:
            obstacles.append("S")
        if dW < OBSTACLE_THRESHOLD:
            obstacles.append("W")
            
        logger.debug("Sensor values -> N: %.2f, E: %.2f, S: %.2f, W: %.2f", dN, dE, dS, dW)
        return obstacles
    except Exception as e:
        logger.error("Error detecting obstacles: %s", e)
        return []

# --- Turn off all LEDs ---
def turn_leds_off():
    """Turn off all LED indicators"""
    try:
        led_N.set(0)
        led_E.set(0)
        led_S.set(0)
        led_W.set(0)
        logger.debug("All LEDs turned off")
    except Exception as e:
        logger.error("Error turning off LEDs: %s", e)

# --- Send status via MQTT ---
def send_status():
    """
    Send the current robot status to the MQTT broker.
    Only sends if the position has changed since last time.
    """
    global last_sent_position
    
    if not mqtt_connected:
        logger.warning("Can't send status: no MQTT connection")
        return
        
    try:
        # Get current position
        pos = trans.getSFVec3f()  # [x, y, z]
        x_pos = round(pos[0], 1)
        y_pos = round(pos[1], 1)
        current_pos = (x_pos, y_pos)
        
        # Only send if position has changed
        if last_sent_position == current_pos:
            logger.debug("Position unchanged, no update sent")
            return
            
        last_sent_position = current_pos
        
        # Compose status message
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
        
        # Convert to JSON and send
        payload = json.dumps(status_message)
        client.publish(TOPIC_PUBLISH, payload)
        logger.info("Status message sent: position=(%f, %f), emergency=%s",
                   x_pos, y_pos, emergency_stop)
    except Exception as e:
        logger.error("Error sending status: %s", e)

# --- Set position ---
def set_position(x, y):
    """
    Set the position of the robot.
    Validates coordinates and keeps the robot within boundaries.
    """
    try:
        # Validate and round
        new_x = round(x, 1)
        new_y = round(y, 1)
        
        # Keep within boundaries
        new_x = min(max(new_x, MIN_BOUND), MAX_BOUND)
        new_y = min(max(new_y, MIN_BOUND), MAX_BOUND)
        
        # Maintain current z-coordinate
        current = trans.getSFVec3f()
        trans.setSFVec3f([new_x, new_y, current[2]])
        
        # Maintain rotation (looking up)
        rot.setSFRotation([0, 0, 1, 0])
        
        logger.debug("Position set: (%f, %f)", new_x, new_y)
        return True
    except Exception as e:
        logger.error("Error setting position: %s", e)
        return False

# --- Choose alternative direction if primary direction is blocked ---
def choose_alternative_direction(primary, obstacles):
    """
    Choose an alternative direction if the primary direction is blocked.
    If horizontal movement is blocked, try vertical and vice versa.
    """
    if primary in ["E", "W"]:  # Horizontal blocked, try vertical
        if "N" not in obstacles:
            return "N"
        elif "S" not in obstacles:
            return "S"
    elif primary in ["N", "S"]:  # Vertical blocked, try horizontal
        if "E" not in obstacles:
            return "E"
        elif "W" not in obstacles:
            return "W"
            
    return None  # No alternative found

# --- Manhattan distance heuristic ---
def heuristic(a, b):
    """Manhattan distance heuristic"""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

# --- Find closest valid position ---
def find_closest_valid_position(grid, pos):
    """Find the closest valid position in the grid"""
    x, y = pos
    
    # If the position is already valid, return it
    if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT and grid[y][x] == 1:
        return pos
        
    # Search in expanding squares around the position
    for radius in range(1, max(GRID_WIDTH, GRID_HEIGHT)):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                # Only check positions on the border of the square
                if abs(dx) == radius or abs(dy) == radius:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT and grid[ny][nx] == 1:
                        logger.info(f"Adjusted position from ({x}, {y}) to ({nx}, {ny})")
                        return (nx, ny)
                        
    # If no valid position found, return the center of the grid as a fallback
    logger.warning(f"Could not find valid position near ({x}, {y}), using center of grid")
    center_x, center_y = GRID_WIDTH // 2, GRID_HEIGHT // 2
    return (center_x, center_y)

# --- Dijkstra path finding ---
def dijkstra(grid, start, goal):
    """Find shortest path with Dijkstra's algorithm with improved error handling"""
    # If start or goal is not valid, use closest valid position
    start = find_closest_valid_position(grid, start)
    goal = find_closest_valid_position(grid, goal)
    
    queue = []
    heapq.heappush(queue, (0, start))
    visited = set()
    came_from = {}
    cost_so_far = {start: 0}
    
    while queue:
        current_cost, current = heapq.heappop(queue)
        
        if current in visited:
            continue
            
        visited.add(current)
        
        if current == goal:
            break
            
        x, y = current
        
        # Check all four directions
        neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
        
        for nx, ny in neighbors:
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                if grid[ny][nx] == 1 and (nx, ny) not in visited:
                    new_cost = current_cost + 1
                    if (nx, ny) not in cost_so_far or new_cost < cost_so_far[(nx, ny)]:
                        cost_so_far[(nx, ny)] = new_cost
                        priority = new_cost + heuristic((nx, ny), goal)
                        heapq.heappush(queue, (priority, (nx, ny)))
                        came_from[(nx, ny)] = current
    
    # Path reconstruction
    if goal not in came_from and goal != start:
        # No direct path found, try to find partial path
        logger.warning("No direct path found, finding nearest reachable point")
        # Find the closest visited node to the goal
        closest_node = min(visited, key=lambda node: heuristic(node, goal))
        
        if closest_node == start:
            logger.error(f"Cannot find any valid path towards ({goal[0]}, {goal[1]})")
            return []
            
        # Reconstruct path to the closest reachable node
        path = []
        node = closest_node
        while node != start:
            path.append(node)
            node = came_from.get(node)
            if node is None:
                return []  # This shouldn't happen, but just in case
        
        path.reverse()
        return path
    
    # Normal path reconstruction when path exists
    path = []
    node = goal
    
    # If we're already at the goal
    if start == goal:
        return []
        
    while node != start:
        path.append(node)
        node = came_from.get(node)
        if node is None:
            logger.error(f"Path reconstruction failed from {start} to {goal}")
            return []  # This shouldn't happen given our earlier check
            
    path.reverse()
    return path

# --- World-grid coordinate conversions ---
def world_to_grid(x, y):
    """Convert Webots position to grid position"""
    gx = int(round(x / STEP_SIZE))
    gy = GRID_HEIGHT - 1 - int(round(y / STEP_SIZE))  # Inverted Y-axis
    return gx, gy

def grid_to_world(gx, gy):
    """Convert grid position to Webots position"""
    x = round(gx * STEP_SIZE, 1)
    y = round((GRID_HEIGHT - 1 - gy) * STEP_SIZE, 1)
    return x, y

# --- Move to target ---
path_cache = []

def move_to_target():
    """
    Use Dijkstra path planning to move step by step towards target position.
    Includes better error handling for path planning failures.
    """
    global path_cache
    
    if emergency_stop:
        logger.info("EMERGENCY STOP active - no movement allowed")
        return
        
    pos = trans.getSFVec3f()
    current_gx, current_gy = world_to_grid(pos[0], pos[1])
    target_gx, target_gy = world_to_grid(TARGET_POS[0], TARGET_POS[1])
    
    # If path is empty or target has changed: recalculate
    if not path_cache or (target_gx, target_gy) != path_cache[-1] if path_cache else True:
        path_cache = dijkstra(GRID, (current_gx, current_gy), (target_gx, target_gy))
        
        if not path_cache:
            logger.warning(f"No path found to ({target_gx}, {target_gy})")
            # Stay where we are and don't get stuck
            if current_gx != target_gx or current_gy != target_gy:
                logger.info("Using small step movement instead")
                # Move one step in the general direction of the target
                # This is a fallback for when path planning fails
                dx = 1 if target_gx > current_gx else -1 if target_gx < current_gx else 0
                dy = 1 if target_gy > current_gy else -1 if target_gy < current_gy else 0
                
                # Try to move in a valid direction
                for direction in [(dx, dy), (dx, 0), (0, dy), (1, 0), (0, 1), (-1, 0), (0, -1)]:
                    next_x, next_y = current_gx + direction[0], current_gy + direction[1]
                    if 0 <= next_x < GRID_WIDTH and 0 <= next_y < GRID_HEIGHT and GRID[next_y][next_x] == 1:
                        path_cache = [(next_x, next_y)]
                        break
                else:
                    logger.error("Robot is completely stuck, no valid moves")
                    return
    
    # If we have a path to follow
    if path_cache:
        next_step = path_cache.pop(0)
        new_x, new_y = grid_to_world(*next_step)
        
        # Move robot
        if set_position(new_x, new_y):
            dx = next_step[0] - current_gx
            dy = next_step[1] - current_gy
            dir_map = {(0,1): "N", (1,0): "E", (0,-1): "S", (-1,0): "W"}
            direction = dir_map.get((dx, dy), "?")
            
            # LED mappings
            led_N.set(1 if direction == "S" else 0)
            led_E.set(1 if direction == "E" else 0)
            led_S.set(1 if direction == "N" else 0)
            led_W.set(1 if direction == "W" else 0)
            
            logger.info("Moving to grid (%d,%d) world (%.1f, %.1f) direction %s",
                        next_step[0], next_step[1], new_x, new_y, direction)

# --- Main loop ---
logger.info("Simulation started")
last_movement_time = time.time()

try:
    while robot.step(timestep) != -1:
        current_time = time.time()
        
        # Move and send status every second
        if current_time - last_movement_time >= 1.0:
            move_to_target()
            send_status()
            last_movement_time = current_time
            
        # Short pause for CPU load
        time.sleep(0.1)
except KeyboardInterrupt:
    logger.info("Simulation manually stopped")
except Exception as e:
    logger.critical("Unexpected error: %s", e)
finally:
    # Cleanup on exit
    if mqtt_connected:
        client.loop_stop()
        client.disconnect()
        logger.info("MQTT connection closed")
    logger.info("Simulation ended")
