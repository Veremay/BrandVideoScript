## IBIS 节点类型

论证网络以 **Issue** 为起点：Issue 可在没有任何 Position / Argument 时单独存在（待办、开放问题、未来研究方向）。

### issue — 待讨论的问题
创作或品牌合作中需要被讨论、权衡或决策的问题。示例：「产品露出是否会破坏内容自然性？」  
**约束**：无需预设 Position 或 Argument，可作为根节点。

### position — 针对 issue 的立场
对某个 issue 的一种明确立场或方案方向。多个 position 可形成对立。边：`responds_to` 指向 issue（position → issue）。  
**约束**：必须 `responds_to` 至少一个 Issue，否则无效。

### argument — 支撑或反对某立场的理由
支持或反对某个 position 的论据。边：`supports` / `opposes` 指向 position（argument → position）。  
**约束**：必须 `supports` 或 `opposes` 至少一个 Position，否则无效。

### reference — 外部依据（少用）

## source_type

| 值 | 用途 |
|----|------|
| `brand_brief` | Brief 显式要求引发的问题 |
| `brand_inferred` | Wiki / 公开资料推断的隐性关切 |
| `audience_persona` | Persona 属性推论 |
| `audience_simulation` | 对脚本模拟观众反应 |
| `expert_strategy` | 创作策略与结构建议 |

## persist_rationale_graph 工具输入（ibis 字段）

```json
{
  "nodes": [{ "node_type": "issue", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" }],
  "edges": [{ "from_index": 1, "to_index": 0, "relation_type": "responds_to" }],
  "external_edges": [{ "from_index": 0, "to_node_id": "node_existing", "relation_type": "responds_to" }],
  "node_updates": [{ "node_id": "node_existing", "content": "…" }]
}
```

- `from_index`/`to_index`：本批 `nodes` 数组下标。
- `external_edges`：本批新节点与**已有图节点**连边（Expert 常用）。
- 可只提交 `issue` 节点（**不要**为 issue 写 `edges`；issue 是根节点，彼此独立）。
- `responds_to` 仅用于 **position → issue**；`supports` / `opposes` 仅用于 **argument → position**。
- 若提交 `position` / `argument`，须在同批 `edges` 或 `external_edges` 中连好父节点。
- 只输出 JSON，不要 markdown 代码块。
