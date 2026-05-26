import type { RationaleEdge, RationaleNode, RationaleNodeType } from "@/lib/types";

const SERVER_DEFAULT_LAYOUT = { x: 160, y: 120 };
const DEFAULT_LAYOUT_TOLERANCE = 8;

const NODE_WIDTH: Record<"issue" | "position" | "argument", number> = {
  issue: 224,
  position: 224,
  argument: 256
};

/** Estimated rendered height (padding + header + title + body). */
const NODE_HEIGHT = 168;
const COLUMN_GAP = 96;
const ROW_GAP = 48;
const ISSUE_BLOCK_GAP = 32;
const ORIGIN = { x: 64, y: 72 };

type FlowColumn = "issue" | "position" | "argument";

function normalizeNodeType(nodeType: RationaleNodeType): FlowColumn {
  if (nodeType === "position") return "position";
  if (nodeType === "argument" || nodeType === "reference") return "argument";
  return "issue";
}

function columnIndex(nodeType: FlowColumn): number {
  if (nodeType === "position") return 1;
  if (nodeType === "argument") return 2;
  return 0;
}

function columnX(nodeType: FlowColumn): number {
  if (nodeType === "issue") return ORIGIN.x;
  if (nodeType === "position") return ORIGIN.x + NODE_WIDTH.issue + COLUMN_GAP;
  return ORIGIN.x + NODE_WIDTH.issue + COLUMN_GAP + NODE_WIDTH.position + COLUMN_GAP;
}

export function nodeLayoutHeight(node: RationaleNode): number {
  const column = normalizeNodeType(node.node_type);
  const contentLen = (node.content ?? "").length;
  const extraLines = Math.min(3, Math.floor(contentLen / 80));
  return NODE_HEIGHT + extraLines * 18;
}

export function isDefaultServerLayout(layout: { x: number; y: number } | undefined): boolean {
  if (!layout) return true;
  return (
    Math.abs(layout.x - SERVER_DEFAULT_LAYOUT.x) <= DEFAULT_LAYOUT_TOLERANCE &&
    Math.abs(layout.y - SERVER_DEFAULT_LAYOUT.y) <= DEFAULT_LAYOUT_TOLERANCE
  );
}

/** True when the node should follow automatic IBIS layout (not user-dragged). */
export function shouldUseAutoLayout(node: RationaleNode): boolean {
  return isDefaultServerLayout(node.layout);
}

export function hasManualLayout(node: RationaleNode): boolean {
  return !shouldUseAutoLayout(node);
}

/** Visual flow: issue → position → argument (left to right). */
export function isValidVisualConnection(
  sourceId: string,
  targetId: string,
  nodeById: Map<string, RationaleNode>
): boolean {
  const sourceNode = nodeById.get(sourceId);
  const targetNode = nodeById.get(targetId);
  if (!sourceNode || !targetNode || sourceId === targetId) return false;

  const sourceType = normalizeNodeType(sourceNode.node_type);
  const targetType = normalizeNodeType(targetNode.node_type);
  return (
    (sourceType === "issue" && targetType === "position") ||
    (sourceType === "position" && targetType === "argument")
  );
}

/** Map on-canvas direction to canonical IBIS storage (child → parent). */
export function visualConnectionToStored(
  sourceId: string,
  targetId: string,
  nodeById: Map<string, RationaleNode>
): { from_node_id: string; to_node_id: string; relation_type: string } | null {
  if (!isValidVisualConnection(sourceId, targetId, nodeById)) return null;

  const sourceType = normalizeNodeType(nodeById.get(sourceId)!.node_type);
  const targetType = normalizeNodeType(nodeById.get(targetId)!.node_type);

  if (sourceType === "issue" && targetType === "position") {
    return { from_node_id: targetId, to_node_id: sourceId, relation_type: "responds_to" };
  }
  if (sourceType === "position" && targetType === "argument") {
    return { from_node_id: targetId, to_node_id: sourceId, relation_type: "supports" };
  }
  return null;
}

/** Resolve stored edge to visual endpoints; returns null for invalid pairs. */
export function resolveFlowEndpoints(
  edge: RationaleEdge,
  nodeById: Map<string, RationaleNode>
): { source: string; target: string } | null {
  const from = edge.from_node_id;
  const to = edge.to_node_id;
  const fromNode = nodeById.get(from);
  const toNode = nodeById.get(to);
  if (!fromNode || !toNode) return null;

  const fromType = normalizeNodeType(fromNode.node_type);
  const toType = normalizeNodeType(toNode.node_type);

  if (fromType === "issue" && toType === "position") {
    return { source: from, target: to };
  }
  if (fromType === "position" && toType === "issue") {
    return { source: to, target: from };
  }
  if (fromType === "position" && toType === "argument") {
    return { source: from, target: to };
  }
  if (fromType === "argument" && toType === "position") {
    return { source: to, target: from };
  }
  return null;
}

function sortIds(ids: string[], anchorY: Map<string, number>): string[] {
  return [...ids].sort((a, b) => {
    const ay = anchorY.get(a) ?? 0;
    const by = anchorY.get(b) ?? 0;
    if (ay !== by) return ay - by;
    return a.localeCompare(b);
  });
}

function buildVisualChildren(
  nodes: RationaleNode[],
  edges: RationaleEdge[]
): { nodeById: Map<string, RationaleNode>; visualChildren: Map<string, string[]> } {
  const nodeById = new Map(nodes.map((node) => [node.node_id, node]));
  const visualChildren = new Map<string, string[]>();

  for (const edge of edges) {
    const endpoints = resolveFlowEndpoints(edge, nodeById);
    if (!endpoints) continue;
    const { source, target } = endpoints;
    if (!nodeById.has(source) || !nodeById.has(target)) continue;
    const list = visualChildren.get(source) ?? [];
    if (!list.includes(target)) list.push(target);
    visualChildren.set(source, list);
  }

  return { nodeById, visualChildren };
}

/** Remove vertical overlaps within each IBIS column while preserving order. */
function resolveColumnOverlaps(
  positions: Map<string, { x: number; y: number }>,
  nodeById: Map<string, RationaleNode>
): void {
  for (const column of ["issue", "position", "argument"] as const) {
    const entries: Array<{ id: string; y: number; height: number }> = [];
    for (const [id, pos] of positions) {
      const node = nodeById.get(id);
      if (!node || normalizeNodeType(node.node_type) !== column) continue;
      entries.push({ id, y: pos.y, height: nodeLayoutHeight(node) });
    }
    entries.sort((a, b) => a.y - b.y || a.id.localeCompare(b.id));

    let minY = ORIGIN.y;
    for (const entry of entries) {
      const pos = positions.get(entry.id);
      if (!pos) continue;
      if (pos.y < minY) {
        pos.y = minY;
      }
      minY = pos.y + entry.height + ROW_GAP;
    }
  }
}

/** Vertically center each issue on its position/argument subtree span. */
function alignIssuesToSubtrees(
  positions: Map<string, { x: number; y: number }>,
  issueIds: string[],
  visualChildren: Map<string, string[]>,
  nodeById: Map<string, RationaleNode>
): void {
  const collectSpan = (rootId: string): { min: number; max: number } | null => {
    const stack = [...(visualChildren.get(rootId) ?? [])];
    let min = Infinity;
    let max = -Infinity;

    while (stack.length) {
      const id = stack.pop()!;
      const pos = positions.get(id);
      const node = nodeById.get(id);
      if (pos && node) {
        const h = nodeLayoutHeight(node);
        min = Math.min(min, pos.y);
        max = Math.max(max, pos.y + h);
      }
      for (const childId of visualChildren.get(id) ?? []) {
        stack.push(childId);
      }
    }

    if (!Number.isFinite(min)) return null;
    return { min, max };
  };

  for (const issueId of issueIds) {
    const issuePos = positions.get(issueId);
    const issueNode = nodeById.get(issueId);
    if (!issuePos || !issueNode) continue;

    const span = collectSpan(issueId);
    if (!span) continue;

    const issueHeight = nodeLayoutHeight(issueNode);
    const centered = span.min + (span.max - span.min - issueHeight) / 2;
    issuePos.y = Math.max(ORIGIN.y, centered);
  }
}

/**
 * Place nodes in issue | position | argument columns with vertical grouping by graph links.
 */
export function computeIbisLayout(
  nodes: RationaleNode[],
  edges: RationaleEdge[]
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  if (nodes.length === 0) return positions;

  const { nodeById, visualChildren } = buildVisualChildren(nodes, edges);

  const issues = nodes
    .filter((node) => normalizeNodeType(node.node_type) === "issue")
    .map((node) => node.node_id);

  const anchorY = new Map<string, number>();
  let cursorY = ORIGIN.y;

  const placeSubtree = (rootId: string, startY: number): number => {
    const root = nodeById.get(rootId);
    if (!root) return startY;

    const rootType = normalizeNodeType(root.node_type);
    const rootHeight = nodeLayoutHeight(root);
    positions.set(rootId, { x: columnX(rootType), y: startY });
    anchorY.set(rootId, startY);

    const childIds = sortIds(
      (visualChildren.get(rootId) ?? []).filter((id) => nodeById.has(id)),
      anchorY
    );

    let nextY = startY;
    let maxBottom = startY + rootHeight;

    for (const childId of childIds) {
      const child = nodeById.get(childId);
      if (!child) continue;
      const childType = normalizeNodeType(child.node_type);
      if (columnIndex(childType) <= columnIndex(rootType)) continue;

      const blockBottom = placeSubtree(childId, nextY);
      maxBottom = Math.max(maxBottom, blockBottom);
      nextY = blockBottom + ROW_GAP;
    }

    return Math.max(maxBottom, startY + rootHeight);
  };

  for (const issueId of sortIds(issues, anchorY)) {
    const bottom = placeSubtree(issueId, cursorY);
    cursorY = bottom + ISSUE_BLOCK_GAP;
  }

  const unplaced = nodes.filter((node) => !positions.has(node.node_id));
  const byColumn: Record<FlowColumn, string[]> = { issue: [], position: [], argument: [] };
  for (const node of unplaced) {
    byColumn[normalizeNodeType(node.node_type)].push(node.node_id);
  }

  for (const column of ["issue", "position", "argument"] as const) {
    const ids = sortIds(byColumn[column], anchorY);
    let y = cursorY;
    for (const id of ids) {
      if (positions.has(id)) continue;
      const node = nodeById.get(id);
      const height = node ? nodeLayoutHeight(node) : NODE_HEIGHT;
      positions.set(id, { x: columnX(column), y });
      anchorY.set(id, y);
      y += height + ROW_GAP;
    }
    if (ids.length > 0) {
      cursorY = Math.max(cursorY, y);
    }
  }

  alignIssuesToSubtrees(positions, issues, visualChildren, nodeById);
  resolveColumnOverlaps(positions, nodeById);

  return positions;
}

export function layoutForNode(
  node: RationaleNode,
  index: number,
  autoLayouts: Map<string, { x: number; y: number }>
): { x: number; y: number } {
  if (!shouldUseAutoLayout(node) && node.layout) {
    return { x: node.layout.x, y: node.layout.y };
  }
  const auto = autoLayouts.get(node.node_id);
  if (auto) return auto;
  const column = normalizeNodeType(node.node_type);
  return {
    x: columnX(column),
    y: ORIGIN.y + index * (NODE_HEIGHT + ROW_GAP)
  };
}

export { NODE_WIDTH, NODE_HEIGHT, columnX, normalizeNodeType, SERVER_DEFAULT_LAYOUT };
