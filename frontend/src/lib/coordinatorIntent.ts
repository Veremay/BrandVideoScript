/** Match backend coordinator_intent.py — when user asks Coordinator to generate revision schemes. */

const NODE_GENERATION_PATTERNS: RegExp[] = [
  /生成.{0,12}(节点|node)/i,
  /(新增|添加|创建).{0,8}(节点|node)/i
];

const GENERATE_SCHEME_PATTERNS: RegExp[] = [
  /生成.{0,16}(新|多方向|修改|修订)?方案/i,
  /(给|帮|请).{0,8}(我|咱|我们).{0,12}(生成|出|写|提供|给).{0,16}方案/i,
  /(重新|再).{0,6}生成.{0,12}方案/i,
  /新的?.{0,8}修改方案/i,
  /revision\s*proposals?/i,
  /(generate|create|draft).{0,24}(revision|modification).{0,12}(scheme|proposal)s?/i,
  /generate\s+(new\s+)?(revision\s+)?proposals?/i
];

export function wantsGenerateModificationSchemes(
  message: string,
  taskType?: string
): boolean {
  if (taskType === "generate_modification_schemes") return true;
  const text = message.trim();
  if (!text) return false;
  if (NODE_GENERATION_PATTERNS.some((pattern) => pattern.test(text)) && !/方案/.test(text)) {
    return false;
  }
  return GENERATE_SCHEME_PATTERNS.some((pattern) => pattern.test(text));
}

export function resolveCoordinatorTaskType(
  message: string,
  options: { hasQuotes: boolean; explicitTaskType?: string }
): "user_message" | "quote_analysis" | "script_delta" | "generate_modification_schemes" {
  if (options.explicitTaskType === "generate_modification_schemes") {
    return "generate_modification_schemes";
  }
  if (wantsGenerateModificationSchemes(message)) {
    return "generate_modification_schemes";
  }
  if (options.hasQuotes) return "quote_analysis";
  if (options.explicitTaskType === "script_delta") return "script_delta";
  return "user_message";
}
