import { useCallback, useEffect, useRef, useState } from 'react';
import { clampZoom, fitCamera, pinchCamera, resizeCamera, shouldSuppressTap, snapWheelCamera } from '../lib/cameraGestures.js';

const DRAG_THRESHOLD = 10;
// The first wheel event is the deliberate semantic-zoom action. High-resolution
// mice and trackpads can emit a very small delta, so waiting for accumulated
// movement made users scroll twice before the first expansion. The cooldown
// below still prevents a dense stream from adding multiple batches at once.
const WHEEL_DIRECTION_THRESHOLD = 1;
const SNAP_COOLDOWN_MS = 500;

export function useMapCamera(extent, initialZoom = 0, { snapWheel = false, snapWheelCount = 5, snapWheelGlobalCount = 0, snapWheelStepCount = 8, onSnapWheel } = {}) {
  const ref = useRef(null);
  const pointers = useRef(new Map());
  const drag = useRef(null);
  const pinch = useRef(null);
  const interaction = useRef({ moved: false, pinched: false, touchTap: false, desktopTap: false, pointerType: null });
  const hasInteracted = useRef(false);
  const snapWheelActive = useRef(false);
  const snapWheelCooldownUntil = useRef(0);
  const wheelDirectionDelta = useRef(0);
  const fitAfterSemanticChange = useRef(false);
  const semanticCount = useRef(snapWheelGlobalCount);
  const onSnapWheelRef = useRef(onSnapWheel);
  const priorSize = useRef(null);
  const priorExtent = useRef(null);
  const cameraRef = useRef({ x: 450, y: 325, zoom: 1, animate: false });
  const [size, setSize] = useState({ width: 900, height: 650 });
  const [camera, setCamera] = useState(cameraRef.current);
  const extentX = typeof extent === 'number' ? extent : extent.x;
  const extentY = typeof extent === 'number' ? extent : extent.y;
  const fittedZoom = Math.min(size.width * .45 / extentX, size.height * .45 / extentY);
  const restingZoom = clampZoom(Math.max(initialZoom, fittedZoom));
  const commitCamera = useCallback(next => { cameraRef.current = next; setCamera(next); }, []);
  useEffect(() => { onSnapWheelRef.current = onSnapWheel; }, [onSnapWheel]);
  const fit = useCallback(() => {
    hasInteracted.current = true;
    snapWheelActive.current = false;
    fitAfterSemanticChange.current = false;
    semanticCount.current = snapWheelGlobalCount;
    onSnapWheelRef.current?.(snapWheelGlobalCount);
    commitCamera({ ...fitCamera(size, { x: extentX, y: extentY }, initialZoom), animate: true });
  }, [size, extentX, extentY, initialZoom, commitCamera]);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setSize({ width: entry.contentRect.width, height: entry.contentRect.height }));
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const previous = priorSize.current;
    const previousExtent = priorExtent.current;
    const extentChanged = Boolean(previousExtent && (previousExtent.x !== extentX || previousExtent.y !== extentY));
    const next = !previous || !hasInteracted.current
      ? fitCamera(size, { x: extentX, y: extentY }, initialZoom)
      : fitAfterSemanticChange.current && extentChanged
        ? (fitAfterSemanticChange.current = false, { ...fitCamera(size, { x: extentX, y: extentY }, initialZoom), animate: true })
      : snapWheelActive.current && extentChanged
        // Entering the denser view already zoomed at the wheel anchor. Keep
        // that reading view; fitting new nodes here made an upward scroll look
        // like an unexpected zoom-out to the global map.
        ? { ...cameraRef.current, animate: true }
      : resizeCamera(cameraRef.current, previous, size, Math.max(initialZoom, fittedZoom));
    priorSize.current = size;
    priorExtent.current = { x: extentX, y: extentY };
    commitCamera(next);
  }, [size, fittedZoom, initialZoom, extentX, extentY, commitCamera]);
  const zoomAt = useCallback((factor, x, y) => {
    hasInteracted.current = true;
    const current = cameraRef.current;
    const zoom = clampZoom(current.zoom * factor);
    commitCamera({ x: x - (x - current.x) * zoom / current.zoom,
      y: y - (y - current.y) * zoom / current.zoom, zoom, animate: false });
  }, [commitCamera]);
  useEffect(() => {
    const element = ref.current;
    const wheel = event => {
      event.preventDefault();
      const rect = element.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      if (snapWheel) {
        const now = performance.now();
        if (now < snapWheelCooldownUntil.current) return;
        wheelDirectionDelta.current += event.deltaY;
        if (Math.abs(wheelDirectionDelta.current) < WHEEL_DIRECTION_THRESHOLD) return;
        const direction = Math.sign(wheelDirectionDelta.current);
        wheelDirectionDelta.current = 0;
        snapWheelCooldownUntil.current = now + SNAP_COOLDOWN_MS;
        // Keep the gesture semantics fixed instead of deriving them from the
        // first wheel direction: up enters the enlarged field once, while
        // down always returns to the global fit view.
        if (direction < 0) {
          const baseCount = snapWheelActive.current ? semanticCount.current : snapWheelGlobalCount;
          const nextCount = Math.min(snapWheelCount, baseCount + snapWheelStepCount);
          if (nextCount === baseCount) return;
          hasInteracted.current = true;
          snapWheelActive.current = true;
          fitAfterSemanticChange.current = false;
          semanticCount.current = nextCount;
          onSnapWheelRef.current?.(nextCount);
          commitCamera(snapWheelCamera(cameraRef.current, x, y));
        } else if (direction > 0) {
          // A first downward wheel gesture is meaningful too: it opens the
          // wider, forty-node global view from the initial primary-only view.
          // Subsequent downward gestures simply retain that same global view.
          snapWheelActive.current = false;
          fitAfterSemanticChange.current = true;
          semanticCount.current = snapWheelGlobalCount;
          onSnapWheelRef.current?.(snapWheelGlobalCount);
          commitCamera({ ...fitCamera(size, { x: extentX, y: extentY }, initialZoom), animate: true });
        }
        return;
      }
      zoomAt(Math.exp(-Math.max(-100, Math.min(100, event.deltaY)) * .003), x, y);
    };
    element.addEventListener('wheel', wheel, { passive: false });
    return () => element.removeEventListener('wheel', wheel);
  }, [commitCamera, fit, snapWheel, snapWheelCount, snapWheelGlobalCount, snapWheelStepCount, zoomAt]);
  const points = () => [...pointers.current.entries()].slice(0, 2).map(([id, point]) => ({ id, ...point }));
  const pair = () => { const [first, second] = points(); return first && second ? { first, second } : null; };
  const release = (target, pointerId) => { if (target.hasPointerCapture?.(pointerId)) target.releasePointerCapture(pointerId); };
  const beginSingleDrag = () => { const [point] = points(); if (point) drag.current = { pointerId: point.id, clientX: point.x, clientY: point.y, camera: cameraRef.current }; };
  return { ref, camera, size, fit, restingZoom,
    focus: node => { const zoom = clampZoom(Math.min(size.width, size.height) * .28 / node.r);
      commitCamera({ x: size.width / 2 - node.x * zoom, y: size.height / 2 - node.y * zoom, zoom, animate: true }); },
    zoomBy: factor => zoomAt(factor, size.width / 2, size.height / 2),
    consumeTouchTap: () => { const value = interaction.current.touchTap; interaction.current.touchTap = false; return value; },
    consumeDesktopTap: () => { const value = interaction.current.desktopTap; interaction.current.desktopTap = false; return value; },
    handlers: {
      onPointerDown: event => {
        if ((event.pointerType === 'mouse' && event.button !== 0) || event.target.closest('button')) return;
        event.currentTarget.setPointerCapture?.(event.pointerId);
        pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
        if (pointers.current.size === 1) { interaction.current = { moved: false, pinched: false, touchTap: false, desktopTap: false, pointerType: event.pointerType }; beginSingleDrag(); }
        else if (pointers.current.size === 2) { drag.current = null; pinch.current = pair(); interaction.current.moved = true; interaction.current.pinched = true; }
      },
      onPointerMove: event => {
        if (!pointers.current.has(event.pointerId)) return;
        pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
        if (pointers.current.size >= 2 && pinch.current) { const next = pair(); if (!next) return;
          hasInteracted.current = true; commitCamera(pinchCamera(cameraRef.current, pinch.current, next)); pinch.current = next; interaction.current.moved = true; interaction.current.pinched = true; return; }
        if (!drag.current || drag.current.pointerId !== event.pointerId) return;
        const dx = event.clientX - drag.current.clientX, dy = event.clientY - drag.current.clientY;
        if (!interaction.current.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
        hasInteracted.current = true;
        interaction.current.moved = true;
        commitCamera({ x: drag.current.camera.x + dx, y: drag.current.camera.y + dy, zoom: drag.current.camera.zoom, animate: false });
      },
      onPointerUp: event => {
        const wasTouch = event.pointerType === 'touch'; pointers.current.delete(event.pointerId); release(event.currentTarget, event.pointerId);
        if (pointers.current.size >= 2) { pinch.current = pair(); return; }
        if (pointers.current.size === 1) { pinch.current = null; beginSingleDrag(); return; }
        drag.current = null; pinch.current = null;
        interaction.current.touchTap = wasTouch && !shouldSuppressTap(interaction.current);
        interaction.current.desktopTap = !wasTouch && !shouldSuppressTap(interaction.current);
      },
      onPointerCancel: event => { pointers.current.delete(event.pointerId); release(event.currentTarget, event.pointerId); drag.current = null; pinch.current = pointers.current.size >= 2 ? pair() : null; interaction.current.moved = true; },
      onLostPointerCapture: event => { pointers.current.delete(event.pointerId); drag.current = null; pinch.current = pointers.current.size >= 2 ? pair() : null; },
      onPointerLeave: () => { if (!interaction.current.moved && pointers.current.size < 2) drag.current = null; },
      onClickCapture: event => {
        // Pointer capture causes a dragged mouse gesture to finish on the
        // canvas rather than a bubble. Only touch gestures need explicit
        // click suppression; desktop clicks must remain direct drill-downs.
        if (shouldSuppressTap(interaction.current) && interaction.current.pointerType === 'touch') event.stopPropagation();
        interaction.current.touchTap = false;
        interaction.current.desktopTap = false;
        interaction.current.moved = false;
        interaction.current.pinched = false;
      },
    },
  };
}
