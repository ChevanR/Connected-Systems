// script.js
const canvas = document.getElementById('field');
const ctx = canvas.getContext('2d');
const gridSize = 10;
const cellSize = canvas.width / gridSize;

// Object om de laatste robotposities bij te houden
let robots = {};

// Obstakels in het veld, gebaseerd op de webots simulatie
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

// Functie om Webots-coördinaten naar GUI grid-posities te converteren
function coordinateToGridBlock(x, y) {
  // Converteer en wissel x/y om zodat het overeenkomt met Webots oriëntatie
  return {
    // y-coördinaat van Webots wordt x op de GUI
    x: Math.floor(y * 10),
    // x-coördinaat van Webots wordt y op de GUI
    y: Math.floor(x * 10)
  };
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
      // Converteer coördinaten met omwisseling van x en y
      const gridPos = coordinateToGridBlock(
        robot.msg.location.x,
        robot.msg.location.y
      );
      
      // Kies kleur op basis van ID of standaard blauw
      const color = robotColors[id] || 'blue';
      
      ctx.fillStyle = color;
      ctx.fillRect(gridPos.x * cellSize, gridPos.y * cellSize, cellSize, cellSize);
      
      // Teken label voor de robot
      ctx.fillStyle = 'white';
      ctx.font = '12px Arial';
      ctx.fillText(id, gridPos.x * cellSize + 5, gridPos.y * cellSize + 20);
      
      // Debug logging voor robotpositie
      console.log(`Robot ${id} op positie Webots(${robot.msg.location.x}, ${robot.msg.location.y}) -> GUI(${gridPos.x}, ${gridPos.y})`);
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
      alert('Noodstop commando verzonden!');
    })
    .catch(err => {
      console.error('Fout bij versturen noodstop:', err);
      alert('Fout bij versturen noodstop: ' + err.message);
    });
}

// Verstuur een move-opdracht
function sendMove() {
  const unitId = document.getElementById('unitId').value;
  const targetStr = document.getElementById('target').value;
  const parts = targetStr.split(',');
  
  if (parts.length !== 2) {
    alert('Voer het doel in als x,y (bijv. 5,5)');
    return;
  }
  
  // BELANGRIJKE AANPASSING: wissel x en y voor Webots
  // GUI-coördinaten (door gebruiker ingevoerd) worden omgewisseld
  // naar Webots-coördinaten (y,x)
  const guiX = Number(parts[0].trim());
  const guiY = Number(parts[1].trim());
  
  // Stuur naar Webots met juiste conversie (en deel door 10)
  const webotsY = guiX / 10; // GUI X wordt Webots Y
  const webotsX = guiY / 10; // GUI Y wordt Webots X
  
  const target = { x: webotsX, y: webotsY };
  
  console.log(`Move commando: GUI(${guiX},${guiY}) -> Webots(${webotsX},${webotsY})`);
  
  fetch('http://localhost:5001/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unitId, target })
  })
  .then(res => res.json())
  .then(data => {
    console.log('Move opdracht verzonden:', data);
    alert(`Bot ${unitId} wordt verplaatst naar (${guiX},${guiY})`);
  })
  .catch(err => {
    console.error('Fout bij versturen move-opdracht:', err);
    alert('Fout bij versturen move-opdracht: ' + err.message);
  });
}

// Voeg rij met opdrachten toe
function updateQueueDisplay() {
  const queueContent = document.getElementById('queue-content');
  if (queueContent) {
    queueContent.innerHTML = '';
    
    // Standaard units toevoegen, zelfs als niet in robots
    const unitIds = ['bot1', 'unit0', 'unit1', 'unit2'];
    
    // Voeg ook alle gevonden robot IDs toe
    for (const id in robots) {
      if (!unitIds.includes(id)) {
        unitIds.push(id);
      }
    }
    
    // Maak rij voor elke robot
    unitIds.forEach(id => {
      const robot = robots[id];
      let statusText = 'geen opdrachten';
      
      if (robot && robot.msg && robot.msg.location) {
        const gridPos = coordinateToGridBlock(robot.msg.location.x, robot.msg.location.y);
        statusText = `positie: (${gridPos.x},${gridPos.y})`;
      }
      
      queueContent.innerHTML += `<p>${id}: ${statusText}</p>`;
    });
  }
}

// Start met data ophalen en updates
setInterval(fetchRobots, 1000);
