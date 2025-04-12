# Connected Systems - iBot coordination platform

A distributed system for coordinating autonomous robots with real-time communication, collision avoidance, and web-based control.

## Key features
- Real-time MQTT communication between robots/server
- REST API for dashboard interactions
- Dynamic pathfinding with obstacle/collision avoidance
- Priority-based command queuing system
- Emergency stop/resume functionality
- Web-based monitoring dashboard
- ESP32 hardware integration

## Technologies
- **Core protocol**: MQTT + REST
- **Robots**: Webots simulator + Python controllers
- **Server**: Node.js + Express
- **Dashboard**: HTML5/Canvas + JavaScript + CSS
- **Hardware**: ESP32 microcontrollers
- **Containerization**: Docker

## System architecture
The system consists of three main components:
1. **Robots**: Autonomous agents that navigate the environment
2. **Server**: Central coordinator that manages robot commands
3. **Dashboard**: Web interface for monitoring and control

Communication between components uses:
- MQTT for real-time robot-server messaging
- REST API for dashboard-server interaction
- WebSockets for real-time dashboard updates

## Installation

### Prerequisites
- Docker and Docker Compose
- Node.js 14+ (for development)
- Webots simulator (for robot simulation)
- ESP32 hardware (optional, for physical implementation)

### Setup
- Clone the repository
git clone https://github.com/ChevanR/Connected-Systems.git

- Navigate to project directory
cd Connected-Systems

- Start the system with Docker
docker-compose up --build

## System structure
- ├── webots/
- │ └── controllers/
- │ │  └── basic_controller/
- │ │     └── basic_controller.py
- │ │── protos/
- │ │  ├── iBot_led.proto
- │ └── iBot.proto
- │ └── worlds/
- │    ├── .MyArena.jpg
- │    ├── .MyArena.wbproj
- │        └── MyArena.wbt
- ├── server/
- │ ├── server.js
- │ ├── package.json
- │ └── Dockerfile.server
- ├── dashboard/
- │ ├── index.html
- │ ├── style.css
- │ ├── script.js
- │ └── Dockerfile.dashboard
- ├── hardware/
- │ └── iBot.ino
- ├── protocol.md
- ├── README.md
- └── docker-compose.yml


## Usage

### Starting the system
1. Start all services: `docker-compose up`
2. Access dashboard: `http://localhost:8080`

### Controlling robots
Send commands via:
- Web interface (recommended)
- REST API: `POST http://localhost:5001/move`
- MQTT: Publish to `robot/command` topic

### Dashboard features
- Real-time robot position visualization
- Command sending interface
- Queue management
- Emergency stop/resume controls

### Hardware integration
The ESP32 implementation provides:
- Physical emergency stop button
- LED direction indicators
- MQTT connectivity for remote monitoring

## API documentation
See [protocol.md](./protocol.md) for detailed message specifications and endpoints.

## Development

### Local development setup
Start server in development mode
cd server
npm install
npm run dev

Start dashboard in development mode
cd dashboard
npm install
npm run dev


### Simulation
The system uses Webots for robot simulation:
1. Open Webots
2. Load the world file from `robots/worlds/connected_systems.wbt`
3. Start the simulation

## Troubleshooting

### Common issues
- **Dashboard not connecting**: Ensure server is running on port 5001
- **MQTT connection errors**: Check broker availability
- **Robot not responding**: Verify controller is properly loaded

### Debugging
Monitor MQTT traffic
mosquitto_sub -h test.mosquitto.org -t "robot/#" -v

Check server logs
docker logs connected-systems_server_1

View dashboard network requests
Open browser developer tools (F12) and check Network tab


## Contributors
- Chevan ([@chevanr](https://github.com/chevanr)) - Backend infrastructure, GUI & Webots.
- Wen ([@wennhao](https://github.com/wennhao)) - Robot controller development
- Jason ([@jason](https://github.com/jason)) - Hardware development

## License
MIT License - See LICENSE file for details
