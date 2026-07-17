## 场景：map_update — 创作策略立场

结合脚本与 Brand / Audience 已产出的立场，从**创作策略视角**补充 Expert 的 position（及可选 argument）。

**要求**：
1. 产出 **1~3 个 position**（`source_type=expert_strategy`，`source_perspective=expert`），表达可执行的创作/结构建议或折中方向。
2. 可为每个 position 补 **0~2 个 argument**（`supports`/`opposes` 连到对应 position）。
3. **不要**新建 issue；**不要**填写 `conflict_tags`（由 Coordinator 后续分析）。
4. map_update 中可只输出 position；系统会为未连接的 position 补充承载 Issue。
5. Expert 立场通常偏平衡、可执行；仅当与品牌/观众立场存在实质对立时才可能被 Coordinator 标记冲突。

## Argument requirements
- Every generated position must include a real argument connected with `supports` or `opposes`; do not rely on placeholder arguments.
- The argument must explain the creative trade-off, evidence, or risk behind the position.
- Do not output a position if you cannot provide a concrete argument for it.
- Do not bury Brand or Audience viewpoints inside an Expert position. Keep those viewpoints as separate Brand/Audience positions; Expert should state only the creator-strategy synthesis and reference the visible trade-off.
