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
  columnX,
  isValidVisualConnection,
  layoutForNode,
  normalizeNodeType,
  NODE_HEIGHT,
  resolveFlowEndpoints,
  visualConnectionToStored
} from "@/lib/ibisLayout";
import type { RationaleEdge, RationaleNode, RationaleSourceType } from "@/lib/types";
import {
  createGraphEdge,
  createGraphNode,
  deleteGraphEdge,
  deleteGraphNode,
  syncMapFromScript,
  toggleGraphNegotiationQueue,
  updateGraphNode
} from "@/lib/api";
import { isGraphStaleFromScript } from "@/lib/stale";
import { useAppStore } from "@/store/appStore";

type MapNodeType = "issue" | "position" | "argument";

type IbisNodeData = {
  nodeType: MapNodeType;
  title: string;
  content: string;
  width: number;
  sourceType?: RationaleSourceType;
  status?: string;
  inNegotiationQueue?: boolean;
  proposalCount?: number;
  reference?: string;
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
const FLOW_EDGE_TYPE = "default";

function rationaleToFlowNode(
  node: RationaleNode,
  index: number,
  autoLayouts: Map<string, { x: number; y: number }>
): Node<IbisNodeData> | null {
  if (!node.node_id || !node.title) return null;
  const rawType = node.node_type === "reference" ? "argument" : node.node_type;
  const nodeType = (["issue", "position", "argument"].includes(rawType) ? rawType : "issue") as MapNodeType;
  const width = nodeType === "argument" ? 256 : 224;
  const height = NODE_HEIGHT;
  const position = layoutForNode(node, index, autoLayouts);
  return {
    id: node.node_id,
    type: "ibis",
    position,
    width,
    height,
    style: { width, height },
    data: {
      nodeType,
      title: node.title,
      content: node.content,
      width,
      sourceType: node.source_type,
      status: node.status,
      inNegotiationQueue: node.in_negotiation_queue
    }
  };
}

function rationaleToFlowEdge(edge: RationaleEdge, nodeById: Map<string, RationaleNode>): Edge | null {
  const endpoints = resolveFlowEndpoints(edge, nodeById);
  if (!endpoints) return null;
  return {
    id: edge.edge_id,
    source: endpoints.source,
    target: endpoints.target,
    type: FLOW_EDGE_TYPE,
    style: EDGE_STYLE,
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

const MapGraphActionsContext = createContext<{
  editingNodeId: string | null;
  onStartEdit: (nodeId: string) => void;
  onSaveEdit: (nodeId: string, title: string, content: string) => void;
  onCancelEdit: () => void;
  onDelete: (nodeId: string) => void;
  onToggleNegotiation: (nodeId: string, inQueue: boolean) => void;
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
  const graphKey = `${project?._id ?? "none"}:${project?.updated_at ?? ""}:${project?.rationale_nodes?.length ?? 0}`;

  return (
    <ReactFlowProvider>
      <MapViewContent key={graphKey} />
    </ReactFlowProvider>
  );
}

function MapViewContent() {
  const project = useAppStore((state) => state.project);
  const setProject = useAppStore((state) => state.setProject);
  const rationaleNodes = project?.rationale_nodes ?? [];
  const rationaleEdges = project?.rationale_edges ?? [];
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
  const [syncingMap, setSyncingMap] = useState(false);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const { zoomIn, zoomOut, fitView, screenToFlowPosition } = useReactFlow();
  const workspaceRef = useRef<HTMLElement>(null);
  const controlsRef = useRef<HTMLDivElement>(null);
  const edgeMenuRef = useRef<HTMLDivElement>(null);
  const hasFittedRef = useRef(false);

  const closeMenus = useCallback(() => {
    setAddNodeMenuOpen(false);
    setEdgeMenu(null);
  }, []);

  const runFitView = useCallback(() => {
    const workspace = workspaceRef.current;
    if (!workspace || workspace.clientWidth < 64 || workspace.clientHeight < 64) return;
    fitView({ padding: 0.25, duration: 150 });
    hasFittedRef.current = true;
  }, [fitView]);

  useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
    hasFittedRef.current = false;
  }, [flowNodes, flowEdges, setEdges, setNodes]);

  const handleFlowInit = useCallback(() => {
    requestAnimationFrame(() => runFitView());
  }, [runFitView]);

  useEffect(() => {
    hasFittedRef.current = false;
    const workspace = workspaceRef.current;
    if (!workspace) return;

    const observer = new ResizeObserver(() => {
      if (hasFittedRef.current) return;
      requestAnimationFrame(() => runFitView());
    });
    observer.observe(workspace);
    requestAnimationFrame(() => runFitView());

    return () => observer.disconnect();
  }, [runFitView]);

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
        const preview = labels.slice(0, 3).join("、");
        const more = uniqueIds.length > 3 ? ` 等 ${uniqueIds.length} 个` : "";
        const message =
          uniqueIds.length === 1
            ? `Delete "${labels[0] ?? "this node"}"?`
            : `Delete ${uniqueIds.length} selected nodes?${preview ? `\n${preview}${more}` : ""}`;
        if (!window.confirm(message)) return;
      }

      setEditingNodeId((current) => (current && uniqueIds.includes(current) ? null : current));
      setSelectedNodeIds((current) => current.filter((id) => !uniqueIds.includes(id)));

      try {
        let updated = project;
        for (const nodeId of uniqueIds) {
          updated = (await deleteGraphNode(project._id, project.user_id, nodeId)) ?? updated;
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
    const preview = labels.slice(0, 3).join("、");
    const more = nodesToDelete.length > 3 ? ` 等 ${nodesToDelete.length} 个` : "";
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

  const handleSelectionChange = useCallback(({ nodes: selected }: { nodes: Node[] }) => {
    setSelectedNodeIds(selected.map((node) => node.id));
  }, []);

  const handleToggleNegotiation = useCallback(
    async (nodeId: string, inQueue: boolean) => {
      if (!project) return;
      try {
        const updated = await toggleGraphNegotiationQueue(project._id, project.user_id, nodeId, inQueue);
        setProject(updated);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Failed to update negotiation queue");
      }
    },
    [project, setProject]
  );

  const handleAddNode = useCallback(
    async (nodeType: MapNodeType) => {
      if (!project) return;
      const defaults = NODE_DEFAULTS[nodeType];
      const pane = document.querySelector(".map-flow");
      const rect = pane?.getBoundingClientRect();
      const center = rect
        ? screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 })
        : { x: 320, y: 240 };
      const column = normalizeNodeType(nodeType);
      const sameColumnCount = nodes.filter((node) => normalizeNodeType(node.data.nodeType) === column).length;
      const offset = (sameColumnCount % 6) * 28;
      const layout = {
        x: columnX(column),
        y: center.y - NODE_HEIGHT / 2 + offset
      };
      setAddNodeMenuOpen(false);
      try {
        const updated = await createGraphNode(project._id, project.user_id, {
          node_type: nodeType,
          title: defaults.title,
          content: defaults.content,
          layout
        });
        setProject(updated);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Failed to create node");
      }
    },
    [nodes.length, project, screenToFlowPosition, setProject]
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
      onToggleNegotiation: handleToggleNegotiation
    }),
    [editingNodeId, handleCancelEdit, handleDeleteNode, handleSaveEdit, handleStartEdit, handleToggleNegotiation]
  );

  const negotiationIssues = useMemo(() => {
    const queue = new Set(project?.negotiation_queue ?? []);
    return (project?.rationale_nodes ?? []).filter(
      (node) => node.node_type === "issue" && (node.in_negotiation_queue || queue.has(node.node_id))
    );
  }, [project?.negotiation_queue, project?.rationale_nodes]);

  const emptyGraph = flowNodes.length === 0;
  const scriptChanged = isGraphStaleFromScript(project?.stale);
  const mapSyncing = syncingMap || project?.stale?.rationale_graph === "generating";

  const handleUpdateMap = useCallback(async () => {
    if (!project?._id || !project.user_id || syncingMap) return;
    setSyncingMap(true);
    try {
      const updated = await syncMapFromScript(project._id, project.user_id);
      setProject(updated);
      window.setTimeout(() => runFitView(), 80);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Failed to update map");
    } finally {
      setSyncingMap(false);
    }
  }, [project, runFitView, setProject, syncingMap]);

  return (
    <section className="map-workspace" ref={workspaceRef}>
      {scriptChanged || mapSyncing ? (
        <button
          className="map-update-map-btn"
          disabled={mapSyncing}
          onClick={() => void handleUpdateMap()}
          type="button"
          aria-busy={mapSyncing}
        >
          {mapSyncing ? "Updating…" : "Update Map"}
        </button>
      ) : null}
      {!emptyGraph && !scriptChanged && !mapSyncing ? (
        <div className="map-graph-status" aria-live="polite">
          {flowNodes.length} nodes · {flowEdges.length} edges
        </div>
      ) : null}
      {emptyGraph ? (
        <div className="map-empty-state">
          <p>Upload a Brief and run parse, or provision Personas from analytics, to populate the IBIS graph.</p>
        </div>
      ) : null}
      <MapGraphActionsContext.Provider value={graphActions}>
        <ReactFlow
          className="map-flow"
          connectionLineStyle={EDGE_STYLE}
          defaultEdgeOptions={{ style: EDGE_STYLE, type: FLOW_EDGE_TYPE, reconnectable: true }}
          deleteKeyCode={["Backspace", "Delete"]}
          edges={edges}
          edgesReconnectable
          fitViewOptions={{ padding: 0.25 }}
          maxZoom={2}
          minZoom={0.25}
          multiSelectionKeyCode={["Control", "Meta", "Shift"]}
          nodeTypes={nodeTypes}
          nodes={nodes}
          nodesConnectable
          nodesDraggable={!editingNodeId}
          panOnDrag={[1, 2]}
          selectionMode={SelectionMode.Partial}
          selectionOnDrag
          isValidConnection={isValidConnection}
          onConnect={handleConnect}
          onBeforeDelete={handleBeforeDelete}
          onEdgeContextMenu={handleEdgeContextMenu}
          onEdgesChange={onEdgesChange}
          onInit={handleFlowInit}
          onNodeContextMenu={(event) => event.preventDefault()}
          onNodesChange={onNodesChange}
          onNodesDelete={handleNodesDelete}
          onNodeDragStop={handleNodeDragStop}
          onPaneClick={closeMenus}
          onReconnect={handleReconnect}
          onSelectionChange={handleSelectionChange}
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

        <div className="map-negotiation-panel">
          <h2 className="map-legend-title">TO BE NEGOTIATED</h2>
          {negotiationIssues.length === 0 ? (
            <p className="map-negotiation-empty">Mark Issue nodes from the node menu.</p>
          ) : (
            <ul className="map-negotiation-list">
              {negotiationIssues.map((issue) => (
                <li key={issue.node_id}>
                  <strong>{issue.title}</strong>
                  <span>{issue.status ?? "needs_negotiation"}</span>
                </li>
              ))}
            </ul>
          )}
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
            <button aria-label="Fit view" className="map-control-btn" onClick={() => fitView({ padding: 0.25 })} type="button">
              <IconFocus />
            </button>
            {selectedNodeIds.length > 0 ? (
              <>
                <div className="map-control-divider" />
                <button
                  aria-label={`Delete ${selectedNodeIds.length} selected nodes`}
                  className="map-control-btn map-control-btn-delete"
                  onClick={() => void handleDeleteNodes(selectedNodeIds)}
                  type="button"
                >
                  <IconTrash />
                  <span className="map-control-btn-badge">{selectedNodeIds.length}</span>
                </button>
              </>
            ) : null}
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
        className={`map-node map-node-${nodeData.nodeType}${isEditing ? " map-node-editing" : ""}`}
        style={{ width: nodeData.width }}
      >
        <header className="map-node-header">
          <span className="map-node-label">
            {nodeData.nodeType}
            {nodeData.sourceType ? <em className="map-node-source">{sourceLabel(nodeData.sourceType)}</em> : null}
            {nodeData.inNegotiationQueue ? <em className="map-node-negotiation">negotiate</em> : null}
          </span>
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
                {nodeData.nodeType === "issue" ? (
                  <button
                    className="map-node-dropdown-item"
                    onClick={() => {
                      setMenuOpen(false);
                      actions?.onToggleNegotiation(id, !nodeData.inNegotiationQueue);
                    }}
                    role="menuitem"
                    type="button"
                  >
                    {nodeData.inNegotiationQueue ? "Remove from negotiation" : "Add to negotiation"}
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

function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
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
