const canvas = document.getElementById('field');
const ctx = canvas.getContext('2d');
const gridSize = 10;
const cellSize = canvas.width / gridSize;

const obstacles = [
  [1,1],[1,2],[1,3], [3,1],[3,2],[3,3], [6,1],[6,2],[6,3], [8,1],[8,2],[8,3],
  [1,6],[1,7],[1,8], [3,6],[3,7],[3,8], [6,6],[6,7],[6,8], [8,6],[8,7],[8,8]
];

const units = {
  unit0: { x: 0, y: 0, color: 'blue', queue: [] },
  unit1: { x: 0, y: 9, color: 'green', queue: [] },
  unit2: { x: 9, y: 0, color: 'orange', queue: [] },
};

const socket = new WebSocket('ws://localhost:8081/');

socket.addEventListener('open', () => {
  console.log('WebSocket connected');
});

socket.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  console.log('Ontvangen van server:', data);
});

function drawGrid() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#aaa';
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

  // Obstakels tekenen
  ctx.fillStyle = 'gray';
  for (const [x, y] of obstacles) {
    ctx.fillRect(x * cellSize + 2, y * cellSize + 2, cellSize - 4, cellSize - 4);
  }
}

function drawUnits() {
  for (const id in units) {
    const unit = units[id];
    ctx.fillStyle = unit.color;
    ctx.fillRect(
      unit.x * cellSize + 2,
      unit.y * cellSize + 2,
      cellSize - 4,
      cellSize - 4
    );
  }
}

function updateQueues() {
  const queuesDiv = document.getElementById('queues');
  queuesDiv.innerHTML = '';
  for (const id in units) {
    const q = units[id].queue.map(pos => `(${pos.x},${pos.y})`).join(' -> ');
    queuesDiv.innerHTML += `<div><strong>${id}</strong>: ${q || 'geen opdrachten'}</div>`;
  }
}

function isObstacle(x, y) {
  return obstacles.some(([ox, oy]) => ox === x && oy === y);
}

function moveUnit() {
  const unitId = document.getElementById('unitId').value;
  const to = document.getElementById('to').value.split(',').map(Number);
  if (units[unitId]) {
    const newTarget = { x: to[0], y: to[1] };
    if (!isObstacle(newTarget.x, newTarget.y)) {
      units[unitId].queue.push(newTarget);
      socket.send(JSON.stringify({ type: 'move', unitId, target: newTarget }));
      updateQueues();
    } else {
      alert('Doelpositie is een obstakel!');
    }
  }
}

function sendStop() {
  alert('NOODSTOP verstuurd!');
  socket.send(JSON.stringify({ type: 'stop' }));
}

function update() {
  drawGrid();

  // Simuleer queue-verwerking
  for (const id in units) {
    const unit = units[id];
    if (unit.queue.length > 0) {
      const next = unit.queue[0];
      let newX = unit.x;
      let newY = unit.y;
      if (unit.x < next.x) newX++;
      else if (unit.x > next.x) newX--;
      else if (unit.y < next.y) newY++;
      else if (unit.y > next.y) newY--;

      if (!isObstacle(newX, newY)) {
        unit.x = newX;
        unit.y = newY;
        if (unit.x === next.x && unit.y === next.y) {
          unit.queue.shift();
        }
      } else {
        unit.queue = []; // Stop de queue als er een obstakel in de weg staat
      }
    }
  }

  drawUnits();
  updateQueues();
}

setInterval(update, 1000);