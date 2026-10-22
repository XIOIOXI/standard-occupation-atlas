export const MIN_ZOOM = .02;
export const MAX_ZOOM = 40;

export const clampZoom = value => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));

export const pointDistance = (first, second) => Math.hypot(first.x - second.x, first.y - second.y);
export const pointCenter = (first, second) => ({ x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 });

// Keep the market coordinate beneath the two-finger centre fixed as the
// fingers move. This supports both a changing pinch distance and centre.
export function pinchCamera(camera, previous, next) {
  const previousDistance = pointDistance(previous.first, previous.second);
  const nextDistance = pointDistance(next.first, next.second);
  if (!previousDistance || !nextDistance) return camera;
  const previousCenter = pointCenter(previous.first, previous.second);
  const nextCenter = pointCenter(next.first, next.second);
  const zoom = clampZoom(camera.zoom * nextDistance / previousDistance);
  const worldX = (previousCenter.x - camera.x) / camera.zoom;
  const worldY = (previousCenter.y - camera.y) / camera.zoom;
  return { x: nextCenter.x - worldX * zoom, y: nextCenter.y - worldY * zoom, zoom, animate: false };
}

export const shouldSuppressTap = ({ moved = false, pinched = false }) => moved || pinched;
export const touchBubbleAction = (selectedId, nodeId) => selectedId === nodeId ? 'enter' : 'select';

// Semantic expansion is tied to deliberate wheel zoom, not to the initial
// fit-to-view camera. Every 18% beyond the resting scale reveals one real
// lower-demand occupation, capped so the field remains legible.
export const SNAP_WHEEL_FACTOR = 1.8;

export function snapWheelCamera(camera, x, y, factor = SNAP_WHEEL_FACTOR) {
  const zoom = clampZoom(camera.zoom * factor);
  return {
    x: x - (x - camera.x) * zoom / camera.zoom,
    y: y - (y - camera.y) * zoom / camera.zoom,
    zoom,
    animate: true,
  };
}

export function fitCamera(size, extent, initialZoom = 0) {
  const extentX = typeof extent === 'number' ? extent : extent.x;
  const extentY = typeof extent === 'number' ? extent : extent.y;
  const zoom = Math.max(initialZoom, Math.min(size.width * .45 / extentX, size.height * .45 / extentY));
  return { x: size.width / 2, y: size.height / 2, zoom: clampZoom(zoom), animate: false };
}

export function resizeCamera(camera, previousSize, nextSize, minimumZoom) {
  const zoom = Math.max(minimumZoom, camera.zoom);
  const worldX = (previousSize.width / 2 - camera.x) / camera.zoom;
  const worldY = (previousSize.height / 2 - camera.y) / camera.zoom;
  return { x: nextSize.width / 2 - worldX * zoom, y: nextSize.height / 2 - worldY * zoom, zoom, animate: false };
}
