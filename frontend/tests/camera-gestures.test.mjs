import test from 'node:test';
import assert from 'node:assert/strict';
import { MAX_ZOOM, MIN_ZOOM, SNAP_WHEEL_FACTOR, clampZoom, fitCamera, pinchCamera, resizeCamera, shouldSuppressTap, snapWheelCamera, touchBubbleAction } from '../src/lib/cameraGestures.js';

test('pinch keeps the world point beneath the finger centre anchored', () => {
  const camera = { x: 120, y: 80, zoom: 2, animate: false };
  const previous = { first: { x: 200, y: 150 }, second: { x: 300, y: 150 } };
  const next = { first: { x: 170, y: 140 }, second: { x: 370, y: 140 } };
  const result = pinchCamera(camera, previous, next);
  assert.equal(result.zoom, 4);
  // The old centre maps to world (65, 35); that world coordinate remains at
  // the new centre (270, 140), including centre movement during the pinch.
  assert.equal(result.x + 65 * result.zoom, 270);
  assert.equal(result.y + 35 * result.zoom, 140);
});

test('pinch scale respects the existing minimum and maximum camera bounds', () => {
  const pair = { first: { x: 0, y: 0 }, second: { x: 100, y: 0 } };
  assert.equal(pinchCamera({ x: 0, y: 0, zoom: MAX_ZOOM, animate: false }, pair,
    { first: { x: 0, y: 0 }, second: { x: 400, y: 0 } }).zoom, MAX_ZOOM);
  assert.equal(pinchCamera({ x: 0, y: 0, zoom: MIN_ZOOM, animate: false }, pair,
    { first: { x: 0, y: 0 }, second: { x: 1, y: 0 } }).zoom, MIN_ZOOM);
  assert.equal(clampZoom(100), MAX_ZOOM);
  assert.equal(clampZoom(0), MIN_ZOOM);
});

test('dragging or pinching suppresses the follow-up click', () => {
  assert.equal(shouldSuppressTap({ moved: true, pinched: false }), true);
  assert.equal(shouldSuppressTap({ moved: false, pinched: true }), true);
  assert.equal(shouldSuppressTap({ moved: false, pinched: false }), false);
});

test('a touch bubble selects first and enters on a second tap', () => {
  assert.equal(touchBubbleAction(null, 'industry-1'), 'select');
  assert.equal(touchBubbleAction('industry-1', 'industry-1'), 'enter');
  assert.equal(touchBubbleAction('industry-1', 'industry-2'), 'select');
});

test('fit-to-view uses the measured mobile canvas dimensions', () => {
  const camera = fitCamera({ width: 375, height: 400 }, { x: 500, y: 300 });
  assert.equal(camera.zoom, .3375);
  assert.equal(camera.x, 187.5);
  assert.equal(camera.y, 200);
});

test('resizing preserves the viewed world centre without reducing below fit', () => {
  const camera = { x: 100, y: 120, zoom: 2, animate: false };
  const next = resizeCamera(camera, { width: 400, height: 500 }, { width: 600, height: 300 }, .8);
  assert.equal(next.zoom, 2);
  assert.equal((300 - next.x) / next.zoom, (200 - camera.x) / camera.zoom);
  assert.equal((150 - next.y) / next.zoom, (250 - camera.y) / camera.zoom);
  assert.equal(resizeCamera({ ...camera, zoom: .3 }, { width: 400, height: 500 }, { width: 600, height: 300 }, .8).zoom, .8);
});

test('semantic wheel zoom expands in one anchored motion', () => {
  const camera = { x: 200, y: 150, zoom: 1, animate: false };
  const next = snapWheelCamera(camera, 320, 210);
  assert.equal(next.zoom, SNAP_WHEEL_FACTOR);
  assert.equal((320 - next.x) / next.zoom, (320 - camera.x) / camera.zoom);
  assert.equal((210 - next.y) / next.zoom, (210 - camera.y) / camera.zoom);
});
