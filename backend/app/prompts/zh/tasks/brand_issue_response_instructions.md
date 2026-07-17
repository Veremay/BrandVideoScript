## 任务：针对用户 Issue 生成品牌立场与论据

用户提出了一个议题（Issue）。从品牌方视角给出：
- **1 个 position** 节点（品牌立场）
- **1~2 个 argument** 节点（支撑或反对该 position 的理由）
- 用 `external_edges` 将 position（from_index: 0）以 `responds_to` 连到目标 issue（to_node_id）
- 用 `edges` 将每个 argument（from_index）以 `supports` 或 `opposes` 连到 position（to_index: 0）
- position / argument 的 `source_type` 限：`brand_brief`、`brand_inferred`
- 不要输出 issue 节点
- 用户可见文案禁止提及 Brand Wiki / wiki / Tavily 等内部名称；依据可写「根据品牌知识」「根据公开资料」「根据 Brief」
