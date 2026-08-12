// Minimal sparkline renderer using Canvas — no external dependencies required.
// Usage: <canvas class="sparkline" data-values="24000,24100,24050,24200"></canvas>

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('canvas.sparkline').forEach(canvas => {
    const raw = canvas.dataset.values || '';
    const values = raw.split(',').map(Number).filter(v => !isNaN(v));
    if (values.length < 2) return;

    const w = canvas.width || 80;
    const h = canvas.height || 32;
    canvas.width = w;
    canvas.height = h;

    const ctx = canvas.getContext('2d');
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    const isUp = values[values.length - 1] >= values[0];
    const color = isUp ? '#22c55e' : '#ef4444';

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    ctx.beginPath();
    values.forEach((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
});
