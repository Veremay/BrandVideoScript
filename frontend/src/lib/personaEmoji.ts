const PERSONA_EMOJIS = [
  "😀",
  "🙂",
  "😎",
  "🤓",
  "🧑‍💻",
  "👩‍🎨",
  "🧑‍🚀",
  "🦊",
  "🐱",
  "🐶",
  "🌟",
  "🎯",
  "🎨",
  "📱",
  "☕",
  "🎮",
  "🚗",
  "✈️",
  "🏃",
  "💡"
];

export function randomPersonaEmoji(): string {
  return PERSONA_EMOJIS[Math.floor(Math.random() * PERSONA_EMOJIS.length)] ?? "🙂";
}

export function getPersonaEmoji(persona: { persona_id: string; icon?: string }): string {
  const icon = persona.icon?.trim();
  if (icon) return icon;

  let hash = 0;
  for (const char of persona.persona_id) {
    hash = (hash * 31 + char.charCodeAt(0)) | 0;
  }
  return PERSONA_EMOJIS[Math.abs(hash) % PERSONA_EMOJIS.length] ?? "🙂";
}
