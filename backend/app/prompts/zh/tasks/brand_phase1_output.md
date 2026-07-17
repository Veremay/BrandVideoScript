## 输出 JSON（仅需求字段，不要 ibis）

字段枚举约束（严格使用以下值，不得自造）：
- `brand_insights[].category`：`"explicit_requirement"` | `"implicit_requirement"`
  - Brief 解析阶段禁止使用 `brand_feedback`；风险预判归入 `"implicit_requirement"`
- `brand_insights[].confidence`：`"high"` | `"medium"` | `"low"`

```json
{
  "constraints": ["纯文本，约束条件放这里"],
  "pr_risks": ["纯文本，审片风险放这里"],
  "brand_insights": [
    { "category": "explicit_requirement", "title": "…", "content": "…", "reason": "…", "confidence": "high" }
  ]
}
```
