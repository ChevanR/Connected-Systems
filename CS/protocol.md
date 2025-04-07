# Communicatie Protocol

Dit protocol beschrijft hoe berichten tussen de Webots-controller, de Node.js-server en de robots via MQTT worden uitgewisseld.

## Berichtenstructuur

Alle berichten worden verstuurd in JSON-formaat. De basisstructuur is als volgt:

{
"protocolVersion": 1.0,
"data": {
"sender": "IDENTIFICATIE_VAN_DE_ZENDER",
"target": "DOELPARTIJ",
"msg": {
"location": {"x": X_COORDINAAT, "y": Y_COORDINAAT},
"obstacles": ["L", "R", "N", "S"],
"command": "MOVE", // alleen in command-berichten
"target": {"x": X, "y": Y} // alleen in command-berichten
}
}
}


### Uitleg velden

- **protocolVersion:** Geeft aan welke versie van het protocol wordt gebruikt.
- **data:** Bevat de hoofdgegevens van het bericht.
  - **sender:** Identificatie van de zender, bijvoorbeeld `bot1` of `server`.
  - **target:** Wie het bericht bedoeld is (kan `server` of een specifieke robot-ID zijn, of "all" voor broadcast).
  - **msg:** Het bericht zelf:
    - **location:** De locatie van de robot (in de formele grid).
    - **obstacles:** Lijst met obstakels (bijv. richtingen waar een sensor een obstakel detecteert).
    - **command:** Indien het bericht een opdracht betreft (bijv. `"MOVE"` of `"EMERGENCY_STOP"`).
    - **target:** Bij een MOVE-opdracht geeft dit het doel van de beweging aan.

## Toepassing

- **Status berichten (robot/status):**  
  De Webots-controller stuurt status updates met de huidige locatie en obstakels.
  
- **Command berichten (robot/command):**  
  De Node.js-server stuurt via REST-opdrachten pakketten (bijv. MOVE, EMERGENCY_STOP) naar het betreffende apparaat.

## Versiebeheer

Voor compatibiliteit dient het protocol een version number (bijv. 1.0) te bevatten. Eventuele wijzigingen dienen duidelijk te worden gedocumenteerd, zodat oude en nieuwe berichten correct kunnen worden geïnterpreteerd.

