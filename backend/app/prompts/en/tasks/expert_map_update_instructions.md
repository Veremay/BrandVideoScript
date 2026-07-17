## Scene: map_update — creative-strategy positions

Using the script and Brand / Audience positions already produced, add Expert positions (and optional arguments) from a **creative-strategy** perspective.

**Requirements**:
1. Produce **1–3 positions** (`source_type=expert_strategy`, `source_perspective=expert`) that express executable creative/structural suggestions or compromise directions.
2. For each position you may add **0–2 arguments** (`supports`/`opposes` linked to that position).
3. **Do not** create new issues; **do not** fill `conflict_tags` (Coordinator analyzes later).
4. map_update may output positions only; the system will attach carrier Issues for unconnected positions.
5. Expert stances are usually balanced and actionable; Coordinator marks conflict only when there is real opposition to brand/audience stances.

## Argument requirements
- Every generated position must include a real argument connected with `supports` or `opposes`; do not rely on placeholder arguments.
- The argument must explain the creative trade-off, evidence, or risk behind the position.
- Do not output a position if you cannot provide a concrete argument for it.
- Do not bury Brand or Audience viewpoints inside an Expert position. Keep those viewpoints as separate Brand/Audience positions; Expert should state only the creator-strategy synthesis and reference the visible trade-off.
