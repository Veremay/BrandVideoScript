## IBIS node types

The argumentation network uses **Position (stance) as the basic unit**: each side states a stance first; the Coordinator analyzes conflicts among stances and marks them with **conflict_tags**. Issue returns to its classic meaning — a **question / topic under discussion**, not the conflict itself.

### position — stance / viewpoint (must be carried by an Issue)
A clear stance or direction from one side (brand / audience / expert) about the script or collaboration. Example: "Product information must appear in the first 3 seconds."

**conflict_tags field**: `["A"]`, `["B"]`, `["A", "C"]`, etc. Filled by the Coordinator in the conflict-analysis step.
Two positions with the same tag conflict; tags may span different issues.

**Constraints**: a position must `responds_to` some issue, and at least one real argument must `supports` / `opposes` it. Brand / Audience / Expert must output real arguments for every position in map_update; the system only attaches carrier Issues and never invents placeholder Arguments. If an Agent outputs issue / argument itself, it must also output the matching edges.

### issue — topic / question (matter under discussion)
Represents **a topic or question that needs parties to take a stance**. Example: "How should brand timing balance audience acceptance?"
An Issue **no longer represents the conflict itself**; conflicts are expressed via conflict_tags on positions.

**Constraints**: an Agent-created issue must have **≥1 position** that `responds_to` it. User-created issues may be empty temporarily (user will add positions or click Generate Position). Do not produce isolated agent issues with no connections.

### argument — reason supporting / opposing a stance
Evidence for or against a position. Edges: `supports` / `opposes` toward position (argument → position).
**Constraints**: must `supports` or `opposes` at least one position.

### reference — external evidence (use sparingly)

## Relation types

| relation_type | Direction | Meaning |
|---------------|-----------|---------|
| `responds_to` | position → issue | This stance responds to an issue |
| `supports` / `opposes` | argument → position | Argument supports / opposes the stance |

## source_type

| Value | Use |
|-------|-----|
| `brand_brief` | Brand stance driven by explicit Brief requirements |
| `brand_inferred` | Implicit brand stance inferred from brand knowledge / public sources |
| `audience_persona` | Audience stance inferred from Persona attributes |
| `audience_simulation` | Stance from simulating audience reaction to the script |
| `expert_strategy` | Creative-strategy stance and structural suggestions |

## persist_rationale_graph tool input (ibis field)

```json
{
  "nodes": [
    {
      "node_type": "position",
      "title": "…",
      "content": "…",
      "source_type": "brand_brief",
      "source_perspective": "brand",
      "conflict_tags": []
    }
  ],
  "edges": [{ "from_index": 1, "to_index": 0, "relation_type": "responds_to" }],
  "external_edges": [{ "from_node_id": "node_existing_position", "to_index": 0, "relation_type": "responds_to" }],
  "node_updates": [{ "node_id": "node_existing", "content": "…" }]
}
```

- Each `edges` / `external_edges` endpoint may mix **batch indices** (`from_index` / `to_index`) or **existing node ids** (`from_node_id` / `to_node_id`).
- `external_edges` attach **existing graph nodes** to this batch's new nodes.
- Agent-created issues need at least **1** `responds_to` (position → issue).
- A position must connect to an issue and be supported or opposed by ≥1 argument; an argument must connect to a position.
- Leave **conflict_tags** as `[]` when Brand / Audience / Expert produce nodes; **Coordinator** fills them in a separate conflict-analysis step. Agents **must not** judge conflicts themselves.
- Output JSON only — no markdown code fences.
