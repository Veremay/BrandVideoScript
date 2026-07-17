## Output JSON (ibis nodes only)

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
    "external_edges": [
      { "from_index": 0, "to_node_id": "<issue_id>", "relation_type": "responds_to" }
    ],
    "node_updates": []
  }
}
```
