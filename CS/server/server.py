import time
import json
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
import paho.mqtt.client as mqtt

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# Dictionary to hold latest robot statuses received over MQTT
robot_data = {}

# MQTT on_message callback: process messages from "robot/status"
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        sender = data.get("data", {}).get("sender", "unknown")
        robot_data[sender] = data.get("data", {})
    except Exception as e:
        print("Error processing MQTT message:", e)

mqtt_client = mqtt.Client("MainServer", protocol=mqtt.MQTTv311)
mqtt_client.on_message = on_message

# Use the public MQTT broker
BROKER = "test.mosquitto.org"
PORT = 1883

try:
    mqtt_client.connect(BROKER, PORT, 60)
except Exception as e:
    print("Error connecting to MQTT broker:", e)
mqtt_client.subscribe("robot/status")
mqtt_thread = threading.Thread(target=mqtt_client.loop_forever)
mqtt_thread.start()

@app.route('/robots', methods=['GET'])
def get_robot_statuses():
    return jsonify(robot_data)

@app.route('/emergency_stop', methods=['POST'])
def emergency_stop():
    command = {
        "protocolVersion": 1.0,
        "data": {
            "sender": "server",
            "target": "all",
            "msg": "EMERGENCY_STOP"
        }
    }
    mqtt_client.publish("robot/command", json.dumps(command))
    return "Emergency stop command sent", 200

@app.route('/move', methods=['POST'])
def move_unit():
    payload = request.json  # Expected format: {"unitId": "...", "target": {"x": X, "y": Y}}
    command = {
        "protocolVersion": 1.0,
        "data": {
            "sender": "server",
            "target": payload.get("unitId", "unknown"),
            "msg": {
                "command": "MOVE",
                "target": payload.get("target", {})
            }
        }
    }
    mqtt_client.publish("robot/command", json.dumps(command))
    return jsonify({"status": "move command sent"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
