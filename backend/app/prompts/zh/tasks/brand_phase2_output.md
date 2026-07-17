## 输出 JSON（仅 ibis 节点，不要需求字段）

字段枚举约束：
- `nodes[].node_type`：`"position"` 或 `"argument"`（Brand 侧不产 issue）
- `nodes[].source_type`：`"brand_brief"` | `"brand_inferred"`

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
