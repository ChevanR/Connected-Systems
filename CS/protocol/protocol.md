# TINCOS-protocol

## Bot → Server
```json
{
  "protocolVersion": 1.0,
  "data": {
    "sender": "tinbot1",
    "target": "server",
    "emergency": 0,
    "msg": {
      "location": { "x": 0.0, "y": 0.1 },
      "obstacles": [
        { "x": 1.0, "y": 0.0 },
        { "x": 2.0, "y": 1.0 }
      ]
    }
  }
}

// Server → Bot
{
  "protocolVersion": 1.0,
  "data": {
    "sender": "server",
    "target": "tinbot1",
    "emergency": 0,
    "msg": {
      "direction": "N",       // or "E", "S", "W", or ""
      "ledStatus": "N"        // which LED to turn on
    }
  }
}

// Dashboard → Server
{
  "protocolVersion": 1.0,
  "data": {
    "sender": "dashboard",
    "target": "server",
    "emergency": 0,
    "msg": {
      "taskList": [
        { "bot": "tinbot1", "goal": { "x": 4, "y": 3 } },
        { "bot": "tinbot2", "goal": { "x": 9, "y": 5 } }
      ]
    }
  }
}

// Noodstop
{
  "protocolVersion": 1.0,
  "data": {
    "sender": "tinbot1",
    "emergency": 1
  }
}