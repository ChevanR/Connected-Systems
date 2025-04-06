const express = require('express');
const mqtt = require('mqtt');
const cors = require('cors');
const bodyParser = require('body-parser');

const app = express();
app.use(cors());
app.use(bodyParser.json());

// In-memory opslag van robotstatussen
let robotData = {};

// Verbinding maken met de publieke MQTT-broker
const MQTT_BROKER = 'mqtt://test.mosquitto.org:1883';
const client  = mqtt.connect(MQTT_BROKER);

client.on('connect', () => {
  console.log("Node.js server verbonden met MQTT-broker op " + MQTT_BROKER);
  client.subscribe('robot/status', (err) => {
    if (err) console.error('Fout bij abonneren op robot/status:', err);
    else console.log('Geabonneerd op topic: robot/status');
  });
});

client.on('message', (topic, message) => {
  try {
    const data = JSON.parse(message.toString());
    const sender = data.data.sender;
    if (sender) {
      robotData[sender] = data.data;
      console.log(`Status ontvangen van ${sender}:`, robotData[sender]);
    }
  } catch (error) {
    console.error("Fout bij verwerken van MQTT-bericht:", error);
  }
});

// REST Endpoint: Haal robotstatussen op
app.get('/robots', (req, res) => {
  res.json(robotData);
});

// REST Endpoint: Noodstop
app.post('/emergency_stop', (req, res) => {
  const command = {
    protocolVersion: 1.0,
    data: {
      sender: "server",
      target: "all",
      msg: "EMERGENCY_STOP"
    }
  };
  client.publish('robot/command', JSON.stringify(command), (err) => {
    if (err) {
      console.error("Fout bij verzenden noodstop:", err);
      res.status(500).json({ status: "Error sending emergency stop" });
    } else {
      res.send("Emergency stop command sent");
    }
  });
});

// REST Endpoint: Move
app.post('/move', (req, res) => {
  const { unitId, target } = req.body;
  const command = {
    protocolVersion: 1.0,
    data: {
      sender: "server",
      target: unitId,
      msg: {
        command: "MOVE",
        target: target
      }
    }
  };
  client.publish('robot/command', JSON.stringify(command), (err) => {
    if (err) {
      console.error("Fout bij verzenden move-opdracht:", err);
      res.status(500).json({ status: "Error sending move command" });
    } else {
      res.json({ status: `Move command sent to ${unitId}` });
    }
  });
});

// Start de server op poort 5001 in plaats van 5000
const PORT = 5001;
app.listen(PORT, () => {
  console.log(`Node.js server draait op poort ${PORT}`);
});
