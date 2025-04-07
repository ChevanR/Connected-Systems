/**
 * Connected Systems Dashboard - script.js
 * 
 * Dit script:
 * - Haalt robotdata op van de server
 * - Tekent het grid en robots op canvas
 * - Verstuurt commando's (move, noodstop)
 * - Valideert invoer en output
 */

// Canvas en context
const canvas = document.getElementById('field');
const ctx = canvas.getContext('2d');
const gridSize = 10;
const cellSize = canvas.width / gridSize;

// Status elementen
const systemStatusEl = document.getElementById('system-status');
const stopStatusEl = document.getElementById('stop-status');
const lastActionEl = document.getElementById('last-action');

// API endpoint basis
const API_BASE = 'http://localhost:5001';

// Object om robotdata bij te houden
let robots = {};
// Noodstop status
let emergencyActive = false;

// Obstakels in het veld
const obstacles = [
  // Verticale obstakels kolom 1, 3, 6, 8
  {x: 1, y: 1}, {x: 1, y: 2}, {x: 1, y: 3},
  {x: 3, y: 1}, {x: 3, y: 2}, {x: 3, y: 3},
  {x: 6, y: 1}, {x: 6, y: 2}, {x: 6, y: 3},
  {x: 8, y: 1}, {x: 8, y: 2}, {x: 8, y: 3},
  
  // Verticale obstakels kolom 1, 3, 6, 8 (onderste helft)
  {x: 1, y: 6}, {x: 1, y: 7}, {x: 1, y: 8},
  {x: 3, y: 6}, {x: 3, y: 7}, {x: 3, y: 8},
  {x: 6, y: 6}, {x: 6, y: 7}, {x: 6, y: 8},
  {x: 8, y: 6}, {x: 8, y: 7}, {x: 8, y: 8}
];

/**
 * Logging naar console met timestamp
 */
function log(level, message, data = null) {
  const timestamp = new Date().toISOString();
  const logMessage = `${timestamp} - ${level}: ${message}`;
  
  if (data) {
    console.log(logMessage, data);
  } else {
    console.log(logMessage);
  }
}

/**
 * Converteer Webots-coördinaten naar GUI grid-posities
 * 
 * @param {number} x - Webots x-coördinaat (0.0-0.9)
 * @param {number} y - Webots y-coördinaat (0.0-0.9)
 * @returns {Object} - GUI x,y grid-positie (0-9)
 */
function coordinateToGridBlock(x, y) {
  return {
    // Webots y wordt GUI x
    x: Math.floor(y * 10),
    // Webots x wordt GUI y
    y: Math.floor(x * 10)
  };
}

/**
 * Controleer of een grid-positie een obstakel bevat
 * 
 * @param {number} x - Grid x-positie (0-9)
 * @param {number} y - Grid y-positie (0-9)
 * @returns {boolean} - true als er geen obstakel is
 */
function validateGridPosition(x, y) {
  // Binnen grid grenzen
  if (x < 0 || x >= gridSize || y < 0 || y >= gridSize) {
    return false;
  }
  
  // Controleer obstakels
  for (const obs of obstacles) {
    if (obs.x === x && obs.y === y) {
      return false;
    }
  }
  
  return true;
}

/**
 * Valideer en corrigeer coördinaten
 * 
 * @param {number} x - Grid x-coördinaat
 * @param {number} y - Grid y-coördinaat
 * @returns {Object} - gevalideerde x,y coördinaten
 */
function validateCoordinates(x, y) {
  // Maak positief
  x = Math.abs(x);
  y = Math.abs(y);
  
  // Houd binnen grid
  x = Math.min(Math.max(Math.round(x), 0), gridSize-1);
  y = Math.min(Math.max(Math.round(y), 0), gridSize-1);
  
  return {x, y};
}

/**
 * Teken het grid en obstakels
 */
function drawGrid() {
  // Wis canvas
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  // Teken gridlijnen
  ctx.strokeStyle = '#ccc';
  for (let i = 0; i <= gridSize; i++) {
    ctx.beginPath();
    ctx.moveTo(i * cellSize, 0);
    ctx.lineTo(i * cellSize, canvas.height);
    ctx.stroke();
    
    ctx.beginPath();
    ctx.moveTo(0, i * cellSize);
    ctx.lineTo(canvas.width, i * cellSize);
    ctx.stroke();
  }
  
  // Teken obstakels
  ctx.fillStyle = '#999';
  obstacles.forEach(obstacle => {
    ctx.fillRect(obstacle.x * cellSize, obstacle.y * cellSize, cellSize, cellSize);
  });
}

/**
 * Teken de robots op het grid
 */
function drawRobots() {
  // Kleur per robot
  const robotColors = {
    'bot1': 'blue',
    'bot2': 'green',
    'bot3': 'red'
  };

  // Loop door alle robots
  for (const id in robots) {
    const robot = robots[id];
    if (robot && robot.msg && robot.msg.location) {
      // Haal coördinaten
      const { x, y } = robot.msg.location;
      
      // Converteer coördinaten voor grid
      const gridPos = coordinateToGridBlock(x, y);
      
      // Teken robot als gekleurd blokje
      const color = robotColors[id] || 'blue';
      ctx.fillStyle = color;
      ctx.fillRect(gridPos.x * cellSize, gridPos.y * cellSize, cellSize, cellSize);
      
      // Teken ID als label
      ctx.fillStyle = 'white';
      ctx.font = '12px Arial';
      ctx.fillText(id, gridPos.x * cellSize + 5, gridPos.y * cellSize + 20);
      
      // Log transformatie voor debugging
      log('DEBUG', `Robot ${id}: Webots(${x}, ${y}) -> GUI(${gridPos.x}, ${gridPos.y})`);
    }
  }
}

/**
 * Update het volledige speelveld
 */
function updateField() {
  drawGrid();
  drawRobots();
}

/**
 * Haal robotdata op van server
 */
async function fetchRobots() {
  try {
    const res = await fetch(`${API_BASE}/robots`);
    if (res.ok) {
      const data = await res.json();
      log('INFO', 'Ontvangen robotdata:', data);
      
      // Update robots object met nieuwe data
      robots = data;
      
      // Update het speelveld
      updateField();
      
      // Update robot statussen
      updateQueueDisplay();
    } else {
      log('ERROR', `Fout bij ophalen robotdata: ${res.status} ${res.statusText}`);
      systemStatusEl.textContent = "verbindingsfout";
      systemStatusEl.style.color = "#ff5757";
    }
  } catch (err) {
    log('ERROR', 'Fetch error:', err);
    systemStatusEl.textContent = "offline";
    systemStatusEl.style.color = "#ff5757";
  }
}

/**
 * Haal noodstop status op van server
 */
async function fetchEmergencyStatus() {
  try {
    const res = await fetch(`${API_BASE}/emergency_status`);
    if (res.ok) {
      const data = await res.json();
      emergencyActive = data.active;
      
      // Update UI
      if (emergencyActive) {
        stopStatusEl.textContent = "ACTIEF";
        stopStatusEl.classList.add('active');
        document.querySelector('.stop-btn').classList.add('active-stop');
      } else {
        stopStatusEl.textContent = "inactief";
        stopStatusEl.classList.remove('active');
        document.querySelector('.stop-btn').classList.remove('active-stop');
      }
    }
  } catch (err) {
    log('ERROR', 'Fout bij ophalen noodstop status:', err);
  }
}

/**
 * Verstuur noodstop commando
 */
function sendStop() {
  // Visuele feedback
  document.querySelector('.stop-btn').classList.add('active-stop');
  
  fetch(`${API_BASE}/emergency_stop`, { 
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  })
  .then(response => response.json())
  .then(data => {
    log('INFO', 'Noodstop verzonden, resultaat:', data);
    
    // Update status
    stopStatusEl.textContent = "ACTIEF";
    stopStatusEl.classList.add('active');
    emergencyActive = true;
    
    // Update actie log
    updateLastAction("noodstop geactiveerd");
  })
  .catch(err => {
    log('ERROR', 'Fout bij versturen noodstop:', err);
    alert('Fout bij versturen noodstop: ' + err.message);
  });
}

/**
 * Hervat na noodstop
 */
function sendResume() {
  // Visuele feedback
  document.querySelector('.stop-btn').classList.remove('active-stop');
  
  fetch(`${API_BASE}/resume`, { 
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  })
  .then(response => response.json())
  .then(data => {
    log('INFO', 'Resume verzonden, resultaat:', data);
    
    // Update status
    stopStatusEl.textContent = "inactief";
    stopStatusEl.classList.remove('active');
    emergencyActive = false;
    
    // Update actie log
    updateLastAction("systeem herstart");
  })
  .catch(err => {
    log('ERROR', 'Fout bij versturen resume:', err);
    alert('Fout bij versturen resume: ' + err.message);
  });
}

/**
 * Verstuur bewegingscommando
 */
function sendMove() {
  // Als noodstop actief is, sta geen beweging toe
  if (emergencyActive) {
    alert('Kan geen bewegingscommando versturen tijdens noodstop.');
    return;
  }
  
  const unitId = document.getElementById('unitId').value;
  const targetStr = document.getElementById('target').value;
  const parts = targetStr.split(',');
  
  if (parts.length !== 2) {
    alert('Voer het doel in als x,y (bijv. 5,5)');
    return;
  }
  
  // Haal coördinaten en valideer
  const guiX = Number(parts[0].trim());
  const guiY = Number(parts[1].trim());
  
  // Valideer
  const validatedPos = validateCoordinates(guiX, guiY);
  
  // Controleer obstakels
  if (!validateGridPosition(validatedPos.x, validatedPos.y)) {
    alert('Deze locatie bevat een obstakel of is buiten het bereik. Kies een andere locatie.');
    return;
  }
  
  // Converteer van GUI grid naar Webots coördinaten (let op de omwisseling en schaal)
  const webotsX = validatedPos.y / 10;  // GUI Y wordt Webots X
  const webotsY = validatedPos.x / 10;  // GUI X wordt Webots Y
  
  const target = { x: webotsX, y: webotsY };
  log('INFO', `Move commando: GUI(${validatedPos.x},${validatedPos.y}) -> Webots(${webotsX},${webotsY})`);
  
  fetch(`${API_BASE}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unitId, target })
  })
  .then(res => res.json())
  .then(data => {
    log('INFO', 'Move opdracht verzonden, resultaat:', data);
    
    // Update actie log
    updateLastAction(`${unitId} naar (${validatedPos.x},${validatedPos.y})`);
  })
  .catch(err => {
    log('ERROR', 'Fout bij versturen move-opdracht:', err);
    alert('Fout bij versturen move-opdracht: ' + err.message);
  });
}

/**
 * Update de queue-display met robot status
 */
function updateQueueDisplay() {
  const queueContent = document.getElementById('queue-content');
  if (queueContent) {
    queueContent.innerHTML = '';
    
    // Vaste set van robots weergeven
    const unitIds = ['bot1', 'bot2', 'bot3'];
    
    unitIds.forEach(id => {
      let statusText = 'niet verbonden';
      let gridPos = { x: '-', y: '-' };
      
      if (robots[id] && robots[id].msg && robots[id].msg.location) {
        gridPos = coordinateToGridBlock(
          robots[id].msg.location.x,
          robots[id].msg.location.y
        );
        statusText = `positie: (${gridPos.x}, ${gridPos.y})`;
      }
      
      queueContent.innerHTML += `<p>${id}: ${statusText}</p>`;
    });
  }
}

/**
 * Update de "laatste actie" status
 */
function updateLastAction(action) {
  lastActionEl.textContent = action;
  
  // Laat actie 5 seconden zien, dan leegmaken
  setTimeout(() => {
    if (lastActionEl.textContent === action) {
      lastActionEl.textContent = '';
    }
  }, 5000);
}

// Polling interval voor data ophalen (1 sec)
setInterval(fetchRobots, 1000);
// Check emergency status every 2 seconds
setInterval(fetchEmergencyStatus, 2000);

// Initial fetch
fetchRobots();
fetchEmergencyStatus();

// Init bericht
log('INFO', 'Dashboard geïnitialiseerd');
