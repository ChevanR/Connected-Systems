const canvas = document.getElementById('field');
const ctx = canvas.getContext('2d');
const gridSize = 10;
const cellSize = canvas.width / gridSize;

// Object om de laatste robotposities bij te houden
let robots = {};

// Vaste obstakels definiëren zoals in het voorbeeld
const obstacles = [
  {x: 1, y: 1}, {x: 3, y: 1}, {x: 5, y: 1}, {x: 7, y: 1},
  {x: 1, y: 2}, {x: 3, y: 2}, {x: 5, y: 2}, {x: 7, y: 2},
  {x: 1, y: 3}, {x: 3, y: 3}, {x: 5, y: 3}, {x: 7, y: 3},
  {x: 1, y: 6}, {x: 3, y: 6}, {x: 5, y: 6}, {x: 7, y: 6},
  {x: 1, y: 7}, {x: 3, y: 7}, {x: 5, y: 7}, {x: 7, y: 7},
  {x: 1, y: 8}, {x: 3, y: 8}, {x: 5, y: 8}, {x: 7, y: 8}
];

// Functie om decimale Webots-coördinaten naar grid-posities te converteren
function coordinateToGridBlock(coord) {
  // Vermenigvuldig Webots-coördinaten (bijv. 0.1, 0.2) met 10 voor het grid (1, 2)
  return Math.floor(coord * 10);
}

// Teken het grid
function drawGrid() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#ccc';
  
  // Teken gridlijnen
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

// Teken robots
function drawRobots() {
  const robotColors = {
    'bot1': 'blue',
    'unit0': 'orange',
    'unit1': 'green',
    'unit2': 'red'
  };

  for (const id in robots) {
    const robot = robots[id];
    if (robot && robot.msg && robot.msg.location) {
      // Converteer vloeiende coördinaten naar grid-posities
      const x = coordinateToGridBlock(robot.msg.location.x);
      const y = coordinateToGridBlock(robot.msg.location.y);
      
      // Kies kleur op basis van ID of standaard blauw
      const color = robotColors[id] || 'blue';
      
      ctx.fillStyle = color;
      ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
      
      // Teken label voor de robot
      ctx.fillStyle = 'white';
      ctx.font = '12px Arial';
      ctx.fillText(id, x * cellSize + 5, y * cellSize + 20);
    }
  }
}

// Update het hele canvas
function updateField() {
  drawGrid();
  drawRobots();
}

// Haal robotdata op
async function fetchRobots() {
  try {
    const res = await fetch('http://localhost:5001/robots');
    if (res.ok) {
      robots = await res.json();
      console.log('Ontvangen robotdata:', robots);
      updateField();
      updateQueueDisplay();
    } else {
      console.error('Fout bij ophalen robotdata:', res.statusText);
    }
  } catch (err) {
    console.error('Fetch error:', err);
  }
}

// Verstuur een noodstop-opdracht
function sendStop() {
  fetch('http://localhost:5001/emergency_stop', { method: 'POST' })
    .then(response => response.text())
    .then(data => {
      console.log('Noodstop verzonden:', data);
    })
    .catch(err => console.error('Fout bij versturen noodstop:', err));
}

// Verstuur een move-opdracht
function sendMove() {
  const unitId = document.getElementById('unitId').value;
  const targetStr = document.getElementById('target').value;
  const parts = targetStr.split(',');
  
  if (parts.length !== 2) {
    alert('Voer het doel in als x,y');
    return;
  }
  
  // Converteer grid-positie naar decimale waarden voor de server (deel door 10)
  const x = Number(parts[0].trim()) / 10;
  const y = Number(parts[1].trim()) / 10;
  
  const target = { x, y };
  
  fetch('http://localhost:5001/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unitId, target })
  })
  .then(res => res.json())
  .then(data => {
    console.log('Move opdracht verzonden:', data);
  })
  .catch(err => console.error('Fout bij versturen move-opdracht:', err));
}

// Voeg rij met opdrachten toe
function updateQueueDisplay() {
  const queueContent = document.getElementById('queue-content');
  if (queueContent) {
    queueContent.innerHTML = '';
    
    // Standaard units toevoegen, zelfs als niet in robots
    const unitIds = ['unit0', 'unit1', 'unit2'];
    
    // Voeg ook alle gevonden robot IDs toe
    for (const id in robots) {
      if (!unitIds.includes(id)) {
        unitIds.push(id);
      }
    }
    
    // Maak rij voor elke robot
    unitIds.forEach(id => {
      queueContent.innerHTML += `<p>${id}: geen opdrachten</p>`;
    });
  }
}

// Start met data ophalen en updates
setInterval(fetchRobots, 1000);
