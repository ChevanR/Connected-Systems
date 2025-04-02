// server.js
// This Node.js server connects to the public MQTT broker and serves as a bridge using WebSockets.
// It receives robot status messages from MQTT and broadcasts them to all connected WebSocket clients.
// It also broadcasts commands received from the WebSocket clients to the MQTT broker.

const WebSocket = require('ws');
const mqtt = require('mqtt');
const express = require('express');
const http = require('http');
const path = require('path');

// ----- Configuration -----
const MQTT_BROKER = 'mqtt://test.mosquitto.org';
const MQTT_STATUS_TOPIC = 'robot/status';
const MQTT_COMMAND_TOPIC = 'robot/command';
const WS_PORT = 8081;  // WebSocket server port

// ----- Connect to MQTT broker -----
const mqttClient = mqtt.connect(MQTT_BROKER);
mqttClient.on('connect', () => {
  console.log('[MQTT] Connected to broker:', MQTT_BROKER);
  mqttClient.subscribe(MQTT_STATUS_TOPIC, (err) => {
    if(err) console.error('[MQTT] Subscription error:', err);
    else console.log(`[MQTT] Subscribed to topic ${MQTT_STATUS_TOPIC}`);
  });
});

// ----- Setting up Express and WebSocket server -----
const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });
  
// Serve static files from the frontend folder
app.use(express.static(path.join(__dirname, '../frontend')));

// Broadcast a message to all WebSocket clients
function broadcast(message) {
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  });
}

// ----- MQTT Message Handler -----
// When a message is received on the status topic, broadcast it via websockets.
mqttClient.on('message', (topic, message) => {
  if (topic === MQTT_STATUS_TOPIC) {
    const msgString = message.toString();
    console.log('[MQTT] Status message received:', msgString);
    broadcast(msgString);  // Send to all connected WebSocket clients
  }
});

// ----- WebSocket message handler -----
// Receives commands (for movement etc.) from the GUI and publishes them to the MQTT broker.
wss.on('connection', (ws) => {
  console.log('[WS] WebSocket client connected');
  ws.on('message', (message) => {
    console.log('[WS] Message received from client:', message);
    try {
      const data = JSON.parse(message);
      // For this example, assume a message type 'move' is sent from the GUI:
      if(data.type === 'move'){
        // Build the MQTT command message
        const mqttCommand = {
          protocolVersion: 1.0,
          data: {
            sender: "gui",
            target: data.unitId, // unit identifier (e.g. "bot1")
            msg: {
              direction: data.direction,  // e.g. "N", "S", etc.
              target: { x: data.target.x, y: data.target.y }
            }
          }
        };
        mqttClient.publish(MQTT_COMMAND_TOPIC, JSON.stringify(mqttCommand));
        console.log(`[MQTT] Command published for ${data.unitId}`);
      }
      // Handle other types of messages as needed...
    } catch (e) {
      console.error("[WS] Error processing message:", e);
    }
  });
  ws.on('close', () => {
    console.log('[WS] WebSocket client disconnected');
  });
});

// Start the HTTP + WebSocket server
server.listen(WS_PORT, () => {
  console.log(`WebSocket server is running at ws://localhost:${WS_PORT}`);
});
