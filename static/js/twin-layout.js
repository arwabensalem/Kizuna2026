/**
 * Room layout shared by the 2D plan and the 3D twin.
 * Each room takes whole cells on a grid that is COLS cells wide.
 */

export const SPAN = {
  living_room: [2, 2],
  kitchen: [2, 1],
  bedroom: [2, 1],
  bathroom: [1, 1],
  garage: [2, 1],
  other: [1, 1],
  garden: [2, 1],
  pool: [2, 1],
};

export const RANK = {
  living_room: 0,
  kitchen: 1,
  bedroom: 2,
  bathroom: 3,
  other: 4,
  garage: 5,
  garden: 6,
  pool: 7,
};

export const COLS = 4;

export function layout(rooms) {
  const indoor = rooms
    .filter((room) => room.kind !== "garden" && room.kind !== "pool")
    .slice()
    .sort((a, b) => (RANK[a.kind] ?? 9) - (RANK[b.kind] ?? 9));
  const outdoor = rooms.filter((room) => room.kind === "garden" || room.kind === "pool");
  const taken = new Set();
  const placed = [];
  let maxY = -1;

  function free(x, y, w, h) {
    if (x + w > COLS) {
      return false;
    }
    for (let dy = 0; dy < h; dy += 1) {
      for (let dx = 0; dx < w; dx += 1) {
        if (taken.has(`${x + dx},${y + dy}`)) {
          return false;
        }
      }
    }
    return true;
  }

  function occupy(x, y, w, h) {
    for (let dy = 0; dy < h; dy += 1) {
      for (let dx = 0; dx < w; dx += 1) {
        taken.add(`${x + dx},${y + dy}`);
      }
    }
  }

  indoor.forEach((room) => {
    const [w, h] = SPAN[room.kind] || [1, 1];
    let spot = null;
    for (let y = 0; y < 24 && !spot; y += 1) {
      for (let x = 0; x <= COLS - w; x += 1) {
        if (free(x, y, w, h)) {
          spot = { x, y, w, h };
          break;
        }
      }
    }
    if (!spot) {
      spot = { x: 0, y: maxY + 1, w, h };
    }
    occupy(spot.x, spot.y, spot.w, spot.h);
    maxY = Math.max(maxY, spot.y + spot.h - 1);
    placed.push({ ...room, ...spot });
  });

  let ox = 0;
  outdoor.forEach((room) => {
    const [w, h] = SPAN[room.kind] || [2, 1];
    const y = maxY + 1;
    placed.push({ ...room, x: ox, y, w, h });
    ox += w;
    maxY = Math.max(maxY, y);
  });

  return { placed, rows: Math.max(1, maxY + 1) };
}
