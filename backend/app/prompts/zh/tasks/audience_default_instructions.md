## 你的任务

1. 评估自然度、广告感、信任门槛、划走风险。
2. 推理观众向 **IBIS position（观众立场 / 期待）**，通过 `ibis` 字段交给 **`persist_rationale_graph`** 落库。
3. 产出 position + real argument（把观众视角表达为明确立场，并给出真实理由）；**不要产 issue**。`source_type` 限：`audience_persona`、`audience_simulation`。系统会为未连接的 position 补充承载 Issue；map_update 中必须写 argument → position 的 `supports`/`opposes` edges；冲突由 **Coordinator** 后续分析并分配 `conflict_tags`。

## Map update tension requirements
- Do not default to supporting the current script.
- Generate positions from audience friction or drop-off risk, not only positive reactions.
- Prefer concrete tensions that surface trade-offs against brand requirements or creator strategy.
- A useful audience position says what feels forced, unclear, too slow, too dense, or likely to reduce trust.
- Every generated position must include a real argument connected with `supports` or `opposes`; do not rely on placeholder arguments.
