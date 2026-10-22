// Deterministic visual placement only. Counts come exclusively from Product Data.
// Area = PI * 8^2 * demand, with one shared camera scale (no per-node clipping).
export function bubbleLayout(items, radiusScale = 8) {
  const sorted = [...items].sort((a, b) => (b.layoutValue ?? b.value) - (a.layoutValue ?? a.value) || a.id.localeCompare(b.id));
  const nodes = [];
  const grid = new Map();
  const cellSize = 100;
  let cursor = 0;
  let extent = 1;
  let extentX = 1;
  let extentY = 1;
  const cells = (x, y, r) => {
    const keys = [];
    for (let ix = Math.floor((x - r) / cellSize); ix <= Math.floor((x + r) / cellSize); ix++) {
      for (let iy = Math.floor((y - r) / cellSize); iy <= Math.floor((y + r) / cellSize); iy++) keys.push(`${ix},${iy}`);
    }
    return keys;
  };
  for (const item of sorted) {
    const layoutValue = item.layoutValue ?? item.value;
    if (!(layoutValue > 0)) continue;
    // One scale is shared by all siblings, so bubble area remains proportional
    // to the demand metric while each drill-down level stays readable.
    const r = radiusScale * Math.sqrt(layoutValue);
    let x, y, keys;
    // A spatial grid avoids pairwise collision scans across the entire market.
    while (true) {
      // An elliptical golden-angle spiral creates a denser, more organic field
      // than a symmetric cone while remaining deterministic and collision-safe.
      const index = cursor++;
      const angle = index * 2.399963229728653;
      const distance = 9 * Math.sqrt(index);
      x = Math.cos(angle) * distance * 1.58 + Math.sin(index * .71) * 3;
      y = Math.sin(angle) * distance * .78 + Math.cos(index * .53) * 2;
      keys = cells(x, y, r + 3);
      const neighbors = new Set(keys.flatMap(key => grid.get(key) || []));
      // Deliberately retain a generous spatial gutter. The map is a reading
      // surface, not a container that needs to be filled edge-to-edge.
      if ([...neighbors].every(n => Math.hypot(x - n.x, y - n.y) >= r + n.r + 8)) break;
    }
    const node = { ...item, x, y, r };
    nodes.push(node);
    for (const key of keys) {
      if (!grid.has(key)) grid.set(key, []);
      grid.get(key).push(node);
    }
    extent = Math.max(extent, Math.abs(x) + r, Math.abs(y) + r);
    extentX = Math.max(extentX, Math.abs(x) + r);
    extentY = Math.max(extentY, Math.abs(y) + r);
  }
  return { nodes, extent, extentX, extentY };
}
