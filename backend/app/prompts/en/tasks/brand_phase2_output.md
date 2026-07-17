## Output JSON (ibis nodes only — no requirement fields)

Field enum constraints:
- `nodes[].node_type`: `"position"` or `"argument"` (Brand does not produce issues)
- `nodes[].source_type`: `"brand_brief"` | `"brand_inferred"`

```json
{
  "ibis": {
    "nodes": [
      { "node_type": "position", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" },
      { "node_type": "argument", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" }
    ],
    "edges": [
      { "from_index": 1, "to_index": 0, "relation_type": "supports" }
    ],
    "external_edges": [],
    "node_updates": []
  }
}
```

{{IBIS_TYPES}}
