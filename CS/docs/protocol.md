# MQTT Protocol Specification

## Message Structure
Each message is a JSON object containing:
- `protocolVersion`: (e.g., 1.0)
- `data`: 
  - `sender`: Identifier of the sender (e.g., "bot1")
  - `target`: Intended recipient (e.g., "server" or "all")
  - `msg`: Object that includes:
    - `location`: An object with `x` and `y` coordinates
    - `obstacles`: A list of obstacles (e.g., ["N", "E"])

Example:
{
  "protocolVersion": 1.0,
  "data": {
    "sender": "bot1",
    "target": "server",
    "msg": {
      "location": {"x": 0.3, "y": 0.4},
      "obstacles": ["N", "E"]
    }
  }
}
