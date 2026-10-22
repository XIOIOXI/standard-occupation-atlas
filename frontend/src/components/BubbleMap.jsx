import React, { useEffect, useMemo, useRef, useState } from 'react';
import { bubbleLayout } from '../lib/bubbleLayout.js';
import { useMapCamera } from '../hooks/useMapCamera.js';
import { touchBubbleAction } from '../lib/cameraGestures.js';

export default function BubbleMap({ items, label, onSelect, focusId, focusRevision = 0, metricLabel = '面积 = 招聘岗位记录数', countUnit = '岗位', transition = false, onZoomChange, onSemanticZoomChange, snapWheel = false, semanticExpansionCount = 5, semanticGlobalCount = 0, semanticStepCount = 8, variant = 'default', subject: subjectOverride, showInspector = true, showLegend = true, showZoomControls = true }) {
  const radiusScale = useMemo(() => {
    const max = Math.max(...items.map(item => item.value), 1);
    return Math.max(.9, Math.min(34, 72 / Math.sqrt(max)));
  }, [items]);
  const layout = useMemo(() => bubbleLayout(items, radiusScale), [items, radiusScale]);
  // Start a large market at a readable scale; Fit reveals the entire extent.
  const camera = useMapCamera({ x: layout.extentX, y: layout.extentY }, items.length > 1000 ? .42 : 0, { snapWheel, snapWheelCount: semanticExpansionCount, snapWheelGlobalCount: semanticGlobalCount, snapWheelStepCount: semanticStepCount, onSnapWheel: onSemanticZoomChange });
  const timer = useRef(null);
  const pendingDesktopNode = useRef(null);
  const ignoreNextClick = useRef(false);
  const [activeId, setActiveId] = useState(null);
  const [touchSelectedId, setTouchSelectedId] = useState(null);
  const { x, y, zoom, animate } = camera.camera;
  // Programmatic focus is a drill-down transition, not a user request to reveal
  // a denser dataset. Callers receive the animation flag to keep those concerns
  // separate.
  useEffect(() => { onZoomChange?.(zoom, animate); }, [onZoomChange, zoom, animate]);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    clearTimeout(timer.current);
    const node = layout.nodes.find(n => n.id === focusId);
    if (node) camera.focus(node);
    // Focus follows the selected ID and viewport resize, not each camera movement.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId, focusRevision, layout, camera.size]);
  const visible = layout.nodes.filter(n => focusId === n.id || (n.x + n.r) * zoom + x >= 0 &&
    (n.x - n.r) * zoom + x <= camera.size.width && (n.y + n.r) * zoom + y >= 0 && (n.y - n.r) * zoom + y <= camera.size.height);
  function enter(node) {
    setActiveId(node.id);
    clearTimeout(timer.current);
    if (transition) {
      camera.focus(node);
      timer.current = setTimeout(() => onSelect(node.id), 420);
    } else onSelect(node.id);
  }
  function select(node, event) {
    if (ignoreNextClick.current) { ignoreNextClick.current = false; return; }
    // Pointer Events are supported in current iOS Safari. Restrict the
    // two-tap behaviour to an explicit touch event so desktop mouse clicks
    // always remain direct drill-down actions.
    const pointerType = event.nativeEvent?.pointerType;
    const isTouchTap = pointerType === 'touch';
    if (!isTouchTap) camera.consumeTouchTap();
    if (isTouchTap) {
      if (touchBubbleAction(touchSelectedId, node.id) === 'select') {
        setTouchSelectedId(node.id);
        setActiveId(node.id);
        return;
      }
    }
    enter(node);
  }
  function clearSelection(event) {
    if (!event.target.closest('.market-bubble')) {
      camera.consumeTouchTap();
      setActiveId(null);
      setTouchSelectedId(null);
    }
  }
  function markDesktopCandidate(node, event) {
    if (event.pointerType !== 'touch' && event.button === 0) pendingDesktopNode.current = { node, pointerId: event.pointerId };
  }
  function completePointerUp(event) {
    camera.handlers.onPointerUp(event);
    const candidate = pendingDesktopNode.current;
    pendingDesktopNode.current = null;
    if (candidate?.pointerId === event.pointerId && camera.consumeDesktopTap()) {
      ignoreNextClick.current = true;
      enter(candidate.node);
    }
  }
  const activeNode = layout.nodes.find(node => node.id === activeId || touchSelectedId === node.id || (!activeId && node.id === focusId));
  const subject = subjectOverride || (variant === 'industry' ? '行业' : '职业');
  return <div className="bubble-map">
    <div className={`bubble-canvas bubble-canvas--${variant}${transition ? ' has-drill-motion' : ''}`} ref={camera.ref} {...camera.handlers} onPointerUp={completePointerUp} onClick={clearSelection}>
    <svg className="bubble-svg" aria-label={label} role="group" data-total-nodes={layout.nodes.length}>
      <g className={animate ? 'camera animated' : 'camera'} transform={`translate(${x} ${y}) scale(${zoom})`}>
        {visible.map(node => {
          const screenRadius = node.r * zoom;
          const isActive = activeId === node.id;
          // Dense semantic-zoom additions remain identifiable. Small circles
          // carry a compact name; only circles with sufficient room carry a
          // second demand line, so the field stays readable.
          const showLabel = node.empty || screenRadius >= 19 || focusId === node.id || isActive;
          const showCount = node.empty || screenRadius >= 38 || focusId === node.id || isActive;
          const screenFont = Math.min(14, Math.max(9, screenRadius * .28));
          const font = screenFont / zoom;
          const compactLabelLength = showCount ? 12 : screenRadius < 22 ? 3 : 6;
          // Display projections can contain a level-2 direct-position bucket
          // with no level-3 catalog label.  A missing display label must not
          // crash the entire map.
          const nodeLabel = String(node.label ?? '未命名岗位');
          const shortLabel = nodeLabel.length <= compactLabelLength ? nodeLabel : `${nodeLabel.slice(0, compactLabelLength - 1)}…`;
          return <g key={node.id} className={`market-bubble${node.empty ? ' empty-direction' : ''}${focusId === node.id ? ' focused search-highlighted' : ''}${isActive ? ' active' : ''}`}
            role="button" tabIndex={0} aria-label={`${nodeLabel}，${node.value} 个${countUnit}`} data-id={node.id} data-demand={node.value}
            transform={`translate(${node.x} ${node.y})`} onPointerDown={event => markDesktopCandidate(node, event)} onClick={event => select(node, event)}
            onMouseEnter={() => setActiveId(node.id)} onMouseLeave={() => setActiveId(null)}
            onFocus={() => setActiveId(node.id)} onBlur={() => setActiveId(null)}
            onKeyDown={event => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); enter(node); } }}>
            <title>{nodeLabel} · {node.value} 个${countUnit}</title>
            <circle r={node.r} className="bubble-halo" vectorEffect="non-scaling-stroke" />
            <circle r={node.r} className="bubble-body" vectorEffect="non-scaling-stroke" />
            {showLabel && <text textAnchor="middle" fontSize={font} dy={-font * .05}>
              <tspan x="0" dy={showCount ? -font * .05 : font * .32}>{(isActive || focusId === node.id) ? nodeLabel : shortLabel}</tspan>
              {showCount && <tspan x="0" dy={font * 1.6} className="bubble-count">{node.empty ? '暂无岗位' : <>{node.value.toLocaleString()} <tspan className="bubble-unit">{countUnit}</tspan></>}</tspan>}
            </text>}
          </g>;
        })}
      </g>
    </svg>
    {showLegend && <div className="map-legend">{metricLabel}<br />拖动浏览 · 滚轮缩放 · 点击深入</div>}
    {showZoomControls && <div className="zoom-controls"><button aria-label="放大" onClick={() => camera.zoomBy(1.4)}>+</button><button aria-label="缩小" onClick={() => camera.zoomBy(1 / 1.4)}>−</button><button className="fit-map" aria-label="适应画布" onClick={camera.fit}>适应</button></div>}
    </div>
    {showInspector && <div className="bubble-inspector" aria-live="polite">{activeNode ? <><span>{subject}</span><strong>{activeNode.label}</strong><small>{activeNode.value.toLocaleString()} 个{countUnit}</small><button className="inspector-enter" onClick={event => { event.stopPropagation(); enter(activeNode); }}>进入{variant === 'industry' ? '职业方向探索' : '职业详情'} →</button></> : <><span>{subject}探索</span><strong>移动光标至气泡</strong><small>点按气泡查看名称与下级数量</small></>}</div>}
  </div>;
}
