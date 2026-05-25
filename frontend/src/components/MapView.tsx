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
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

type MapNodeType = "issue" | "position" | "argument";

type IbisNodeData = {
  nodeType: MapNodeType;
  title: string;
  content: string;
  width: number;
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


const MAP_NODE_SEEDS: MapNodeSeed[] = [
  {
    id: "issue-root",
    nodeType: "issue",
    title: "Brand Identity Issue",
    content: "Lack of consistent visual narrative across social channels leads to fragmentation.",
    x: 164,
    y: 250,
    width: 224,
    proposalCount: 2
  },
  {
    id: "position-audience",
    nodeType: "position",
    title: "Audience Preference",
    content: "Gen-Z segments prioritize raw, unpolished aesthetics over high-gloss production.",
    x: 564,
    y: 100,
    width: 224
  },
  {
    id: "position-technical",
    nodeType: "position",
    title: "Technical Feasibility",
    content: "Internal rendering pipeline can't support 4K 60fps for all weekly content drops.",
    x: 564,
    y: 400,
    width: 224
  },
  {
    id: "argument-expert",
    nodeType: "argument",
    title: "Expert Refinement",
    content: "Creative Director suggests blending lo-fi textures with high-quality typography for contrast.",
    x: 964,
    y: 153,
    width: 256
  },
  {
    id: "argument-hardware",
    nodeType: "argument",
    title: "Hardware Constraint",
    content: "Current GPU farm load peaks at 88%, causing thermal throttling during multi-pass exports.",
    x: 964,
    y: 400,
    width: 256,
    reference: "ref: system_audit_v4.json"
  }
];

const MAP_EDGE_SEEDS: MapEdgeSeed[] = [
  { from: "issue-root", to: "position-audience" },
  { from: "issue-root", to: "position-technical" },
  { from: "position-audience", to: "argument-expert" },
  { from: "position-technical", to: "argument-hardware" }
];

const LEGEND_ITEMS: Array<{ type: MapNodeType; label: string }> = [
  { type: "issue", label: "Issue" },
  { type: "position", label: "Position" },
  { type: "argument", label: "Argument" }
];

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

const EDGE_STYLE = { stroke: "#7ed4fd", strokeWidth: 2 };

const MapGraphActionsContext = createContext<{
  editingNodeId: string | null;
  onStartEdit: (nodeId: string) => void;
  onSaveEdit: (nodeId: string, title: string, content: string) => void;
  onCancelEdit: () => void;
  onDelete: (nodeId: string) => void;
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
    type: "smoothstep",
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
    type: "smoothstep",
    style: EDGE_STYLE,
    reconnectable: true
  };
}

const initialNodes = MAP_NODE_SEEDS.map(toFlowNode);
const initialEdges = MAP_EDGE_SEEDS.map(toFlowEdge);

export function MapView() {
  return (
    <ReactFlowProvider>
      <MapViewContent />
    </ReactFlowProvider>
  );
}

function MapViewContent() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [addNodeMenuOpen, setAddNodeMenuOpen] = useState(false);
  const [edgeMenu, setEdgeMenu] = useState<EdgeMenuState | null>(null);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const { zoomIn, zoomOut, fitView, screenToFlowPosition } = useReactFlow();
  const controlsRef = useRef<HTMLDivElement>(null);
  const edgeMenuRef = useRef<HTMLDivElement>(null);

  const closeMenus = useCallback(() => {
    setAddNodeMenuOpen(false);
    setEdgeMenu(null);
  }, []);

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
    (nodeId: string, title: string, content: string) => {
      const nextTitle = title.trim();
      const nextContent = content.trim();
      if (!nextTitle) return;
      setNodes((current) =>
        current.map((item) =>
          item.id === nodeId
            ? { ...item, data: { ...item.data, title: nextTitle, content: nextContent } }
            : item
        )
      );
      setEditingNodeId((current) => (current === nodeId ? null : current));
    },
    [setNodes]
  );

  const handleCancelEdit = useCallback(() => {
    setEditingNodeId(null);
  }, []);

  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      const node = nodes.find((item) => item.id === nodeId);
      if (!node) return;
      const confirmed = window.confirm(`Delete "${node.data.title}"?`);
      if (!confirmed) return;
      setEditingNodeId((current) => (current === nodeId ? null : current));
      setNodes((current) => current.filter((item) => item.id !== nodeId));
      setEdges((current) => current.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
    },
    [nodes, setEdges, setNodes]
  );

  const handleAddNode = useCallback(
    (nodeType: MapNodeType) => {
      const defaults = NODE_DEFAULTS[nodeType];
      const pane = document.querySelector(".map-flow");
      const rect = pane?.getBoundingClientRect();
      const center = rect
        ? screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 })
        : { x: 320, y: 240 };
      const offset = (nodes.length % 6) * 28;
      const newNode: Node<IbisNodeData> = {
        id: `node-${Date.now()}`,
        type: "ibis",
        position: { x: center.x - defaults.width / 2 + offset, y: center.y - 80 + offset },
        data: {
          nodeType,
          title: defaults.title,
          content: defaults.content,
          width: defaults.width
        }
      };
      setNodes((current) => [...current, newNode]);
      setAddNodeMenuOpen(false);
    },
    [nodes.length, screenToFlowPosition, setNodes]
  );

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target || connection.source === connection.target) return;
      setEdges((current) => {
        const exists = current.some((edge) => edge.source === connection.source && edge.target === connection.target);
        if (exists) return current;
        return addEdge(createFlowEdge(connection), current);
      });
    },
    [setEdges]
  );

  const handleReconnect = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      if (!newConnection.source || !newConnection.target || newConnection.source === newConnection.target) return;
      setEdges((current) => {
        const withoutOld = current.filter((edge) => edge.id !== oldEdge.id);
        if (withoutOld.some((edge) => edge.source === newConnection.source && edge.target === newConnection.target)) {
          return current;
        }
        return reconnectEdge(oldEdge, newConnection, current);
      });
      closeMenus();
    },
    [closeMenus, setEdges]
  );

  const handleDeleteEdge = useCallback(
    (edgeId: string) => {
      setEdges((current) => current.filter((edge) => edge.id !== edgeId));
      closeMenus();
    },
    [closeMenus, setEdges]
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
      onDelete: handleDeleteNode
    }),
    [editingNodeId, handleCancelEdit, handleDeleteNode, handleSaveEdit, handleStartEdit]
  );

  return (
    <section className="map-workspace">
      <MapGraphActionsContext.Provider value={graphActions}>
        <ReactFlow
          className="map-flow"
          connectionLineStyle={EDGE_STYLE}
          defaultEdgeOptions={{ style: EDGE_STYLE, type: "smoothstep", reconnectable: true }}
          deleteKeyCode={["Backspace", "Delete"]}
          edges={edges}
          edgesReconnectable
          fitView
          fitViewOptions={{ padding: 0.25 }}
          maxZoom={2}
          minZoom={0.5}
          nodeTypes={nodeTypes}
          nodes={nodes}
          nodesConnectable
          nodesDraggable={!editingNodeId}
          onConnect={handleConnect}
          onEdgeContextMenu={handleEdgeContextMenu}
          onEdgesChange={onEdgesChange}
          onNodeContextMenu={(event) => event.preventDefault()}
          onNodesChange={onNodesChange}
          onPaneClick={closeMenus}
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

  return (
    <>
      <Handle className="map-node-handle map-node-handle-target" position={Position.Left} type="target" />
      <article
        className={`map-node map-node-${nodeData.nodeType}${isEditing ? " map-node-editing" : ""}`}
        style={{ width: nodeData.width }}
      >
        <header className="map-node-header">
          <span className="map-node-label">{nodeData.nodeType}</span>
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
      <Handle className="map-node-handle map-node-handle-source" position={Position.Right} type="source" />
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
