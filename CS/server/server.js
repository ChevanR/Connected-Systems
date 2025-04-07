/**
 * Connected Systems Node.js Server
 * 
 * Deze server:
 * - Verbindt met MQTT broker en abonneert op robot/status
 * - Biedt REST endpoints voor dashboard communicatie
 * - Stuurt commando's naar robots via MQTT robot/command
 * - Houdt robotstatussen bij in memory
 */

const express = require('express');
const mqtt = require('mqtt');
const cors = require('cors');
const bodyParser = require('body-parser');

// Express app setup
const app = express();
app.use(cors());
app.use(bodyParser.json());

// In-memory opslag van robotstatussen
let robotData = {};
// Noodstop status bijhouden
let emergencyStopActive = false;

// MQTT Instellingen
const MQTT_BROKER = 'mqtt://test.mosquitto.org:1883';
const MQTT_TOPICS = {
    STATUS: 'robot/status',
    COMMAND: 'robot/command'
};

// Logging helper
function log(type, message, data = null) {
    const timestamp = new Date().toISOString();
    const logMessage = `${timestamp} - ${type}: ${message}`;
    
    if (data) {
        console.log(logMessage, data);
    } else {
        console.log(logMessage);
    }
}

// Verbinding maken met de publieke MQTT-broker
log('INFO', `Verbinden met MQTT broker ${MQTT_BROKER}...`);
const client = mqtt.connect(MQTT_BROKER);

client.on('connect', () => {
    log('INFO', `Verbonden met MQTT broker ${MQTT_BROKER}`);
    
    // Abonneren op robot status topic
    client.subscribe(MQTT_TOPICS.STATUS, (err) => {
        if (err) {
            log('ERROR', `Fout bij abonneren op ${MQTT_TOPICS.STATUS}:`, err);
        } else {
            log('INFO', `Geabonneerd op topic: ${MQTT_TOPICS.STATUS}`);
        }
    });
});

client.on('error', (err) => {
    log('ERROR', 'MQTT verbindingsfout:', err);
});

client.on('message', (topic, message) => {
    try {
        // Bericht parsen
        const data = JSON.parse(message.toString());
        
        // Controleren of bericht correct formaat heeft
        if (!data.data || !data.data.sender) {
            log('WARNING', 'Ongeldig MQTT bericht formaat:', data);
            return;
        }
        
        const sender = data.data.sender;
        
        // Status opslaan
        robotData[sender] = data.data;
        
        // Detail logging alleen bij significante wijzigingen
        const location = data.data.msg && data.data.msg.location ? 
            `(${data.data.msg.location.x}, ${data.data.msg.location.y})` : 'onbekend';
        log('INFO', `Status ontvangen van ${sender}: positie=${location}`);
    } catch (error) {
        log('ERROR', "Fout bij verwerken van MQTT-bericht:", error);
    }
});

/**
 * REST API Endpoints
 */

// GET /robots - Haal alle robotstatussen op
app.get('/robots', (req, res) => {
    res.json(robotData);
});

// GET /emergency_status - Haal huidige noodstop status op
app.get('/emergency_status', (req, res) => {
    res.json({ active: emergencyStopActive });
});

// POST /emergency_stop - Activeer noodstop
app.post('/emergency_stop', (req, res) => {
    log('WARNING', "NOODSTOP commando ontvangen");
    emergencyStopActive = true;
    
    const command = {
        protocolVersion: 1.0,
        data: {
            sender: "server",
            target: "all",
            msg: "EMERGENCY_STOP"
        }
    };
    
    // Verstuur 3x voor betrouwbaarheid
    for (let i = 0; i < 3; i++) {
        publishCommand(MQTT_TOPICS.COMMAND, command, (err) => {
            if (err) {
                log('ERROR', `Poging ${i+1}: Fout bij verzenden noodstop:`, err);
            } else {
                log('INFO', `Poging ${i+1}: NOODSTOP commando verzonden`);
            }
        });
    }
    
    res.json({ status: "Emergency stop activated", active: true });
});

// POST /resume - Deactiveer noodstop
app.post('/resume', (req, res) => {
    log('INFO', "RESUME commando ontvangen");
    emergencyStopActive = false;
    
    const command = {
        protocolVersion: 1.0,
        data: {
            sender: "server",
            target: "all",
            msg: "RESUME"
        }
    };
    
    publishCommand(MQTT_TOPICS.COMMAND, command, (err) => {
        if (err) {
            log('ERROR', "Fout bij verzenden resume-opdracht:", err);
            res.status(500).json({ status: "Error sending resume command" });
        } else {
            log('INFO', "RESUME commando verzonden via MQTT");
            res.json({ status: "Resume command sent", active: false });
        }
    });
});

// POST /move - Verstuur bewegingscommando
app.post('/move', (req, res) => {
    // Controleer of er een noodstop actief is
    if (emergencyStopActive) {
        log('WARNING', "Move commando geweigerd: noodstop actief");
        return res.status(403).json({ 
            status: "Move command rejected: emergency stop is active" 
        });
    }
    
    // Haal parameters uit request
    const { unitId, target } = req.body;
    
    // Valideer parameters
    if (!unitId || !target || typeof target.x !== 'number' || typeof target.y !== 'number') {
        log('WARNING', "Ongeldige parameters voor move commando:", req.body);
        return res.status(400).json({ status: "Invalid parameters" });
    }
    
    // Coördinaten valideren en positief maken
    const validTarget = {
        x: Math.abs(parseFloat(target.x.toFixed(1))),
        y: Math.abs(parseFloat(target.y.toFixed(1)))
    };
    
    log('INFO', `Move commando ontvangen voor ${unitId} naar (${validTarget.x}, ${validTarget.y})`);
    
    const command = {
        protocolVersion: 1.0,
        data: {
            sender: "server",
            target: unitId,
            msg: {
                command: "MOVE",
                target: validTarget
            }
        }
    };
    
    publishCommand(MQTT_TOPICS.COMMAND, command, (err) => {
        if (err) {
            log('ERROR', "Fout bij verzenden move-opdracht:", err);
            res.status(500).json({ status: "Error sending move command" });
        } else {
            log('INFO', `Move commando verzonden naar ${unitId}: (${validTarget.x}, ${validTarget.y})`);
            res.json({ 
                status: `Move command sent to ${unitId}`,
                target: validTarget
            });
        }
    });
});

// Helper functie voor MQTT publiceren met foutafhandeling
function publishCommand(topic, command, callback) {
    const payload = JSON.stringify(command);
    client.publish(topic, payload, (err) => {
        if (err) {
            log('ERROR', `Fout bij publiceren op ${topic}:`, err);
            callback(err);
        } else {
            log('DEBUG', `Bericht gepubliceerd op ${topic}:`, payload);
            callback(null);
        }
    });
}

// Start de server op poort 5001
const PORT = 5001;
app.listen(PORT, () => {
    log('INFO', `Node.js server draait op poort ${PORT}`);
});

// Graceful shutdown
process.on('SIGINT', () => {
    log('INFO', 'Server wordt afgesloten...');
    if (client) {
        client.end();
    }
    process.exit();
});
