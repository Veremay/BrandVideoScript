# llm-wiki — 品牌手册库（Markdown）

供 Brand Brief 流水线在 **Agentic Search** 阶段读取。目录约定：

- `brands/{brand_slug}/meta.json` — `display_name`、`aliases[]`（用于与 Brief 正文匹配）
- `brands/{brand_slug}/handbook.md` — 主手册（建议按 `##` 分节，便于截取片段）

`brand_slug` 与文件夹名一致。若 Brief 中出现 `aliases` 或 `display_name` 中的任一字符串，则优先匹配该品牌。

开发环境可使用 `_example` 示例品牌（Brief 中出现「示例科技」即可命中）。
