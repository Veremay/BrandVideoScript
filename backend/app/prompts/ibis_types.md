## IBIS 节点类型

论证网络以 **Position（立场）为基本单元**：各方先表达立场，Coordinator 负责分析立场之间的冲突，并通过 **conflict_tags** 标记冲突关系。Issue 恢复其经典含义——**待讨论的问题/议题**，而非冲突本身。

### position — 立场 / 观点（必须由 Issue 承载）
某一方（品牌 / 观众 / 专家）对脚本或合作的明确立场或方案方向。示例：「产品信息必须在前 3 秒出现」。

**conflict_tags 字段**：`["A"]`、`["B"]`、`["A", "C"]` 等。由 Coordinator 在冲突分析步骤中填写。
相同 tag 的两个 position 之间存在冲突，tag 可跨越不同的 issue。

**约束**：position 必须通过 `responds_to` 指向某个 issue，并且至少有 1 个真实 argument 通过 `supports` / `opposes` 指向它。Brand / Audience / Expert 在 map_update 中必须为每个 position 输出真实 argument；系统只补充承载 Issue，不会生成占位 Argument。如果 Agent 自己输出 issue / argument，则必须同时输出相应边。

### issue — 议题 / 问题（待讨论的话题）
表示**一个需要各方表态的议题或问题**。示例：「品牌露出时机如何平衡观众接受度？」。
Issue **不再代表冲突本身**；冲突由 position 上的 conflict_tags 表达。

**约束**：Agent 创建的 issue 必须有 **≥1 个 position** 通过 `responds_to` 指向它。用户手动创建的 issue 可以暂时为空（用户会手动补充或点击 Generate Position）。禁止产出没有任何连接的孤立 agent issue。

### argument — 支撑 / 反对某立场的理由
支持或反对某个 position 的论据。边：`supports` / `opposes` 指向 position（argument → position）。
**约束**：必须 `supports` 或 `opposes` 至少一个 position。

### reference — 外部依据（少用）

## 关系类型

| relation_type | 方向 | 含义 |
|---------------|------|------|
| `responds_to` | position → issue | 该立场是对某个议题的回应 |
| `supports` / `opposes` | argument → position | 论据支撑 / 反对立场 |

## source_type

| 值 | 用途 |
|----|------|
| `brand_brief` | Brief 显式要求引发的品牌立场 |
| `brand_inferred` | Wiki / 公开资料推断的隐性品牌立场 |
| `audience_persona` | Persona 属性推论的观众立场 |
| `audience_simulation` | 对脚本模拟观众反应得到的立场 |
| `expert_strategy` | 创作策略立场与结构建议 |

## persist_rationale_graph 工具输入（ibis 字段）

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

- 每条 `edges` / `external_edges` 的端点都可用 **本批下标**（`from_index` / `to_index`）或 **已有节点 id**（`from_node_id` / `to_node_id`）任意组合。
- `external_edges` 用于把**已有图节点**接入本批新节点。
- Agent 创建的 issue 至少需要 **1 条** `responds_to`（position → issue）。
- position 必须连到某个 issue，并至少被 1 个 argument 支撑或反对；argument 必须连到某个 position。
- **conflict_tags** 字段由 Brand / Audience / Expert Agent 产出时留空 `[]`；**Coordinator** 在独立的冲突分析步骤中填写。各 Agent **不需要**自行判断冲突。
- 只输出 JSON，不要 markdown 代码块。
