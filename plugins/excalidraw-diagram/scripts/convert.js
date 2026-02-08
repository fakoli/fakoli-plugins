#!/usr/bin/env node
/**
 * Excalidraw Skeleton-to-File Converter
 *
 * Expands a compact "skeleton" JSON into a full .excalidraw file.
 * Zero npm dependencies. Requires Node.js >= 18.
 *
 * Usage:
 *   node convert.js <input.json> [output.excalidraw]
 *   node convert.js --stdin [output.excalidraw]       # read skeleton from stdin
 *   node convert.js --modify <existing.excalidraw> <input.json> [output.excalidraw]
 */

"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

// ─── Excalidraw Constants ──────────────────────────────────────────────────────

const COLOR_PALETTE = {
  transparent: "transparent",
  black: "#1e1e1e",
  white: "#ffffff",
  gray: ["#f8f9fa", "#e9ecef", "#ced4da", "#868e96", "#343a40"],
  red: ["#fff5f5", "#ffc9c9", "#ff8787", "#fa5252", "#e03131"],
  pink: ["#fff0f6", "#fcc2d7", "#f783ac", "#e64980", "#c2255c"],
  grape: ["#f8f0fc", "#eebefa", "#da77f2", "#be4bdb", "#9c36b5"],
  violet: ["#f3f0ff", "#d0bfff", "#9775fa", "#7950f2", "#6741d9"],
  blue: ["#e7f5ff", "#a5d8ff", "#4dabf7", "#228be6", "#1971c2"],
  cyan: ["#e3fafc", "#99e9f2", "#3bc9db", "#15aabf", "#0c8599"],
  teal: ["#e6fcf5", "#96f2d7", "#38d9a9", "#12b886", "#099268"],
  green: ["#ebfbee", "#b2f2bb", "#69db7c", "#40c057", "#2f9e44"],
  yellow: ["#fff9db", "#ffec99", "#ffd43b", "#fab005", "#f08c00"],
  orange: ["#fff4e6", "#ffd8a8", "#ffa94d", "#fd7e14", "#e8590c"],
  bronze: ["#f8f1ee", "#eaddd7", "#d2bab0", "#a18072", "#846358"],
};

// Semantic color name -> [strokeColor, backgroundColor]
const THEME_COLORS = {
  default: {
    blue:    { stroke: COLOR_PALETTE.blue[3],   bg: COLOR_PALETTE.blue[0] },
    red:     { stroke: COLOR_PALETTE.red[3],    bg: COLOR_PALETTE.red[0] },
    green:   { stroke: COLOR_PALETTE.green[3],  bg: COLOR_PALETTE.green[0] },
    orange:  { stroke: COLOR_PALETTE.orange[3], bg: COLOR_PALETTE.orange[0] },
    violet:  { stroke: COLOR_PALETTE.violet[3], bg: COLOR_PALETTE.violet[0] },
    yellow:  { stroke: COLOR_PALETTE.yellow[3], bg: COLOR_PALETTE.yellow[0] },
    cyan:    { stroke: COLOR_PALETTE.cyan[3],   bg: COLOR_PALETTE.cyan[0] },
    teal:    { stroke: COLOR_PALETTE.teal[3],   bg: COLOR_PALETTE.teal[0] },
    pink:    { stroke: COLOR_PALETTE.pink[3],   bg: COLOR_PALETTE.pink[0] },
    grape:   { stroke: COLOR_PALETTE.grape[3],  bg: COLOR_PALETTE.grape[0] },
    gray:    { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    black:   { stroke: COLOR_PALETTE.black,     bg: COLOR_PALETTE.transparent },
    white:   { stroke: COLOR_PALETTE.gray[2],   bg: COLOR_PALETTE.white },
    bronze:  { stroke: COLOR_PALETTE.bronze[3], bg: COLOR_PALETTE.bronze[0] },
  },
  blueprint: {
    blue:    { stroke: "#a5d8ff", bg: "transparent" },
    red:     { stroke: "#ffc9c9", bg: "transparent" },
    green:   { stroke: "#b2f2bb", bg: "transparent" },
    orange:  { stroke: "#ffd8a8", bg: "transparent" },
    violet:  { stroke: "#d0bfff", bg: "transparent" },
    yellow:  { stroke: "#ffec99", bg: "transparent" },
    cyan:    { stroke: "#99e9f2", bg: "transparent" },
    teal:    { stroke: "#96f2d7", bg: "transparent" },
    pink:    { stroke: "#fcc2d7", bg: "transparent" },
    grape:   { stroke: "#eebefa", bg: "transparent" },
    gray:    { stroke: "#ced4da", bg: "transparent" },
    black:   { stroke: "#e9ecef", bg: "transparent" },
    white:   { stroke: "#ced4da", bg: "transparent" },
    bronze:  { stroke: "#eaddd7", bg: "transparent" },
  },
  warm: {
    blue:    { stroke: COLOR_PALETTE.blue[3],   bg: COLOR_PALETTE.yellow[0] },
    red:     { stroke: COLOR_PALETTE.red[3],    bg: COLOR_PALETTE.orange[0] },
    green:   { stroke: COLOR_PALETTE.green[3],  bg: COLOR_PALETTE.yellow[0] },
    orange:  { stroke: COLOR_PALETTE.orange[3], bg: COLOR_PALETTE.orange[0] },
    violet:  { stroke: COLOR_PALETTE.violet[3], bg: COLOR_PALETTE.pink[0] },
    yellow:  { stroke: COLOR_PALETTE.yellow[3], bg: COLOR_PALETTE.yellow[0] },
    cyan:    { stroke: COLOR_PALETTE.cyan[3],   bg: COLOR_PALETTE.teal[0] },
    teal:    { stroke: COLOR_PALETTE.teal[3],   bg: COLOR_PALETTE.green[0] },
    pink:    { stroke: COLOR_PALETTE.pink[3],   bg: COLOR_PALETTE.pink[0] },
    grape:   { stroke: COLOR_PALETTE.grape[3],  bg: COLOR_PALETTE.grape[0] },
    gray:    { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    black:   { stroke: COLOR_PALETTE.black,     bg: COLOR_PALETTE.transparent },
    white:   { stroke: COLOR_PALETTE.gray[2],   bg: COLOR_PALETTE.white },
    bronze:  { stroke: COLOR_PALETTE.bronze[3], bg: COLOR_PALETTE.bronze[0] },
  },
  monochrome: {
    blue:    { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    red:     { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    green:   { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    orange:  { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    violet:  { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    yellow:  { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    cyan:    { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    teal:    { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    pink:    { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    grape:   { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    gray:    { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
    black:   { stroke: COLOR_PALETTE.black,     bg: COLOR_PALETTE.transparent },
    white:   { stroke: COLOR_PALETTE.gray[2],   bg: COLOR_PALETTE.white },
    bronze:  { stroke: COLOR_PALETTE.gray[3],   bg: COLOR_PALETTE.gray[0] },
  },
};

const DEFAULT_COLOR = "blue";
const FONT_FAMILY_EXCALIFONT = 5;
const FONT_FAMILY_NUNITO = 6;

const ROUNDNESS = {
  LEGACY: 1,
  PROPORTIONAL_RADIUS: 2,
  ADAPTIVE_RADIUS: 3,
};

// ─── Utility Functions ─────────────────────────────────────────────────────────

function randomId() {
  return crypto.randomBytes(10).toString("base64url").slice(0, 20);
}

function randomSeed() {
  return Math.floor(Math.random() * 2147483647) + 1;
}

function generateFractionalIndex(i, total) {
  // Simple fractional index: a0, a1, a2, ...
  const base = "a";
  const idx = i.toString(36).padStart(5, "0");
  return base + idx;
}

function estimateTextWidth(text, fontSize) {
  // Character-class-based width estimation for Excalifont
  const narrow = /[ilj1!|.,;:'"()\[\]{}]/;
  const wide = /[MWmw@%]/;
  const lines = text.split("\n");
  let maxWidth = 0;
  for (const line of lines) {
    let w = 0;
    for (const ch of line) {
      if (narrow.test(ch)) w += fontSize * 0.35;
      else if (wide.test(ch)) w += fontSize * 0.8;
      else if (ch === " ") w += fontSize * 0.3;
      else w += fontSize * 0.55;
    }
    maxWidth = Math.max(maxWidth, w);
  }
  return maxWidth + 8; // padding
}

function estimateTextHeight(text, fontSize, lineHeight) {
  const lines = text.split("\n");
  return lines.length * fontSize * (lineHeight || 1.25) + 4;
}

// ─── Color Resolution ──────────────────────────────────────────────────────────

function resolveColors(colorName, themeName) {
  const theme = THEME_COLORS[themeName] || THEME_COLORS.default;
  const resolved = theme[colorName] || theme[DEFAULT_COLOR];
  return resolved;
}

function isHexColor(str) {
  return /^#[0-9a-fA-F]{3,8}$/.test(str);
}

function resolveStrokeColor(colorName, themeName) {
  if (isHexColor(colorName)) return colorName;
  return resolveColors(colorName, themeName).stroke;
}

function resolveBackgroundColor(colorName, themeName) {
  if (isHexColor(colorName)) return colorName;
  return resolveColors(colorName, themeName).bg;
}

// ─── Element Builders ──────────────────────────────────────────────────────────

function baseElement(id, type, index) {
  return {
    id,
    type,
    x: 0,
    y: 0,
    width: 0,
    height: 0,
    angle: 0,
    strokeColor: COLOR_PALETTE.black,
    backgroundColor: COLOR_PALETTE.transparent,
    fillStyle: "solid",
    strokeWidth: 2,
    strokeStyle: "solid",
    roughness: 1,
    opacity: 100,
    groupIds: [],
    frameId: null,
    index: generateFractionalIndex(index, 0),
    roundness: null,
    seed: randomSeed(),
    version: 1,
    versionNonce: randomSeed(),
    isDeleted: false,
    boundElements: null,
    updated: Date.now(),
    link: null,
    locked: false,
  };
}

function buildShapeElement(skelEl, idMap, theme, index) {
  const id = idMap.get(skelEl.id) || randomId();
  const el = baseElement(id, skelEl.type, index);

  const colorName = skelEl.color || DEFAULT_COLOR;
  el.strokeColor = resolveStrokeColor(colorName, theme);
  el.backgroundColor = resolveBackgroundColor(colorName, theme);
  el.fillStyle = skelEl.fillStyle || "solid";
  el.strokeStyle = skelEl.strokeStyle || "solid";
  el.roughness = skelEl.roughness ?? 1;
  el.opacity = skelEl.opacity ?? 100;

  el.x = skelEl.x || 0;
  el.y = skelEl.y || 0;
  el.width = skelEl.width || 200;
  el.height = skelEl.height || 80;

  // Roundness
  if (skelEl.type === "diamond") {
    el.roundness = { type: ROUNDNESS.PROPORTIONAL_RADIUS };
  } else if (skelEl.type === "rectangle") {
    el.roundness = { type: ROUNDNESS.ADAPTIVE_RADIUS };
  } else if (skelEl.type === "ellipse") {
    el.roundness = null;
  }

  if (skelEl.groupIds) el.groupIds = skelEl.groupIds;
  if (skelEl.frameId) el.frameId = skelEl.frameId;

  return el;
}

function buildTextElement(text, containerId, index, opts = {}) {
  const id = randomId();
  const fontSize = opts.fontSize || 16;
  const lineHeight = opts.lineHeight || 1.25;
  const el = baseElement(id, "text", index);

  el.text = text;
  el.originalText = text;
  el.autoResize = true;
  el.fontSize = fontSize;
  el.fontFamily = opts.fontFamily || FONT_FAMILY_EXCALIFONT;
  el.textAlign = opts.textAlign || "center";
  el.verticalAlign = opts.verticalAlign || "middle";
  el.lineHeight = lineHeight;
  el.containerId = containerId || null;
  el.strokeColor = opts.strokeColor || COLOR_PALETTE.black;
  el.backgroundColor = COLOR_PALETTE.transparent;

  el.width = estimateTextWidth(text, fontSize);
  el.height = estimateTextHeight(text, fontSize, lineHeight);

  if (containerId) {
    el.textAlign = "center";
    el.verticalAlign = "middle";
  }

  return el;
}

function buildFreeTextElement(skelEl, idMap, theme, index) {
  const id = idMap.get(skelEl.id) || randomId();
  const fontSize = skelEl.fontSize || 20;
  const lineHeight = skelEl.lineHeight || 1.25;
  const el = baseElement(id, "text", index);

  const colorName = skelEl.color || "black";
  el.strokeColor = resolveStrokeColor(colorName, theme);

  el.text = skelEl.text || skelEl.label || "";
  el.originalText = el.text;
  el.autoResize = true;
  el.fontSize = fontSize;
  el.fontFamily = skelEl.fontFamily || FONT_FAMILY_EXCALIFONT;
  el.textAlign = skelEl.textAlign || "left";
  el.verticalAlign = skelEl.verticalAlign || "top";
  el.lineHeight = lineHeight;
  el.containerId = null;

  el.x = skelEl.x || 0;
  el.y = skelEl.y || 0;
  el.width = estimateTextWidth(el.text, fontSize);
  el.height = estimateTextHeight(el.text, fontSize, lineHeight);

  return el;
}

function computeFixedPoint(fromEl, toEl, isStart) {
  const fromCX = fromEl.x + fromEl.width / 2;
  const fromCY = fromEl.y + fromEl.height / 2;
  const toCX = toEl.x + toEl.width / 2;
  const toCY = toEl.y + toEl.height / 2;
  const dx = toCX - fromCX;
  const dy = toCY - fromCY;

  const sign = isStart ? 1 : -1;
  const absDx = Math.abs(dx);
  const absDy = Math.abs(dy);

  if (absDx > absDy) {
    // Horizontal dominant
    return (sign * dx > 0) ? [1.0, 0.5] : [0.0, 0.5];
  } else {
    // Vertical dominant
    return (sign * dy > 0) ? [0.5, 1.0] : [0.5, 0.0];
  }
}

function addBoundElement(el, entry) {
  if (!el.boundElements) el.boundElements = [];
  if (!el.boundElements.some((be) => be.id === entry.id)) {
    el.boundElements.push(entry);
  }
}

function buildArrowElement(skelEl, idMap, shapeElements, theme, index, existingElements) {
  const id = idMap.get(skelEl.id) || randomId();
  const el = baseElement(id, "arrow", index);

  const colorName = skelEl.color || "black";
  el.strokeColor = resolveStrokeColor(colorName, theme);
  el.backgroundColor = COLOR_PALETTE.transparent;
  el.fillStyle = "solid";
  el.strokeStyle = skelEl.style === "dashed" ? "dashed" : skelEl.style === "dotted" ? "dotted" : "solid";
  el.roughness = skelEl.roughness ?? 1;
  el.roundness = { type: ROUNDNESS.PROPORTIONAL_RADIUS };

  el.startArrowhead = skelEl.startArrowhead || null;
  el.endArrowhead = skelEl.endArrowhead !== undefined ? skelEl.endArrowhead : "arrow";
  el.startBinding = null;
  el.endBinding = null;
  el.lastCommittedPoint = null;

  // Resolve from/to — check idMap first, then fall back to existingElements
  let fromId = skelEl.from ? idMap.get(skelEl.from) : null;
  let toId = skelEl.to ? idMap.get(skelEl.to) : null;
  let fromEl = fromId ? shapeElements.get(fromId) : null;
  let toEl = toId ? shapeElements.get(toId) : null;

  // Fall back to existing elements (modification mode)
  if (!fromEl && skelEl.from && existingElements) {
    const existing = existingElements.get(skelEl.from);
    if (existing) {
      fromId = existing.id;
      fromEl = existing;
    }
  }
  if (!toEl && skelEl.to && existingElements) {
    const existing = existingElements.get(skelEl.to);
    if (existing) {
      toId = existing.id;
      toEl = existing;
    }
  }

  let startX, startY, endX, endY;

  if (fromEl && toEl) {
    // Compute arrow endpoints from shape centers
    const fromCX = fromEl.x + fromEl.width / 2;
    const fromCY = fromEl.y + fromEl.height / 2;
    const toCX = toEl.x + toEl.width / 2;
    const toCY = toEl.y + toEl.height / 2;

    startX = fromCX;
    startY = fromCY;
    endX = toCX;
    endY = toCY;

    // Compute edge-aware FixedPointBindings
    el.startBinding = {
      elementId: fromId,
      fixedPoint: computeFixedPoint(fromEl, toEl, true),
      mode: "orbit",
    };

    el.endBinding = {
      elementId: toId,
      fixedPoint: computeFixedPoint(fromEl, toEl, false),
      mode: "orbit",
    };

    // Add boundElements references to the shapes (with dedup)
    addBoundElement(fromEl, { type: "arrow", id: el.id });
    addBoundElement(toEl, { type: "arrow", id: el.id });
  } else {
    // Fallback: use explicit coordinates or defaults
    startX = skelEl.x || 0;
    startY = skelEl.y || 0;
    endX = (skelEl.x || 0) + (skelEl.width || 200);
    endY = (skelEl.y || 0) + (skelEl.height || 0);
  }

  el.x = startX;
  el.y = startY;

  const dx = endX - startX;
  const dy = endY - startY;

  el.points = [[0, 0], [dx, dy]];
  el.width = Math.abs(dx);
  el.height = Math.abs(dy);

  return el;
}

function buildLineElement(skelEl, idMap, shapeElements, theme, index) {
  const id = idMap.get(skelEl.id) || randomId();
  const el = baseElement(id, "line", index);

  const colorName = skelEl.color || "black";
  el.strokeColor = resolveStrokeColor(colorName, theme);
  el.backgroundColor = COLOR_PALETTE.transparent;
  el.strokeStyle = skelEl.style === "dashed" ? "dashed" : skelEl.style === "dotted" ? "dotted" : "solid";
  el.roughness = skelEl.roughness ?? 1;
  el.roundness = { type: ROUNDNESS.PROPORTIONAL_RADIUS };

  el.startArrowhead = null;
  el.endArrowhead = null;
  el.startBinding = null;
  el.endBinding = null;
  el.lastCommittedPoint = null;

  if (skelEl.points && skelEl.points.length >= 2) {
    el.x = skelEl.x || skelEl.points[0][0];
    el.y = skelEl.y || skelEl.points[0][1];
    el.points = skelEl.points.map((p) => [p[0] - el.x, p[1] - el.y]);
  } else {
    el.x = skelEl.x || 0;
    el.y = skelEl.y || 0;
    const w = skelEl.width || 200;
    const h = skelEl.height || 0;
    el.points = [[0, 0], [w, h]];
  }

  const xs = el.points.map((p) => p[0]);
  const ys = el.points.map((p) => p[1]);
  el.width = Math.max(...xs) - Math.min(...xs);
  el.height = Math.max(...ys) - Math.min(...ys);

  return el;
}

function buildFrameElement(skelEl, idMap, allElements, theme, index) {
  const id = idMap.get(skelEl.id) || randomId();
  const el = baseElement(id, "frame", index);

  el.strokeColor = "#bbb";
  el.backgroundColor = COLOR_PALETTE.transparent;
  el.fillStyle = "solid";
  el.strokeWidth = 2;
  el.strokeStyle = "solid";
  el.roughness = 0;
  el.roundness = null;
  el.name = skelEl.label || skelEl.name || null;

  // If explicit position/size
  if (skelEl.x != null) el.x = skelEl.x;
  if (skelEl.y != null) el.y = skelEl.y;
  if (skelEl.width != null) el.width = skelEl.width;
  if (skelEl.height != null) el.height = skelEl.height;

  return el;
}

// ─── Layout Algorithms ─────────────────────────────────────────────────────────

const SPACING_X = 60;
const SPACING_Y = 80;
const DEFAULT_WIDTH = 200;
const DEFAULT_HEIGHT = 80;

function layoutGrid(shapes) {
  if (shapes.length === 0) return;
  const cols = Math.ceil(Math.sqrt(shapes.length));

  // Compute per-column max width and per-row max height
  const colWidths = [];
  const rowHeights = [];
  for (let i = 0; i < shapes.length; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    colWidths[col] = Math.max(colWidths[col] || 0, shapes[i].width || DEFAULT_WIDTH);
    rowHeights[row] = Math.max(rowHeights[row] || 0, shapes[i].height || DEFAULT_HEIGHT);
  }

  // Position using cumulative widths/heights
  for (let i = 0; i < shapes.length; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    let x = 0;
    for (let c = 0; c < col; c++) x += colWidths[c] + SPACING_X;
    let y = 0;
    for (let r = 0; r < row; r++) y += rowHeights[r] + SPACING_Y;
    shapes[i].x = x;
    shapes[i].y = y;
  }
}

function layoutTopDown(shapes, arrows) {
  if (shapes.length === 0) return;
  // Build adjacency from arrows
  const adj = buildAdjacency(shapes, arrows);
  const levels = assignLevels(shapes, adj);
  positionByLevels(shapes, levels, "vertical");
}

function layoutLeftRight(shapes, arrows) {
  if (shapes.length === 0) return;
  const adj = buildAdjacency(shapes, arrows);
  const levels = assignLevels(shapes, adj);
  positionByLevels(shapes, levels, "horizontal");
}

function buildAdjacency(shapes, arrows) {
  const idSet = new Set(shapes.map((s) => s._skelId));
  const adj = new Map();
  const inDeg = new Map();
  for (const s of shapes) {
    adj.set(s._skelId, []);
    inDeg.set(s._skelId, 0);
  }
  for (const a of arrows) {
    if (a._from && a._to && idSet.has(a._from) && idSet.has(a._to)) {
      adj.get(a._from).push(a._to);
      inDeg.set(a._to, (inDeg.get(a._to) || 0) + 1);
    }
  }
  return { adj, inDeg };
}

function assignLevels(shapes, { adj, inDeg }) {
  const levels = new Map();
  // Kahn's algorithm for topological sort / level assignment
  const queue = [];
  for (const s of shapes) {
    if ((inDeg.get(s._skelId) || 0) === 0) {
      queue.push(s._skelId);
      levels.set(s._skelId, 0);
    }
  }

  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    const curLevel = levels.get(cur);
    for (const next of adj.get(cur) || []) {
      const newLevel = curLevel + 1;
      if (!levels.has(next) || levels.get(next) < newLevel) {
        levels.set(next, newLevel);
      }
      inDeg.set(next, inDeg.get(next) - 1);
      if (inDeg.get(next) === 0) {
        queue.push(next);
      }
    }
  }

  // Handle any unvisited nodes (cycles) — assign to level 0
  for (const s of shapes) {
    if (!levels.has(s._skelId)) {
      levels.set(s._skelId, 0);
    }
  }

  return levels;
}

function positionByLevels(shapes, levels, direction) {
  // Group shapes by level
  const byLevel = new Map();
  for (const s of shapes) {
    const lvl = levels.get(s._skelId) || 0;
    if (!byLevel.has(lvl)) byLevel.set(lvl, []);
    byLevel.get(lvl).push(s);
  }

  const sortedLevels = [...byLevel.keys()].sort((a, b) => a - b);

  // Compute max dimension per level for consistent spacing
  const levelMaxPrimary = new Map(); // primary axis (Y for vertical, X for horizontal)
  for (const lvl of sortedLevels) {
    const group = byLevel.get(lvl);
    let maxDim = 0;
    for (const s of group) {
      maxDim = Math.max(maxDim, direction === "vertical" ? (s.height || DEFAULT_HEIGHT) : (s.width || DEFAULT_WIDTH));
    }
    levelMaxPrimary.set(lvl, maxDim);
  }

  for (const lvl of sortedLevels) {
    const group = byLevel.get(lvl);

    // Compute cumulative offset for the primary axis
    let primaryOffset = 0;
    for (const prevLvl of sortedLevels) {
      if (prevLvl >= lvl) break;
      primaryOffset += levelMaxPrimary.get(prevLvl) + (direction === "vertical" ? SPACING_Y : SPACING_X);
    }

    // Compute cross-axis positions for items in this level
    const crossSizes = group.map((s) => direction === "vertical" ? (s.width || DEFAULT_WIDTH) : (s.height || DEFAULT_HEIGHT));
    const totalCross = crossSizes.reduce((sum, sz, i) => sum + sz + (i > 0 ? (direction === "vertical" ? SPACING_X : SPACING_Y) : 0), 0);

    let crossOffset = -totalCross / 2;
    for (let i = 0; i < group.length; i++) {
      const s = group[i];
      if (direction === "vertical") {
        s.x = crossOffset;
        s.y = primaryOffset;
        crossOffset += (s.width || DEFAULT_WIDTH) + SPACING_X;
      } else {
        s.x = primaryOffset;
        s.y = crossOffset;
        crossOffset += (s.height || DEFAULT_HEIGHT) + SPACING_Y;
      }
    }
  }

  // Shift everything so minimum x,y is at (50, 50)
  let minX = Infinity, minY = Infinity;
  for (const s of shapes) {
    minX = Math.min(minX, s.x);
    minY = Math.min(minY, s.y);
  }
  for (const s of shapes) {
    s.x -= minX - 50;
    s.y -= minY - 50;
  }
}

function needsAutoLayout(skeletonElements) {
  const shapes = skeletonElements.filter(
    (el) => el.type !== "arrow" && el.type !== "line" && el.type !== "text"
  );
  if (shapes.length === 0) return false;
  const withCoords = shapes.filter((el) => el.x != null && el.y != null);
  // All have coords → no layout needed
  if (withCoords.length === shapes.length) return false;
  // None have coords or only some do → apply layout
  return true;
}

function applyLayout(shapes, arrows, layoutName) {
  switch (layoutName) {
    case "top-down":
    case "tree":
    case "flowchart":
      layoutTopDown(shapes, arrows);
      break;
    case "left-right":
    case "pipeline":
    case "flow":
      layoutLeftRight(shapes, arrows);
      break;
    case "grid":
    default:
      layoutGrid(shapes);
      break;
  }
}

// ─── Frame Sizing ──────────────────────────────────────────────────────────────

function computeFrameBounds(frameEl, childIds, allElementsMap) {
  const PADDING = 30;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

  for (const cid of childIds) {
    const child = allElementsMap.get(cid);
    if (!child) continue;
    minX = Math.min(minX, child.x);
    minY = Math.min(minY, child.y);
    maxX = Math.max(maxX, child.x + (child.width || 0));
    maxY = Math.max(maxY, child.y + (child.height || 0));
  }

  if (minX === Infinity) return; // no children found

  if (frameEl.x == null) frameEl.x = minX - PADDING;
  if (frameEl.y == null) frameEl.y = minY - PADDING - 20; // extra for name
  if (frameEl.width == null) frameEl.width = (maxX - minX) + 2 * PADDING;
  if (frameEl.height == null) frameEl.height = (maxY - minY) + 2 * PADDING + 20;
}

// ─── Main Conversion ───────────────────────────────────────────────────────────

function validateSkeleton(skeleton) {
  const errors = [];
  if (!skeleton || typeof skeleton !== "object") {
    errors.push("Skeleton must be a JSON object");
    return errors;
  }
  if (!Array.isArray(skeleton.elements)) {
    errors.push("skeleton.elements must be an array");
    return errors;
  }
  const ids = new Set();
  for (let i = 0; i < skeleton.elements.length; i++) {
    const el = skeleton.elements[i];
    if (!el.type) {
      errors.push(`Element at index ${i} is missing required "type" field`);
    }
    if (el.type !== "arrow" && el.type !== "line" && el.type !== "text" && !el.id) {
      errors.push(`Shape element at index ${i} (type: ${el.type}) is missing required "id" field`);
    }
    if (el.id) ids.add(el.id);
  }
  // Check arrow from/to references
  for (let i = 0; i < skeleton.elements.length; i++) {
    const el = skeleton.elements[i];
    if (el.type === "arrow") {
      if (el.from && !ids.has(el.from)) {
        errors.push(`Arrow at index ${i} references unknown "from" id: "${el.from}"`);
      }
      if (el.to && !ids.has(el.to)) {
        errors.push(`Arrow at index ${i} references unknown "to" id: "${el.to}"`);
      }
    }
  }
  return errors;
}

function convert(skeleton, existingFile) {
  // Validate skeleton input
  const validationErrors = validateSkeleton(skeleton);
  if (validationErrors.length > 0) {
    // In modification mode, allow arrow refs to existing element IDs
    const criticalErrors = existingFile
      ? validationErrors.filter((e) => !e.includes("references unknown"))
      : validationErrors;
    if (criticalErrors.length > 0) {
      throw new Error("Skeleton validation failed:\n  - " + criticalErrors.join("\n  - "));
    }
    // Non-critical errors (unknown refs in modify mode) — just warn
    for (const err of validationErrors) {
      if (!criticalErrors.includes(err)) {
        console.warn(`Warning: ${err} (may reference existing elements)`);
      }
    }
  }

  const theme = skeleton.theme || "default";
  const layoutName = skeleton.layout || "grid";

  // Map skeleton IDs to generated IDs
  const idMap = new Map();
  const skelElements = skeleton.elements || [];

  // Pre-assign IDs
  for (const el of skelElements) {
    if (el.id) {
      idMap.set(el.id, randomId());
    }
  }

  // Separate element types
  const shapeSkels = [];
  const arrowSkels = [];
  const lineSkels = [];
  const textSkels = [];
  const frameSkels = [];

  for (const el of skelElements) {
    switch (el.type) {
      case "rectangle":
      case "diamond":
      case "ellipse":
        shapeSkels.push(el);
        break;
      case "arrow":
        arrowSkels.push(el);
        break;
      case "line":
        lineSkels.push(el);
        break;
      case "text":
        textSkels.push(el);
        break;
      case "frame":
        frameSkels.push(el);
        break;
      default:
        // Treat unknown as rectangle
        el.type = "rectangle";
        shapeSkels.push(el);
    }
  }

  // Build shapes first (arrows need shape positions)
  let elementIndex = 0;
  const shapeElements = new Map(); // excalidrawId -> element
  const shapes = []; // for layout

  for (const skel of shapeSkels) {
    const el = buildShapeElement(skel, idMap, theme, elementIndex++);
    el._skelId = skel.id; // temp reference for layout
    shapeElements.set(el.id, el);
    shapes.push(el);
  }

  // Tag arrows with skeleton from/to for layout
  const arrowsForLayout = arrowSkels.map((a) => ({
    _from: a.from,
    _to: a.to,
  }));

  // Auto-layout if needed
  const autoLayout = needsAutoLayout(shapeSkels);
  if (autoLayout) {
    applyLayout(shapes, arrowsForLayout, layoutName);
    // Apply computed positions back
    for (const s of shapes) {
      const el = shapeElements.get(s.id);
      if (el) {
        el.x = s.x;
        el.y = s.y;
      }
    }
  }

  // Build all elements in order
  const allElements = [];

  // Add shapes and their labels
  for (const el of shapeElements.values()) {
    const skel = shapeSkels.find((s) => idMap.get(s.id) === el.id);
    if (skel && skel.label) {
      const textEl = buildTextElement(skel.label, el.id, elementIndex++, {
        fontSize: skel.fontSize || 16,
        strokeColor: el.strokeColor,
      });
      // Position text at center of shape
      textEl.x = el.x + (el.width - textEl.width) / 2;
      textEl.y = el.y + (el.height - textEl.height) / 2;

      if (!el.boundElements) el.boundElements = [];
      el.boundElements.push({ type: "text", id: textEl.id });

      allElements.push(el);
      allElements.push(textEl);
    } else {
      allElements.push(el);
    }
    // Clean temp props
    delete el._skelId;
  }

  // Build existing elements lookup for modification mode
  const existingElementsMap = new Map();
  if (existingFile) {
    for (const el of (existingFile.elements || [])) {
      if (!el.isDeleted) {
        existingElementsMap.set(el.id, el);
      }
    }
  }

  // Build arrows
  for (const skel of arrowSkels) {
    const el = buildArrowElement(skel, idMap, shapeElements, theme, elementIndex++, existingElementsMap);

    // Arrow label
    if (skel.label) {
      const textEl = buildTextElement(skel.label, el.id, elementIndex++, {
        fontSize: skel.fontSize || 14,
        strokeColor: el.strokeColor,
      });
      textEl.x = el.x + (el.width || 0) / 2 - textEl.width / 2;
      textEl.y = el.y + (el.height || 0) / 2 - textEl.height / 2;

      if (!el.boundElements) el.boundElements = [];
      el.boundElements.push({ type: "text", id: textEl.id });

      allElements.push(el);
      allElements.push(textEl);
    } else {
      allElements.push(el);
    }
  }

  // Build lines
  for (const skel of lineSkels) {
    const el = buildLineElement(skel, idMap, shapeElements, theme, elementIndex++);
    allElements.push(el);
  }

  // Build standalone text
  for (const skel of textSkels) {
    const el = buildFreeTextElement(skel, idMap, theme, elementIndex++);
    allElements.push(el);
  }

  // Build frames
  const allElementsMap = new Map();
  for (const el of allElements) {
    allElementsMap.set(el.id, el);
  }

  for (const skel of frameSkels) {
    const el = buildFrameElement(skel, idMap, allElements, theme, elementIndex++);

    // Resolve children
    const childExcalidrawIds = [];
    if (skel.children) {
      for (const childSkelId of skel.children) {
        const childId = idMap.get(childSkelId);
        if (!childId) {
          console.warn(`Warning: Frame "${skel.id}" references unknown child "${childSkelId}"`);
          continue;
        }
        if (childId) {
          childExcalidrawIds.push(childId);
          const childEl = allElementsMap.get(childId);
          if (childEl) {
            childEl.frameId = el.id;
            // Also assign frame to bound text elements
            if (childEl.boundElements) {
              for (const be of childEl.boundElements) {
                const boundEl = allElementsMap.get(be.id);
                if (boundEl) boundEl.frameId = el.id;
              }
            }
          }
        }
      }
    }

    computeFrameBounds(el, childExcalidrawIds, allElementsMap);
    allElements.push(el);
  }

  // Merge with existing file if modifying
  let finalElements = allElements;
  if (existingFile) {
    const existingElements = existingFile.elements || [];
    // Remove deleted elements from existing
    const kept = existingElements.filter((e) => !e.isDeleted);

    // Handle removals from skeleton
    const removeIds = new Set();
    if (skeleton.remove) {
      for (const rid of skeleton.remove) {
        // Find by original excalidraw ID (in modification mode)
        const found = kept.find((e) => e.id === rid);
        if (found) {
          removeIds.add(found.id);
          // Also remove bound text
          if (found.boundElements) {
            for (const be of found.boundElements) {
              if (be.type === "text") removeIds.add(be.id);
            }
          }
        }
      }
    }

    // Clean dangling arrow bindings
    const filtered = kept.filter((e) => !removeIds.has(e.id));
    for (const el of filtered) {
      if (el.startBinding && removeIds.has(el.startBinding.elementId)) {
        el.startBinding = null;
      }
      if (el.endBinding && removeIds.has(el.endBinding.elementId)) {
        el.endBinding = null;
      }
      if (el.boundElements) {
        el.boundElements = el.boundElements.filter((be) => !removeIds.has(be.id));
      }
    }

    // Re-index everything
    elementIndex = filtered.length;
    for (let i = 0; i < allElements.length; i++) {
      allElements[i].index = generateFractionalIndex(elementIndex + i, 0);
    }

    finalElements = [...filtered, ...allElements];
  }

  // Re-assign fractional indices
  for (let i = 0; i < finalElements.length; i++) {
    finalElements[i].index = generateFractionalIndex(i, finalElements.length);
  }

  // Clean up internal temp properties
  for (const el of finalElements) {
    delete el._skelId;
  }

  // Compute viewport to fit all elements
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const el of finalElements) {
    if (el.isDeleted) continue;
    minX = Math.min(minX, el.x || 0);
    minY = Math.min(minY, el.y || 0);
    maxX = Math.max(maxX, (el.x || 0) + (el.width || 0));
    maxY = Math.max(maxY, (el.y || 0) + (el.height || 0));
  }

  const contentWidth = maxX - minX;
  const contentHeight = maxY - minY;
  const viewportPadding = 100;

  // Build output
  const output = {
    type: "excalidraw",
    version: 2,
    source: "https://github.com/fakoli/excalidraw-diagram-plugin",
    elements: finalElements,
    appState: {
      gridSize: 20,
      gridStep: 5,
      gridModeEnabled: false,
      viewBackgroundColor: theme === "blueprint" ? "#1e293b" : "#ffffff",
      scrollX: -(minX - viewportPadding),
      scrollY: -(minY - viewportPadding),
      zoom: { value: 1 },
      currentItemStrokeColor: COLOR_PALETTE.black,
      currentItemBackgroundColor: COLOR_PALETTE.transparent,
      currentItemFillStyle: "solid",
      currentItemStrokeWidth: 2,
      currentItemStrokeStyle: "solid",
      currentItemRoughness: 1,
      currentItemOpacity: 100,
      currentItemFontFamily: FONT_FAMILY_EXCALIFONT,
      currentItemFontSize: 20,
      currentItemTextAlign: "left",
      currentItemStartArrowhead: null,
      currentItemEndArrowhead: "arrow",
      currentItemArrowType: "round",
    },
    files: {},
  };

  return output;
}

// ─── CLI ───────────────────────────────────────────────────────────────────────

function printUsage() {
  console.log(`Usage:
  node convert.js <input.json> [output.excalidraw]
  node convert.js --stdin [output.excalidraw]
  node convert.js --modify <existing.excalidraw> <input.json> [output.excalidraw]

Options:
  --stdin          Read skeleton JSON from stdin
  --modify <file>  Modify an existing .excalidraw file
  --help           Show this help message`);
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf-8");
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("--help") || args.length === 0) {
    printUsage();
    process.exit(0);
  }

  let skeletonJson;
  let existingFile = null;
  let outputPath;

  if (args[0] === "--modify") {
    // Modification mode
    if (args.length < 3) {
      console.error("Error: --modify requires <existing.excalidraw> and <input.json>");
      process.exit(1);
    }
    const existingPath = args[1];
    const inputPath = args[2];
    outputPath = args[3] || existingPath;

    try {
      existingFile = JSON.parse(fs.readFileSync(existingPath, "utf-8"));
    } catch (e) {
      console.error(`Error reading existing file: ${e.message}`);
      process.exit(1);
    }

    try {
      skeletonJson = JSON.parse(fs.readFileSync(inputPath, "utf-8"));
    } catch (e) {
      console.error(`Error reading skeleton file: ${e.message}`);
      process.exit(1);
    }
  } else if (args[0] === "--stdin") {
    outputPath = args[1] || "output.excalidraw";
    try {
      const stdinData = await readStdin();
      skeletonJson = JSON.parse(stdinData);
    } catch (e) {
      console.error(`Error parsing stdin JSON: ${e.message}`);
      process.exit(1);
    }
  } else {
    // Normal mode
    const inputPath = args[0];
    outputPath = args[1] || inputPath.replace(/\.json$/, ".excalidraw");

    try {
      skeletonJson = JSON.parse(fs.readFileSync(inputPath, "utf-8"));
    } catch (e) {
      console.error(`Error reading input file: ${e.message}`);
      process.exit(1);
    }
  }

  // Ensure output has .excalidraw extension
  if (!outputPath.endsWith(".excalidraw")) {
    outputPath += ".excalidraw";
  }

  try {
    const result = convert(skeletonJson, existingFile);
    const outputDir = path.dirname(outputPath);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
    fs.writeFileSync(outputPath, JSON.stringify(result, null, 2), "utf-8");

    const elementCount = result.elements.filter((e) => !e.isDeleted).length;
    console.log(JSON.stringify({
      success: true,
      outputPath: path.resolve(outputPath),
      elementCount,
      message: `Wrote ${elementCount} elements to ${path.resolve(outputPath)}`,
    }));
  } catch (e) {
    console.error(JSON.stringify({
      success: false,
      error: e.message,
    }));
    process.exit(1);
  }
}

main();
