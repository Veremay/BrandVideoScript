## IBIS 节点类型（自下而上 · 冲突驱动）

论证网络以 **Position（立场）为基本单元，自下而上生成**：先有各方的 position，当 **≥2 个 position 相互冲突**时，才派生出一个 **Issue** 来表示这个冲突。

> **核心约束：Issue 不能单独存在——Issue 即冲突。** 没有 ≥2 个相互冲突 position 的 Issue 会被服务端丢弃。

### position — 立场 / 观点（基本单元，可独立存在）
某一方（品牌 / 观众 / 专家）对脚本或合作的明确立场或方案方向。示例：「产品信息必须在前 3 秒出现」。
**约束**：position 是根级单元，**可以单独存在**（暂时没有与之冲突的立场）。无需连任何边即合法。

### issue — 冲突（派生节点，不可孤立）
表示 **≥2 个相互冲突 position 之间的争议焦点**。示例：「品牌露出强度 vs 内容自然性」。
**约束**：必须由 **≥2 个 position** 通过 `responds_to` 指向它；同时建议在冲突的两个 position 之间建立 `conflicts_with`。**禁止**产出没有 position 的孤立 issue。

### argument — 支撑 / 反对某立场的理由
支持或反对某个 position 的论据。边：`supports` / `opposes` 指向 position（argument → position）。
**约束**：必须 `supports` 或 `opposes` 至少一个 position。

### reference — 外部依据（少用）

## 关系类型

| relation_type | 方向 | 含义 |
|---------------|------|------|
| `responds_to` | position → issue | 该立场归属于某个冲突 |
| `conflicts_with` | position ↔ position | 两个立场相互冲突 |
| `supports` / `opposes` | argument → position | 论据支撑 / 反对立场 |

## source_type

| 值 | 用途 |
|----|------|
| `brand_brief` | Brief 显式要求引发的品牌立场 |
| `brand_inferred` | Wiki / 公开资料推断的隐性品牌立场 |
| `audience_persona` | Persona 属性推论的观众立场 |
| `audience_simulation` | 对脚本模拟观众反应得到的立场 |
| `expert_strategy` | 创作策略立场、冲突判定与结构建议 |

## persist_rationale_graph 工具输入（ibis 字段）

```json
{
  "nodes": [{ "node_type": "position", "title": "…", "content": "…", "source_type": "brand_brief", "source_perspective": "brand" }],
  "edges": [{ "from_index": 1, "to_index": 0, "relation_type": "responds_to" }],
  "external_edges": [{ "from_node_id": "node_existing_position", "to_index": 0, "relation_type": "responds_to" }],
  "node_updates": [{ "node_id": "node_existing", "content": "…" }]
}
```

- 每条 `edges` / `external_edges` 的端点都可用 **本批下标**（`from_index` / `to_index`）或 **已有节点 id**（`from_node_id` / `to_node_id`）任意组合。
- `external_edges` 用于把**已有图节点**接入本批新节点：典型用法是把来自 Brand / Audience / 已有图的多个 position 连到本批新建的 issue（`responds_to`），并在冲突的两个 position 间补 `conflicts_with`。
- 产出 issue 时**必须**同时给出：① **≥2 条** `responds_to`（position → issue）；② 建议在冲突 position 间给出 `conflicts_with`。
- position 可不连任何边（根级、暂无冲突）。argument 必须连到某个 position。
- **不要**产出没有 position 的孤立 issue（会被丢弃）。
- 只输出 JSON，不要 markdown 代码块。
