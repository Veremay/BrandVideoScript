import type { RationaleEdge, RationaleNode, RationaleNodeType } from "@/lib/types";

const SERVER_DEFAULT_LAYOUT = { x: 160, y: 120 };

const NODE_WIDTH: Record<"issue" | "position" | "argument", number> = {
  issue: 224,
  position: 224,
  argument: 256
};

const NODE_HEIGHT = 132;
const COLUMN_GAP = 96;
const ROW_GAP = 40;
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

export function hasManualLayout(node: RationaleNode): boolean {
  const layout = node.layout;
  if (!layout) return false;
  return layout.x !== SERVER_DEFAULT_LAYOUT.x || layout.y !== SERVER_DEFAULT_LAYOUT.y;
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

function sortByAnchorY(ids: string[], anchorY: Map<string, number>): string[] {
  return [...ids].sort((a, b) => {
    const ay = anchorY.get(a) ?? 0;
    const by = anchorY.get(b) ?? 0;
    if (ay !== by) return ay - by;
    return a.localeCompare(b);
  });
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

  const nodeById = new Map(nodes.map((node) => [node.node_id, node]));
  const visualChildren = new Map<string, string[]>();

  for (const edge of edges) {
    const endpoints = resolveFlowEndpoints(edge, nodeById);
    if (!endpoints) continue;
    const { source, target } = endpoints;
    if (!nodeById.has(source) || !nodeById.has(target)) continue;
    const list = visualChildren.get(source) ?? [];
    list.push(target);
    visualChildren.set(source, list);
  }

  const issues = nodes
    .filter((node) => normalizeNodeType(node.node_type) === "issue")
    .map((node) => node.node_id);
  const orphanIds = nodes
    .filter((node) => !issues.includes(node.node_id))
    .map((node) => node.node_id);

  const anchorY = new Map<string, number>();
  let cursorY = ORIGIN.y;

  const placeSubtree = (rootId: string, startY: number): number => {
    const root = nodeById.get(rootId);
    if (!root) return startY;

    const rootType = normalizeNodeType(root.node_type);
    positions.set(rootId, { x: columnX(rootType), y: startY });
    anchorY.set(rootId, startY);

    const childIds = (visualChildren.get(rootId) ?? []).filter((id) => nodeById.has(id));
    let nextY = startY;

    for (const childId of childIds) {
      const child = nodeById.get(childId);
      if (!child) continue;
      const childType = normalizeNodeType(child.node_type);
      if (columnIndex(childType) <= columnIndex(rootType)) continue;

      const blockBottom = placeSubtree(childId, nextY);
      nextY = blockBottom + ROW_GAP;
    }

    return Math.max(startY + NODE_HEIGHT, nextY - ROW_GAP);
  };

  for (const issueId of issues) {
    const bottom = placeSubtree(issueId, cursorY);
    cursorY = bottom + ROW_GAP + 24;
  }

  const unplaced = nodes.filter((node) => !positions.has(node.node_id));
  const byColumn: Record<FlowColumn, string[]> = { issue: [], position: [], argument: [] };
  for (const node of unplaced) {
    byColumn[normalizeNodeType(node.node_type)].push(node.node_id);
  }

  for (const column of ["issue", "position", "argument"] as const) {
    const ids = sortByAnchorY(byColumn[column], anchorY);
    let y = cursorY;
    for (const id of ids) {
      if (positions.has(id)) continue;
      positions.set(id, { x: columnX(column), y });
      anchorY.set(id, y);
      y += NODE_HEIGHT + ROW_GAP;
    }
    if (ids.length > 0) {
      cursorY = Math.max(cursorY, y);
    }
  }

  for (const orphanId of orphanIds) {
    if (positions.has(orphanId)) continue;
    const node = nodeById.get(orphanId);
    if (!node) continue;
    const column = normalizeNodeType(node.node_type);
    positions.set(orphanId, { x: columnX(column), y: cursorY });
    cursorY += NODE_HEIGHT + ROW_GAP;
  }

  return positions;
}

export function layoutForNode(
  node: RationaleNode,
  index: number,
  autoLayouts: Map<string, { x: number; y: number }>
): { x: number; y: number } {
  if (hasManualLayout(node) && node.layout) {
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

export { NODE_WIDTH, NODE_HEIGHT, columnX, normalizeNodeType };
