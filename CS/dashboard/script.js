// Get canvas and context
const canvas = document.getElementById('field');
const ctx = canvas.getContext('2d');
const gridSize = 10;
const cellSize = canvas.width / gridSize;

// Object to hold the latest robot statuses retrieved from the server
let robots = {};

// Draw grid lines on the canvas
function drawGrid() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
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
}

// Draw robots as colored squares, including labels for identification
function drawRobots() {
  for (const id in robots) {
    const robot = robots[id];
    if (robot.msg && robot.msg.location) {
      const x = robot.msg.location.x;
      const y = robot.msg.location.y;
      const color = robot.msg.color || 'blue';
      ctx.fillStyle = color;
      ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
      ctx.fillStyle = 'white';
      ctx.font = '12px Arial';
      ctx.fillText(id, x * cellSize + 2, y * cellSize + 12);
    }
  }
}

// Update entire canvas by drawing grid and robots
function updateField() {
  drawGrid();
  drawRobots();
}

// Poll the server every 1 second for latest robot data
async function fetchRobots() {
  try {
    const res = await fetch('http://localhost:5000/robots');
    if (res.ok) {
      robots = await res.json();
      updateField();
    } else {
      console.error('Error fetching robots: ', res.statusText);
    }
  } catch (err) {
    console.error('Fetch error: ', err);
  }
}

// Send emergency stop command to server
function sendStop() {
  fetch('http://localhost:5000/emergency_stop', { method: 'POST' })
    .then(response => response.text())
    .then(data => alert(data))
    .catch(err => console.error('Error sending stop command: ', err));
}

// Send move command to server with unit and target
function sendMove() {
  const unitId = document.getElementById('unitId').value;
  const targetStr = document.getElementById('target').value;
  const parts = targetStr.split(',');
  if (parts.length !== 2) {
    alert('Please input the target as x,y');
    return;
  }
  const x = Number(parts[0].trim());
  const y = Number(parts[1].trim());
  const target = { x, y };
  fetch('http://localhost:5000/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unitId, target })
  })
  .then(res => res.json())
  .then(data => alert(data.status))
  .catch(err => console.error('Error sending move command: ', err));
}

// Start polling the server every second
setInterval(fetchRobots, 1000);
