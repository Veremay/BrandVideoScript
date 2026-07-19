import type { RationaleNode, RationaleNodeType } from "@/lib/types";

const NODE_PREFIX: Record<RationaleNodeType, string> = {
  issue: "I",
  position: "P",
  argument: "A",
  reference: "R",
};

/** Build compact, type-local labels in the same order as the project's node list. */
export function buildIbisNodeLabels(nodes: RationaleNode[]): Map<string, string> {
  const counts: Record<RationaleNodeType, number> = {
    issue: 0,
    position: 0,
    argument: 0,
    reference: 0,
  };
  const labels = new Map<string, string>();

  for (const node of nodes) {
    if (!node.node_id || node.lifecycle === "superseded") continue;
    counts[node.node_type] += 1;
    labels.set(node.node_id, `${NODE_PREFIX[node.node_type]}${counts[node.node_type]}`);
  }

  return labels;
}
