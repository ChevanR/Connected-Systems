# Connected Systems project

Dit project bouwt een connected system waarin een Webots-simulatie een robot bestuurt die via MQTT berichten verstuurt met zijn positie en sensorinformatie. Een centrale Node.js-server (met Express en MQTT),
verzamelt deze gegevens en biedt een REST API. Een web-dashboard (gedraaid via nginx) toont live de robotcoördinaten en biedt knoppen om opdrachten te versturen.

## Systeem overzicht

- **Webots controller (Python):**
  - Publiceert status (positie en obstakels) via MQTT naar `robot/status` op de publieke broker (`test.mosquitto.org`).
  
- **Node.js server:**
  - Abonneert zich op `robot/status`
  - Slaat ontvangen berichten op in een in-memory object (`robotData`)
  - Biedt RESTisaties:
    - **GET /robots:** Retourneert de laatste status van de robot
    - **POST /move:** Verstuurt een MOVE-opdracht via MQTT
    - **POST /emergency_stop:** Verstuurt een noodstop-opdracht via MQTT
  - Heeft uitgebreide logging en foutafhandeling voor debugging

- **Dashboard:**
  - Wordt geserveerd door een nginx-container
  - Haalt via HTTP GET de robotdata op van de Node.js server (http://localhost:5001/robots)
  - Tekent de robotpositie op een canvas
  - Laat de gebruiker opdrachten invoeren (Move en Noodstop)

## Installatie & Deployment

### Vereisten
- **Docker** en **Docker Compose**
- Indien je lokaal npm wilt gebruiken: **Node.js** en **npm** (of gebruik de Docker-container)

### Build & Run

1. Clone dit project in je map `CS`.
2. Navigeer naar de root map (waar de `docker-compose.yml` staat).
3. Voer het volgende commando uit om de containers op te bouwen en te starten:
    ```
    docker-compose up --build
    ```
4. De Node.js-server draait op: [http://localhost:5001](http://localhost:5001)  
   Het dashboard draait op: [http://localhost:8080](http://localhost:8080)
   
5. Pas je Webots controller aan om gebruik te maken van deze opzet.

## Verder onderzoek

- Controleer de logboeken van de containers voor debugging:
  - Server logs: `docker-compose logs server`
  - Dashboard logs: `docker-compose logs dashboard`
- Voor MQTT-testen kun je het optionele script in `mqtt/mqtt_tester.py` gebruiken.

