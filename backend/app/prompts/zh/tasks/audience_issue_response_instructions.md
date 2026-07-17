## 任务：针对用户 Issue 生成观众立场与论据

用户提出了一个议题（Issue）。从当前 Persona 视角给出：
- **1 个 position** 节点（观众立场）
- **1~2 个 argument** 节点（支撑或反对该 position 的理由）
- 用 `external_edges` 将 position（from_index: 0）以 `responds_to` 连到目标 issue（to_node_id）
- 用 `edges` 将每个 argument（from_index）以 `supports` 或 `opposes` 连到 position（to_index: 0）
- position / argument 的 `source_type` 限：`audience_persona`、`audience_simulation`
- 不要输出 issue 节点
