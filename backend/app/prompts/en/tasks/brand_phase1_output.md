## Output JSON (requirements fields only — no ibis)

Field enum constraints (use these values only; do not invent new ones):
- `brand_insights[].category`: `"explicit_requirement"` | `"implicit_requirement"`
  - During Brief parse, do not use `brand_feedback`; put risk foresight under `"implicit_requirement"`
- `brand_insights[].confidence`: `"high"` | `"medium"` | `"low"`

```json
{
  "constraints": ["plain text constraints go here"],
  "pr_risks": ["plain text review risks go here"],
  "brand_insights": [
    { "category": "explicit_requirement", "title": "…", "content": "…", "reason": "…", "confidence": "high" }
  ]
}
```
