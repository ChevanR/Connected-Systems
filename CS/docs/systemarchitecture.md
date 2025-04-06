# System Architecture

## Overview
The system is designed to simulate a connected environment where:
- Webots is used for robot simulation.
- An MQTT broker (using Eclipse Mosquitto) handles messaging.
- A central server (Flask based) processes robot status updates and commands.
- A web dashboard visualizes live data and provides control (including emergency stop).

## Components
- **Webots**: Contains the simulation world, robot controller, and PROTO definitions.
- **MQTT**: Handles lightweight message passing between robots and server.
- **Server**: Receives and processes MQTT messages and exposes REST APIs.
- **Dashboard**: Visualizes robot positions and enables command actions.

## Data Flow
1. The robots publish their status to the MQTT topic `robot/status`.
2. The server subscribes to these updates and stores the latest statuses.
3. The dashboard polls the server endpoints to render live updates.
4. Commands (e.g., emergency stop) are sent from the dashboard through the server.
