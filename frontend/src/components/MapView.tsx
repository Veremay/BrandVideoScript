"use client";

import {
  Background,
  BackgroundVariant,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  reconnectEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  useUpdateNodeInternals,
  SelectionMode,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import {
  computeIbisLayout,
  isValidVisualConnection,
  layoutForNode,
  resolveFlowEndpoints,
  visualConnectionToStored
} from "@/lib/ibisLayout";
import type { RationaleEdge, RationaleNode, RationaleSourceType } from "@/lib/types";
import {
  createGraphEdge,
  createGraphNode,
  batchUpdateGraphLayouts,
  deleteGraphEdge,
  deleteGraphNode,
  populateIssuePositions,
  syncMapFromScript,
  fetchProject,
  generateModificationSchemes,
  toggleGraphConsiderationQueue,
  updateGraphNode
} from "@/lib/api";
import { isGraphStaleForUpdateMap } from "@/lib/stale";
import { useAppStore } from "@/store/appStore";

type MapNodeType = "issue" | "position" | "argument";

type IbisNodeData = {
  nodeType: MapNodeType;
  title: string;
  content: string;
  width: number;
  sourceType?: RationaleSourceType;
  status?: string;
  inConsiderationQueue?: boolean;
  proposalCount?: number;
  reference?: string;
  lifecycle?: "active" | "resolved" | "superseded";
  changeMark?: "none" | "modified" | "new";
  suggestion?: string | null;
  createdBy?: string;
  /** Conflict group labels assigned by Coordinator (e.g. ["A", "B"]). Position nodes only. */
  conflictTags?: string[];
} & Record<string, unknown>;

type MapNodeSeed = IbisNodeData & {
  id: string;
  x: number;
  y: number;
};

type MapEdgeSeed = {
  from: string;
  to: string;
};

type EdgeMenuState = {
  x: number;
  y: number;
  edgeId: string;
};


const LEGEND_ITEMS: Array<{ type: MapNodeType; label: string }> = [
  { type: "issue", label: "Issue" },
  { type: "position", label: "Position" },
  { type: "argument", label: "Argument" }
];

const SOURCE_LEGEND: Array<{ source: RationaleSourceType; label: string }> = [
  { source: "brand_brief", label: "Brand · Brief" },
  { source: "brand_inferred", label: "Brand · Inferred" },
  { source: "audience_persona", label: "Audience · Persona" },
  { source: "audience_simulation", label: "Audience · Simulation" },
  { source: "expert_strategy", label: "Expert" }
];

function sourceLabel(source?: RationaleSourceType): string {
  if (!source) return "";
  return SOURCE_LEGEND.find((item) => item.source === source)?.label ?? source;
}

const EDGE_STYLE = { stroke: "#7ed4fd", strokeWidth: 2 };
const EDGE_FOCUS_STYLE = { stroke: "#006591", strokeWidth: 3 };
const FLOW_EDGE_TYPE = "default";

function buildUndirectedAdjacency(edgeList: Edge[]): Map<string, Set<string>> {
  const adjacency = new Map<string, Set<string>>();
  const link = (a: string, b: string) => {
    if (!adjacency.has(a)) adjacency.set(a, new Set());
    adjacency.get(a)!.add(b);
  };
  for (const edge of edgeList) {
    link(edge.source, edge.target);
    link(edge.target, edge.source);
  }
  return adjacency;
}

function reachableNodeIds(startId: string, adjacency: Map<string, Set<string>>): Set<string> {
  const visited = new Set<string>([startId]);
  const queue = [startId];
  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const neighbor of adjacency.get(current) ?? []) {
      if (visited.has(neighbor)) continue;
      visited.add(neighbor);
      queue.push(neighbor);
    }
  }
  return visited;
}

function applyGraphFocus(
  nodeList: Node<IbisNodeData>[],
  edgeList: Edge[],
  focusId: string | null,
  reachable: Set<string> | null
): { nodes: Node<IbisNodeData>[]; edges: Edge[] } {
  if (!focusId || !reachable) {
    return { nodes: nodeList, edges: edgeList };
  }

  const nodes = nodeList.map((node) => {
    const inComponent = reachable.has(node.id);
    const className = inComponent
      ? node.id === focusId
        ? "map-graph-focused map-graph-focus-root"
        : "map-graph-focused"
      : "map-graph-dimmed";
    return { ...node, className };
  });

  const edges = edgeList.map((edge) => {
    const inComponent = reachable.has(edge.source) && reachable.has(edge.target);
    return {
      ...edge,
      className: inComponent ? "map-graph-edge-focused" : "map-graph-edge-dimmed",
      style: inComponent ? EDGE_FOCUS_STYLE : { ...EDGE_STYLE, opacity: 0.22 }
    };
  });

  return { nodes, edges };
}

function rationaleToFlowNode(
  node: RationaleNode,
  index: number,
  autoLayouts: Map<string, { x: number; y: number }>
): Node<IbisNodeData> | null {
  if (!node.node_id || !node.title) return null;
  const rawType = node.node_type === "reference" ? "argument" : node.node_type;
  const nodeType = (["issue", "position", "argument"].includes(rawType) ? rawType : "issue") as MapNodeType;
  const width = nodeType === "argument" ? 256 : 224;
  const position = layoutForNode(node, index, autoLayouts);
  const resolved = node.lifecycle === "resolved";
  return {
    id: node.node_id,
    type: "ibis",
    position,
    width,
    style: { width, opacity: resolved ? 0.5 : 1 },
    data: {
      nodeType,
      title: node.title,
      content: node.content,
      width,
      sourceType: node.source_type,
      status: node.status,
      inConsiderationQueue: node.in_consideration_queue ?? node.in_negotiation_queue,
      lifecycle: node.lifecycle ?? "active",
      changeMark: node.change_mark ?? "none",
      suggestion: node.suggestion ?? null,
      createdBy: node.created_by,
      conflictTags: node.conflict_tags && node.conflict_tags.length > 0 ? node.conflict_tags : undefined,
    }
  };
}

function rationaleToFlowEdge(edge: RationaleEdge, nodeById: Map<string, RationaleNode>): Edge | null {
  const touchesResolved =
    nodeById.get(edge.from_node_id)?.lifecycle === "resolved" ||
    nodeById.get(edge.to_node_id)?.lifecycle === "resolved";
  const dim = (style: Record<string, unknown>) => (touchesResolved ? { ...style, opacity: 0.4 } : style);
  const endpoints = resolveFlowEndpoints(edge, nodeById);
  if (!endpoints) return null;
  return {
    id: edge.edge_id,
    source: endpoints.source,
    target: endpoints.target,
    type: FLOW_EDGE_TYPE,
    style: dim(EDGE_STYLE),
    reconnectable: true
  };
}

const NODE_DEFAULTS: Record<MapNodeType, Pick<IbisNodeData, "title" | "content" | "width">> = {
  issue: {
    title: "New Issue",
    content: "Describe the problem to be resolved.",
    width: 224
  },
  position: {
    title: "New Position",
    content: "Describe the position or viewpoint on this issue.",
    width: 224
  },
  argument: {
    title: "New Argument",
    content: "Provide supporting or opposing rationale.",
    width: 256
  }
};

const MAX_CONSIDERATION_QUEUE_SIZE = 3;

const MapGraphActionsContext = createContext<{
  editingNodeId: string | null;
  onStartEdit: (nodeId: string) => void;
  onSaveEdit: (nodeId: string, title: string, content: string) => void;
  onCancelEdit: () => void;
  onDelete: (nodeId: string) => void;
  onToggleConsideration: (nodeId: string, inQueue: boolean) => void;
  onPopulateIssue: (nodeId: string) => void;
  populatingIssueId: string | null;
  considerationQueueFull: boolean;
} | null>(null);

const nodeTypes: NodeTypes = {
  ibis: IbisNode
};

function toFlowNode(seed: MapNodeSeed): Node<IbisNodeData> {
  const { id, x, y, ...data } = seed;
  return {
    id,
    type: "ibis",
    position: { x, y },
    data
  };
}

function toFlowEdge(seed: MapEdgeSeed): Edge {
  return {
    id: `${seed.from}-${seed.to}`,
    source: seed.from,
    target: seed.to,
    type: FLOW_EDGE_TYPE,
    style: EDGE_STYLE,
    reconnectable: true
  };
}

function createFlowEdge(connection: Connection): Edge {
  return {
    id: `${connection.source}-${connection.target}-${Date.now()}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle,
    targetHandle: connection.targetHandle,
    type: FLOW_EDGE_TYPE,
    style: EDGE_STYLE,
    reconnectable: true
  };
}

export function MapView() {
  const project = useAppStore((state) => state.project);
  const graphKey = project?._id ?? "none";

  return (
    <ReactFlowProvider>
      <MapViewContent key={graphKey} />
    </ReactFlowProvider>
  );
}

function MapViewContent() {
  const project = useAppStore((state) => state.project);
  const setProject = useAppStore((state) => state.setProject);
  const mapFocusNodeId = useAppStore((state) => state.mapFocusNodeId);
  const setMapFocusNodeId = useAppStore((state) => state.setMapFocusNodeId);
  // Superseded nodes survive only in snapshots; never render them on the canvas.
  const rationaleNodes = useMemo(
    () => (project?.rationale_nodes ?? []).filter((node) => node.lifecycle !== "superseded"),
    [project?.rationale_nodes]
  );
  const rationaleEdges = useMemo(
    () => project?.rationale_edges ?? [],
    [project?.rationale_edges]
  );
  const nodeById = useMemo(
    () => new Map(rationaleNodes.map((node) => [node.node_id, node])),
    [rationaleNodes]
  );
  const autoLayouts = useMemo(
    () => computeIbisLayout(rationaleNodes, rationaleEdges),
    [rationaleNodes, rationaleEdges]
  );
  const flowNodes = useMemo(() => {
    return rationaleNodes
      .map((node, index) => rationaleToFlowNode(node, index, autoLayouts))
      .filter((node): node is Node<IbisNodeData> => node !== null);
  }, [autoLayouts, rationaleNodes]);
  const flowNodeIds = useMemo(() => new Set(flowNodes.map((node) => node.id)), [flowNodes]);
  const flowEdges = useMemo(() => {
    return rationaleEdges
      .map((edge) => rationaleToFlowEdge(edge, nodeById))
      .filter((edge): edge is Edge => edge !== null && flowNodeIds.has(edge.source) && flowNodeIds.has(edge.target));
  }, [flowNodeIds, nodeById, rationaleEdges]);

  const isValidConnection = useCallback(
    (connection: Connection | Edge) => {
      const source = connection.source;
      const target = connection.target;
      if (!source || !target || source === target) return false;
      return isValidVisualConnection(source, target, nodeById);
    },
    [nodeById]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);
  const [addNodeMenuOpen, setAddNodeMenuOpen] = useState(false);
  const [edgeMenu, setEdgeMenu] = useState<EdgeMenuState | null>(null);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);
  const [syncingMap, setSyncingMap] = useState(false);
  const [populatingIssueId, setPopulatingIssueId] = useState<string | null>(null);
  const [applyingLayout, setApplyingLayout] = useState(false);
  const { zoomIn, zoomOut, fitView, getViewport, setViewport, setCenter } = useReactFlow();
  const workspaceRef = useRef<HTMLElement>(null);
  const controlsRef = useRef<HTMLDivElement>(null);
  const edgeMenuRef = useRef<HTMLDivElement>(null);
  const hasFittedRef = useRef(false);
  const prevNodeCountRef = useRef(0);

  const closeMenus = useCallback(() => {
    setAddNodeMenuOpen(false);
    setEdgeMenu(null);
  }, []);

  const clearGraphFocus = useCallback(() => {
    setFocusNodeId(null);
  }, []);

  const handlePaneClick = useCallback(() => {
    closeMenus();
    clearGraphFocus();
  }, [clearGraphFocus, closeMenus]);

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node<IbisNodeData>) => {
    setFocusNodeId((current) => (current === node.id ? null : node.id));
  }, []);

  const graphAdjacency = useMemo(() => buildUndirectedAdjacency(edges), [edges]);

  const focusReachable = useMemo(() => {
    if (!focusNodeId) return null;
    return reachableNodeIds(focusNodeId, graphAdjacency);
  }, [focusNodeId, graphAdjacency]);

  const { nodes: displayNodes, edges: displayEdges } = useMemo(
    () => applyGraphFocus(nodes, edges, focusNodeId, focusReachable),
    [edges, focusNodeId, focusReachable, nodes]
  );

  const runFitView = useCallback(() => {
    const workspace = workspaceRef.current;
    if (!workspace || workspace.clientWidth < 64 || workspace.clientHeight < 64) return;
    fitView({ padding: 0.25, duration: 150 });
    hasFittedRef.current = true;
  }, [fitView]);

  useEffect(() => {
    const viewport = hasFittedRef.current ? getViewport() : null;
    setNodes(flowNodes);
    setEdges(flowEdges);
    if (viewport) {
      requestAnimationFrame(() => setViewport(viewport));
    }
  }, [flowNodes, flowEdges, getViewport, setEdges, setNodes, setViewport]);

  useEffect(() => {
    if (focusNodeId && !flowNodeIds.has(focusNodeId)) {
      setFocusNodeId(null);
    }
  }, [focusNodeId, flowNodeIds]);

  useEffect(() => {
    if (!mapFocusNodeId || !flowNodeIds.has(mapFocusNodeId)) return;
    setFocusNodeId(mapFocusNodeId);
    setMapFocusNodeId(null);
    const targetNode = nodes.find((node) => node.id === mapFocusNodeId);
    if (!targetNode) return;
    requestAnimationFrame(() => {
      setCenter(
        targetNode.position.x + (targetNode.width ?? targetNode.data.width) / 2,
        targetNode.position.y + 120,
        { duration: 220, zoom: Math.max(getViewport().zoom, 0.85) }
      );
    });
  }, [flowNodeIds, getViewport, mapFocusNodeId, nodes, setCenter, setMapFocusNodeId]);

  useEffect(() => {
    const count = rationaleNodes.length;
    const prev = prevNodeCountRef.current;
    if (prev === 0 && count > 0 && !hasFittedRef.current) {
      requestAnimationFrame(() => runFitView());
    }
    prevNodeCountRef.current = count;
  }, [rationaleNodes.length, runFitView]);

  const handleFlowInit = useCallback(() => {
    if (!hasFittedRef.current && rationaleNodes.length > 0) {
      requestAnimationFrame(() => runFitView());
    }
  }, [rationaleNodes.length, runFitView]);

  useEffect(() => {
    const workspace = workspaceRef.current;
    if (!workspace) return;

    const observer = new ResizeObserver(() => {
      if (hasFittedRef.current || rationaleNodes.length === 0) return;
      requestAnimationFrame(() => runFitView());
    });
    observer.observe(workspace);
    if (!hasFittedRef.current && rationaleNodes.length > 0) {
      requestAnimationFrame(() => runFitView());
    }

    return () => observer.disconnect();
  }, [rationaleNodes.length, runFitView]);

  useEffect(() => {
    if (!addNodeMenuOpen && !edgeMenu) return;

    function handlePointerDown(event: MouseEvent) {
      const target = event.target as HTMLElement;
      if (controlsRef.current?.contains(target) || edgeMenuRef.current?.contains(target)) return;
      closeMenus();
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeMenus();
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [addNodeMenuOpen, closeMenus, edgeMenu]);

  const handleStartEdit = useCallback((nodeId: string) => {
    setEditingNodeId(nodeId);
  }, []);

  const handleSaveEdit = useCallback(
    async (nodeId: string, title: string, content: string) => {
      const nextTitle = title.trim();
      const nextContent = content.trim();
      if (!nextTitle || !project) return;
      setNodes((current) =>
        current.map((item) =>
          item.id === nodeId
            ? { ...item, data: { ...item.data, title: nextTitle, content: nextContent } }
            : item
        )
      );
      setEditingNodeId((current) => (current === nodeId ? null : current));
      try {
        const updated = await updateGraphNode(project._id, project.user_id, nodeId, {
          title: nextTitle,
          content: nextContent
        });
        setProject(updated);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Failed to save node");
      }
    },
    [project, setNodes, setProject]
  );

  const handleCancelEdit = useCallback(() => {
    setEditingNodeId(null);
  }, []);

  const handleDeleteNodes = useCallback(
    async (nodeIds: string[], options?: { skipConfirm?: boolean }) => {
      const uniqueIds = [...new Set(nodeIds)].filter(Boolean);
      if (!uniqueIds.length || !project) return;

      const labels = uniqueIds
        .map((id) => nodes.find((item) => item.id === id)?.data.title)
        .filter((title): title is string => typeof title === "string" && !!title);

      if (!options?.skipConfirm) {
        const preview = labels.slice(0, 3).join(", ");
        const more = uniqueIds.length > 3 ? ` and ${uniqueIds.length} total` : "";
        const message =
          uniqueIds.length === 1
            ? `Delete "${labels[0] ?? "this node"}"?`
            : `Delete ${uniqueIds.length} selected nodes?${preview ? `\n${preview}${more}` : ""}`;
        if (!window.confirm(message)) return;
      }

      setEditingNodeId((current) => (current && uniqueIds.includes(current) ? null : current));

      const deletePriority = (id: string) => {
        const nodeType = nodes.find((item) => item.id === id)?.data.nodeType;
        if (nodeType === "issue") return 0;
        if (nodeType === "position") return 1;
        if (nodeType === "argument") return 2;
        return 3;
      };
      const sortedIds = [...uniqueIds].sort((a, b) => deletePriority(a) - deletePriority(b));

      try {
        let updated = project;
        for (const nodeId of sortedIds) {
          try {
            updated = (await deleteGraphNode(project._id, project.user_id, nodeId)) ?? updated;
          } catch (error) {
            if (error instanceof Error && error.message.toLowerCase().includes("not found")) {
              continue;
            }
            throw error;
          }
        }
        setProject(updated);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Failed to delete nodes");
        setProject(project);
      }
    },
    [nodes, project, setProject]
  );

  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      void handleDeleteNodes([nodeId]);
    },
    [handleDeleteNodes]
  );

  const handleBeforeDelete = useCallback(async ({ nodes: nodesToDelete }: { nodes: Node[]; edges: Edge[] }) => {
    if (!nodesToDelete.length) return true;
    const labels = nodesToDelete
      .map((node) => (typeof node.data?.title === "string" ? node.data.title : ""))
      .filter(Boolean);
    const preview = labels.slice(0, 3).join(", ");
    const more = nodesToDelete.length > 3 ? ` and ${nodesToDelete.length} total` : "";
    return window.confirm(`Delete ${nodesToDelete.length} selected nodes?${preview ? `\n${preview}${more}` : ""}`);
  }, []);

  const handleNodesDelete = useCallback(
    (deleted: Node<IbisNodeData>[]) => {
      void handleDeleteNodes(
        deleted.map((node) => node.id),
        { skipConfirm: true }
      );
    },
    [handleDeleteNodes]
  );

  const setWorkspaceView = useAppStore((state) => state.setWorkspaceView);
  const setEditorSchemeFocusId = useAppStore((state) => state.setEditorSchemeFocusId);
  const [generatingSchemes, setGeneratingSchemes] = useState(false);

  const considerationPositions = useMemo(() => {
    const queue = new Set(project?.consideration_queue ?? []);
    return (project?.rationale_nodes ?? []).filter(
      (node) =>
        node.node_type === "position" &&
        (node.in_consideration_queue || node.in_negotiation_queue || queue.has(node.node_id))
    );
  }, [project?.consideration_queue, project?.rationale_nodes]);

  // Queue entries whose Position was superseded/removed by a reconcile: show a stale tag.
  const staleConsiderationIds = useMemo(() => {
    const known = new Set((project?.rationale_nodes ?? []).map((node) => node.node_id));
    return (project?.consideration_queue ?? []).filter((id) => !known.has(id));
  }, [project?.consideration_queue, project?.rationale_nodes]);

  const handleToggleConsideration = useCallback(
    async (nodeId: string, inQueue: boolean) => {
      if (!project) return;
      const alreadyInQueue = considerationPositions.some((node) => node.node_id === nodeId);
      if (
        inQueue &&
        !alreadyInQueue &&
        considerationPositions.length >= MAX_CONSIDERATION_QUEUE_SIZE
      ) {
        window.alert(
          `TO BE CONSIDERED can hold at most ${MAX_CONSIDERATION_QUEUE_SIZE} positions. Remove one before adding another.`
        );
        return;
      }
      try {
        const updated = await toggleGraphConsiderationQueue(project._id, project.user_id, nodeId, inQueue);
        setProject(updated);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Failed to update consideration queue");
      }
    },
    [considerationPositions, project, setProject]
  );

  const handlePopulateIssue = useCallback(
    async (nodeId: string) => {
      if (!project?._id || !project.user_id || populatingIssueId) return;
      setPopulatingIssueId(nodeId);
      try {
        const updated = await populateIssuePositions(project._id, project.user_id, nodeId);
        setProject(updated);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Failed to generate positions");
      } finally {
        setPopulatingIssueId(null);
      }
    },
    [populatingIssueId, project, setProject]
  );

  const handleGenerateModificationPlan = useCallback(async () => {
    if (!project?._id || !project.user_id || generatingSchemes) return;
    const positionIds = considerationPositions.map((node) => node.node_id);
    if (!positionIds.length) {
      window.alert("Add at least one Position to TO BE CONSIDERED from the node menu.");
      return;
    }
    setGeneratingSchemes(true);
    try {
      const result = await generateModificationSchemes(project._id, project.user_id, {
        target_position_ids: positionIds,
        message: "Generate modification schemes for adopted positions in TO BE CONSIDERED."
      });
      setProject(result.project);
      const latest = result.schemes[result.schemes.length - 1];
      if (latest?.scheme_id) {
        setEditorSchemeFocusId(latest.scheme_id);
      }
      setWorkspaceView("editor");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to generate modification plan";
      window.alert(`${message} 请稍后重试。`);
      try {
        const refreshed = await fetchProject(project._id, project.user_id);
        setProject(refreshed);
      } catch {
        // ignore refresh failure
      }
    } finally {
      setGeneratingSchemes(false);
    }
  }, [
    considerationPositions,
    generatingSchemes,
    project,
    setEditorSchemeFocusId,
    setProject,
    setWorkspaceView
  ]);

  const handleAddNode = useCallback(
    async (nodeType: MapNodeType) => {
      if (!project) return;
      const defaults = NODE_DEFAULTS[nodeType];
      setAddNodeMenuOpen(false);
      try {
        const updated = await createGraphNode(project._id, project.user_id, {
          node_type: nodeType,
          title: defaults.title,
          content: defaults.content
        });
        setProject(updated);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Failed to create node");
      }
    },
    [project, setProject]
  );

  const handleAutoLayout = useCallback(
    async (options?: { fitView?: boolean }) => {
      if (!project || applyingLayout) return;
      const layouts = computeIbisLayout(rationaleNodes, rationaleEdges);
      if (layouts.size === 0) return;

      setApplyingLayout(true);
      setNodes((current) =>
        current.map((node) => {
          const next = layouts.get(node.id);
          return next ? { ...node, position: next } : node;
        })
      );

      try {
        const layoutPayload = Object.fromEntries([...layouts.entries()]);
        const updated = await batchUpdateGraphLayouts(project._id, project.user_id, layoutPayload);
        setProject(updated);
        if (options?.fitView !== false) {
          window.setTimeout(() => runFitView(), 80);
        }
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Failed to apply layout");
        setProject(project);
      } finally {
        setApplyingLayout(false);
      }
    },
    [applyingLayout, project, rationaleEdges, rationaleNodes, runFitView, setNodes, setProject]
  );

  const handleConnect = useCallback(
    async (connection: Connection) => {
      if (!connection.source || !connection.target || !project) return;
      const stored = visualConnectionToStored(connection.source, connection.target, nodeById);
      if (!stored) return;

      setEdges((current) => {
        const exists = current.some((edge) => edge.source === connection.source && edge.target === connection.target);
        if (exists) return current;
        return addEdge(createFlowEdge(connection), current);
      });
      try {
        const updated = await createGraphEdge(
          project._id,
          project.user_id,
          stored.from_node_id,
          stored.to_node_id,
          stored.relation_type
        );
        setProject(updated);
      } catch (error) {
        setEdges(flowEdges);
        window.alert(error instanceof Error ? error.message : "Failed to create edge");
      }
    },
    [flowEdges, nodeById, project, setEdges, setProject]
  );

  const handleReconnect = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      if (!newConnection.source || !newConnection.target) return;
      if (!isValidVisualConnection(newConnection.source, newConnection.target, nodeById)) return;
      setEdges((current) => {
        const withoutOld = current.filter((edge) => edge.id !== oldEdge.id);
        if (withoutOld.some((edge) => edge.source === newConnection.source && edge.target === newConnection.target)) {
          return current;
        }
        return reconnectEdge(oldEdge, newConnection, current);
      });
      closeMenus();
    },
    [closeMenus, nodeById, setEdges]
  );

  const handleDeleteEdge = useCallback(
    async (edgeId: string) => {
      if (!project) return;
      closeMenus();
      setEdges((current) => current.filter((edge) => edge.id !== edgeId));
      try {
        const updated = await deleteGraphEdge(project._id, project.user_id, edgeId);
        setProject(updated);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Failed to delete edge");
      }
    },
    [closeMenus, project, setEdges, setProject]
  );

  const handleNodeDragStop = useCallback(
    async (_event: React.MouseEvent, node: Node<IbisNodeData>) => {
      if (!project) return;
      try {
        await updateGraphNode(project._id, project.user_id, node.id, {
          layout: { x: node.position.x, y: node.position.y }
        });
      } catch {
        // Layout sync is best-effort on drag end.
      }
    },
    [project]
  );

  const handleEdgeContextMenu = useCallback((event: MouseEvent | React.MouseEvent, edge: Edge) => {
    event.preventDefault();
    const clientX = "clientX" in event ? event.clientX : 0;
    const clientY = "clientY" in event ? event.clientY : 0;
    setAddNodeMenuOpen(false);
    setEdgeMenu({ x: clientX, y: clientY, edgeId: edge.id });
  }, []);

  const graphActions = useMemo(
    () => ({
      editingNodeId,
      onStartEdit: handleStartEdit,
      onSaveEdit: handleSaveEdit,
      onCancelEdit: handleCancelEdit,
      onDelete: handleDeleteNode,
      onToggleConsideration: handleToggleConsideration,
      onPopulateIssue: handlePopulateIssue,
      populatingIssueId,
      considerationQueueFull: considerationPositions.length >= MAX_CONSIDERATION_QUEUE_SIZE
    }),
    [
      considerationPositions.length,
      editingNodeId,
      handleCancelEdit,
      handleDeleteNode,
      handlePopulateIssue,
      handleSaveEdit,
      handleStartEdit,
      handleToggleConsideration,
      populatingIssueId
    ]
  );

  const emptyGraph = flowNodes.length === 0;
  const hasRequirements = (project?.brand_insights ?? []).some(
    (insight) =>
      insight.category === "explicit_requirement" || insight.category === "implicit_requirement"
  );
  const hasPersona = (project?.personas?.length ?? 0) > 0;
  const canUpdateMap = hasRequirements && hasPersona;
  const mapUpdateNeeded = isGraphStaleForUpdateMap(project?.stale);
  const mapSyncing = syncingMap || project?.stale?.rationale_graph === "generating";
  const showUpdateMapButton = mapUpdateNeeded || mapSyncing || (emptyGraph && canUpdateMap);
  const updateMapBlockedReason = !hasRequirements
    ? "Add brand requirements (parse Brief or edit Requirements) before updating the map."
    : !hasPersona
      ? "Provision at least one persona before updating the map."
      : null;

  const handleUpdateMap = useCallback(async () => {
    if (!project?._id || !project.user_id || syncingMap || !canUpdateMap) return;
    setSyncingMap(true);
    try {
      const updated = await syncMapFromScript(project._id, project.user_id);
      const nextNodes = updated.rationale_nodes ?? [];
      const nextEdges = updated.rationale_edges ?? [];
      const layouts = computeIbisLayout(nextNodes, nextEdges);
      if (layouts.size > 0) {
        const layoutPayload = Object.fromEntries([...layouts.entries()]);
        const withLayouts = await batchUpdateGraphLayouts(project._id, project.user_id, layoutPayload, {
          skipSnapshot: true
        });
        setProject(withLayouts);
      } else {
        setProject(updated);
      }
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Failed to update map");
    } finally {
      setSyncingMap(false);
    }
  }, [canUpdateMap, project, setProject, syncingMap]);

  return (
    <section className="map-workspace" ref={workspaceRef}>
      <div className="map-canvas-area">
      {showUpdateMapButton ? (
        <button
          className="map-update-map-btn"
          disabled={mapSyncing || !canUpdateMap}
          onClick={() => void handleUpdateMap()}
          title={!canUpdateMap ? (updateMapBlockedReason ?? undefined) : undefined}
          type="button"
          aria-busy={mapSyncing}
        >
          {mapSyncing ? "Updating…" : "Update Map"}
        </button>
      ) : null}
      {!emptyGraph && !mapUpdateNeeded && !mapSyncing ? (
        <div className="map-graph-status" aria-live="polite">
          {flowNodes.length} nodes · {flowEdges.length} edges
        </div>
      ) : null}
      {emptyGraph ? (
        <div className="map-empty-state">
          <p>
            {!hasRequirements && !hasPersona
              ? "Parse a Brief to extract requirements and provision Personas, then click Update Map to build the graph."
              : !hasRequirements
                ? "Parse a Brief or add requirements in the Requirements panel, then click Update Map."
                : !hasPersona
                  ? "Provision at least one Persona, then click Update Map to detect conflicts from the script."
                  : "Edit the script, requirements, or persona, then click Update Map to refresh the graph."}
          </p>
        </div>
      ) : null}
      <MapGraphActionsContext.Provider value={graphActions}>
        <ReactFlow
          className="map-flow"
          connectionLineStyle={EDGE_STYLE}
          defaultEdgeOptions={{ style: EDGE_STYLE, type: FLOW_EDGE_TYPE, reconnectable: true }}
          deleteKeyCode={["Backspace", "Delete"]}
          edges={displayEdges}
          edgesReconnectable
          fitViewOptions={{ padding: 0.25 }}
          maxZoom={2}
          minZoom={0.25}
          multiSelectionKeyCode={["Control", "Meta", "Shift"]}
          nodeTypes={nodeTypes}
          nodes={displayNodes}
          nodesConnectable
          nodesDraggable={!editingNodeId}
          panOnDrag={[1, 2]}
          selectionMode={SelectionMode.Partial}
          selectionOnDrag
          selectNodesOnDrag={false}
          isValidConnection={isValidConnection}
          onConnect={handleConnect}
          onBeforeDelete={handleBeforeDelete}
          onEdgeContextMenu={handleEdgeContextMenu}
          onEdgesChange={onEdgesChange}
          onInit={handleFlowInit}
          onNodeClick={handleNodeClick}
          onNodeContextMenu={(event) => event.preventDefault()}
          onNodesChange={onNodesChange}
          onNodesDelete={handleNodesDelete}
          onNodeDragStop={handleNodeDragStop}
          onPaneClick={handlePaneClick}
          onReconnect={handleReconnect}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#d4efff" gap={30} size={1.5} variant={BackgroundVariant.Dots} />
        </ReactFlow>
      </MapGraphActionsContext.Provider>

      {edgeMenu ? (
        <div
          className="map-context-menu"
          ref={edgeMenuRef}
          role="menu"
          style={{ left: edgeMenu.x, top: edgeMenu.y }}
        >
          <p className="map-context-menu-title">Edit connection</p>
          <button
            className="map-context-menu-item map-context-menu-item-danger"
            onClick={() => handleDeleteEdge(edgeMenu.edgeId)}
            role="menuitem"
            type="button"
          >
            Delete connection
          </button>
          <p className="map-context-menu-hint">Tip: Drag an endpoint to reconnect.</p>
        </div>
      ) : null}

      <aside className="map-overlay">
        <div className="map-legend">
          <h2 className="map-legend-title">IBIS FRAMEWORK</h2>
          <ul className="map-legend-list">
            {LEGEND_ITEMS.map((item) => (
              <li key={item.type}>
                <span className={`map-legend-dot dot-${item.type}`} />
                <span>{item.label}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="map-controls-wrap" ref={controlsRef}>
          <div className="map-controls">
            <button
              aria-expanded={addNodeMenuOpen}
              aria-haspopup="menu"
              aria-label="Add node"
              className={`map-control-btn map-control-btn-add ${addNodeMenuOpen ? "active" : ""}`}
              onClick={() => {
                setEdgeMenu(null);
                setAddNodeMenuOpen((open) => !open);
              }}
              type="button"
            >
              <IconAddNode />
            </button>
            <div className="map-control-divider" />
            <button aria-label="Zoom in" className="map-control-btn" onClick={() => zoomIn()} type="button">
              <IconPlus />
            </button>
            <button aria-label="Zoom out" className="map-control-btn" onClick={() => zoomOut()} type="button">
              <IconMinus />
            </button>
            <div className="map-control-divider" />
            <button
              aria-label="Auto layout"
              className="map-control-btn"
              disabled={applyingLayout || emptyGraph}
              onClick={() => void handleAutoLayout()}
              title="Auto layout"
              type="button"
            >
              <IconAutoLayout />
            </button>
            <button aria-label="Fit view" className="map-control-btn" onClick={() => fitView({ padding: 0.25 })} type="button">
              <IconFocus />
            </button>
          </div>

          {addNodeMenuOpen ? (
            <div
              className="map-add-node-menu"
              onMouseDown={(event) => event.stopPropagation()}
              role="menu"
            >
              <p className="map-add-node-menu-title">Add node</p>
              {LEGEND_ITEMS.map((item) => (
                <button
                  className={`map-add-node-menu-item map-add-node-menu-item-${item.type}`}
                  key={item.type}
                  onMouseDown={(event) => event.stopPropagation()}
                  onClick={() => handleAddNode(item.type)}
                  role="menuitem"
                  type="button"
                >
                  <span className={`map-legend-dot dot-${item.type}`} />
                  {item.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </aside>

      <aside className="map-overlay-right" aria-label="To be considered">
        <div className="map-consideration-panel">
          <h2 className="map-legend-title">TO BE CONSIDERED</h2>
          <p className="map-consideration-hint">
            Positions you adopt for the next script revision (up to {MAX_CONSIDERATION_QUEUE_SIZE}).
          </p>
          {considerationPositions.length === 0 && staleConsiderationIds.length === 0 ? (
            <p className="map-consideration-empty">Mark Position nodes from the node menu.</p>
          ) : (
            <ul className="map-consideration-list app-scrollbar">
              {considerationPositions.map((position) => (
                <li className="map-consideration-item" key={position.node_id}>
                  <strong className="map-consideration-item-title">{position.title}</strong>
                  <button
                    aria-label={`Remove "${position.title}" from consideration`}
                    className="requirement-delete-btn map-consideration-item-remove"
                    onClick={() => void handleToggleConsideration(position.node_id, false)}
                    type="button"
                  >
                    <IconTrash />
                  </button>
                </li>
              ))}
              {staleConsiderationIds.map((id) => (
                <li className="map-consideration-item map-consideration-item-stale" key={id}>
                  <span className="map-consideration-item-title">
                    <span className="map-node-status-tag map-node-status-resolved">Stance updated / stale</span>
                  </span>
                  <button
                    aria-label="Remove stale consideration entry"
                    className="requirement-delete-btn map-consideration-item-remove"
                    onClick={() => void handleToggleConsideration(id, false)}
                    type="button"
                  >
                    <IconTrash />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button
            className="map-consideration-generate-btn"
            disabled={!considerationPositions.length || generatingSchemes}
            onClick={() => void handleGenerateModificationPlan()}
            type="button"
          >
            {generatingSchemes ? "Generating…" : "Generate modification plan"}
          </button>
        </div>
      </aside>
      </div>
    </section>
  );
}

function IbisNode({ data, id }: NodeProps) {
  const nodeData = data as IbisNodeData;
  const actions = useContext(MapGraphActionsContext);
  const isEditing = actions?.editingNodeId === id;
  const [menuOpen, setMenuOpen] = useState(false);
  const [draftTitle, setDraftTitle] = useState(nodeData.title);
  const [draftContent, setDraftContent] = useState(nodeData.content);
  const menuRef = useRef<HTMLDivElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const articleRef = useRef<HTMLElement>(null);
  const updateNodeInternals = useUpdateNodeInternals();

  useEffect(() => {
    if (!isEditing) return;
    setDraftTitle(nodeData.title);
    setDraftContent(nodeData.content);
    titleInputRef.current?.focus();
    titleInputRef.current?.select();
  }, [isEditing, nodeData.content, nodeData.title]);

  useEffect(() => {
    if (!menuOpen) return;

    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as HTMLElement)) {
        setMenuOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen]);

  useEffect(() => {
    if (!isEditing) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        actions?.onCancelEdit();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [actions, isEditing]);

  useEffect(() => {
    const article = articleRef.current;
    if (!article) return;

    const syncHandlePositions = () => {
      updateNodeInternals(id);
    };

    syncHandlePositions();
    const observer = new ResizeObserver(syncHandlePositions);
    observer.observe(article);
    return () => observer.disconnect();
  }, [id, updateNodeInternals]);

  const handleSave = () => {
    actions?.onSaveEdit(id, draftTitle, draftContent);
  };

  const showTargetHandle = nodeData.nodeType === "position" || nodeData.nodeType === "argument";
  const showSourceHandle = nodeData.nodeType === "issue" || nodeData.nodeType === "position";

  return (
    <>
      {showTargetHandle ? (
        <Handle className="map-node-handle map-node-handle-target" position={Position.Left} type="target" />
      ) : null}
      <article
        ref={articleRef}
        className={`map-node map-node-${nodeData.nodeType}${isEditing ? " map-node-editing" : ""}`}
        style={{ width: nodeData.width }}
      >
        <header className="map-node-header">
          <span className="map-node-label">
            {nodeData.nodeType}
            {nodeData.sourceType ? <em className="map-node-source">{sourceLabel(nodeData.sourceType)}</em> : null}
          </span>
          <div className="map-node-header-actions">
            {nodeData.createdBy === "user" ? (
              <span className="map-node-status-tag map-node-status-user-created">User</span>
            ) : null}
            {nodeData.lifecycle === "resolved" ? (
              <span className="map-node-status-tag map-node-status-resolved">Resolved</span>
            ) : null}
            {nodeData.changeMark === "modified" ? (
              <span className="map-node-status-tag map-node-status-modified">Modified</span>
            ) : null}
            {nodeData.changeMark === "new" ? (
              <span className="map-node-status-tag map-node-status-new">New</span>
            ) : null}
            {nodeData.suggestion ? (
              <span
                className="map-node-status-tag map-node-status-suggestion"
                title="Agent suggestion (does not auto-edit user nodes)"
              >
                {nodeData.suggestion === "resolved?" ? "Suggest resolve?" : "Suggest modify?"}
              </span>
            ) : null}
            {nodeData.conflictTags && nodeData.conflictTags.length > 0
              ? nodeData.conflictTags.map((tag) => (
                  <span
                    key={tag}
                    className="map-conflict-tag"
                    data-tag={tag}
                    title={`Conflict group ${tag} — conflicts with other positions tagged [${tag}]`}
                  >
                    [{tag}]
                  </span>
                ))
              : null}
            {nodeData.inConsiderationQueue ? (
              <span className="map-node-consideration-tag">Consider</span>
            ) : null}
            <div className="map-node-menu-wrap" ref={menuRef}>
            <button
              aria-expanded={isEditing ? undefined : menuOpen}
              aria-haspopup={isEditing ? undefined : "menu"}
              aria-label={isEditing ? "Save changes" : "Node menu"}
              className={`map-node-menu${isEditing ? " map-node-menu-confirm" : ""}`}
              onClick={() => {
                if (isEditing) {
                  handleSave();
                  return;
                }
                setMenuOpen((open) => !open);
              }}
              type="button"
            >
              {isEditing ? <IconCheck /> : <IconMenuDots />}
            </button>
            {!isEditing && menuOpen ? (
              <div className="map-node-dropdown" role="menu">
                <button
                  className="map-node-dropdown-item"
                  onClick={() => {
                    setMenuOpen(false);
                    actions?.onStartEdit(id);
                  }}
                  role="menuitem"
                  type="button"
                >
                  Edit
                </button>
                {nodeData.nodeType === "issue" && nodeData.createdBy === "user" ? (
                  <button
                    className="map-node-dropdown-item"
                    disabled={actions?.populatingIssueId === id}
                    onClick={() => {
                      setMenuOpen(false);
                      actions?.onPopulateIssue(id);
                    }}
                    role="menuitem"
                    type="button"
                  >
                    {actions?.populatingIssueId === id ? "Generating…" : "Generate stance & argument"}
                  </button>
                ) : null}
                {nodeData.nodeType === "position" ? (
                  <button
                    className="map-node-dropdown-item"
                    disabled={!nodeData.inConsiderationQueue && actions?.considerationQueueFull}
                    onClick={() => {
                      setMenuOpen(false);
                      actions?.onToggleConsideration(id, !nodeData.inConsiderationQueue);
                    }}
                    role="menuitem"
                    title={
                      !nodeData.inConsiderationQueue && actions?.considerationQueueFull
                        ? `TO BE CONSIDERED is full (max ${MAX_CONSIDERATION_QUEUE_SIZE})`
                        : undefined
                    }
                    type="button"
                  >
                    {nodeData.inConsiderationQueue
                      ? "Remove from consideration"
                      : actions?.considerationQueueFull
                        ? "Add to consideration (list full)"
                        : "Add to consideration"}
                  </button>
                ) : null}
                <button
                  className="map-node-dropdown-item map-node-dropdown-item-danger"
                  onClick={() => {
                    setMenuOpen(false);
                    actions?.onDelete(id);
                  }}
                  role="menuitem"
                  type="button"
                >
                  Delete
                </button>
              </div>
            ) : null}
            </div>
          </div>
        </header>
        {isEditing ? (
          <>
            <input
              className="map-node-title-input nodrag nopan nowheel"
              onChange={(event) => setDraftTitle(event.target.value)}
              ref={titleInputRef}
              value={draftTitle}
            />
            <textarea
              className="map-node-content-input nodrag nopan nowheel"
              onChange={(event) => setDraftContent(event.target.value)}
              rows={4}
              value={draftContent}
            />
          </>
        ) : (
          <>
            <h3 className="map-node-title">{nodeData.title}</h3>
            <p className="map-node-content">{nodeData.content}</p>
          </>
        )}
        {nodeData.proposalCount ? (
          <footer className="map-node-footer">
            <IconChat />
            <span>{nodeData.proposalCount} AI Proposals</span>
          </footer>
        ) : null}
        {nodeData.reference ? (
          <div className="map-node-ref">
            <code>{nodeData.reference}</code>
          </div>
        ) : null}
      </article>
      {showSourceHandle ? (
        <Handle className="map-node-handle map-node-handle-source" position={Position.Right} type="source" />
      ) : null}
    </>
  );
}

function IconAddNode() {
  return (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <rect height="10" rx="1.5" width="10" x="2" y="2" />
      <line x1="7" x2="7" y1="4.5" y2="9.5" />
      <line x1="4.5" x2="9.5" y1="7" y2="7" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="7" x2="7" y1="2" y2="12" />
      <line x1="2" x2="12" y1="7" y2="7" />
    </svg>
  );
}

function IconMinus() {
  return (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="2" x2="12" y1="7" y2="7" />
    </svg>
  );
}

function IconFocus() {
  return (
    <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <rect height="12" rx="1.5" width="12" x="3" y="3" />
      <circle cx="9" cy="9" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  );
}

function IconAutoLayout() {
  return (
    <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <rect height="4" rx="1" width="4" x="2" y="2" />
      <rect height="4" rx="1" width="4" x="12" y="2" />
      <rect height="4" rx="1" width="4" x="7" y="12" />
      <path d="M6 4h6M9 6v6" strokeLinecap="round" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg aria-hidden="true" fill="none" height="10" stroke="currentColor" strokeWidth="2" viewBox="0 0 12 10" width="12">
      <path d="M1 5.5 4 8.5 11 1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconMenuDots() {
  return (
    <svg aria-hidden="true" fill="currentColor" height="10" viewBox="0 0 4 10" width="3">
      <circle cx="2" cy="1.5" r="0.9" />
      <circle cx="2" cy="5" r="0.9" />
      <circle cx="2" cy="8.5" r="0.9" />
    </svg>
  );
}

function IconChat() {
  return (
    <svg viewBox="0 0 12 10" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
      <path d="M1 1h10v6H4l-3 2V1z" />
    </svg>
  );
}

function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 6h18" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}
