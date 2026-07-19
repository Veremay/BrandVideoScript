"use client";

import { useAppStore } from "@/store/appStore";

type VanillaSetupSection = "requirements" | "conflicts";

type VanillaSetupContextPanelProps = {
  onClose: () => void;
  open: boolean;
  section: VanillaSetupSection;
};

export function VanillaSetupContextPanel({ onClose, open, section }: VanillaSetupContextPanelProps) {
  const project = useAppStore((state) => state.project);
  if (!open || !project) return null;

  const requirements = project.vanilla_setup_data?.brand_requirements?.trim() ?? "";
  const conflicts = project.vanilla_setup_data?.conflicts?.trim() ?? "";
  const isRequirements = section === "requirements";
  const title = isRequirements ? "Brand Requirements" : "Conflicts & Trade-offs";
  const content = isRequirements ? requirements : conflicts;

  return (
    <div className="persona-overlay" role="presentation">
      <button aria-label={`Close ${title}`} className="persona-overlay-backdrop" onClick={onClose} type="button" />
      <section aria-labelledby="vanilla-context-title" aria-modal="true" className="persona-panel vanilla-context-panel" role="dialog">
        <button aria-label="Close" className="persona-panel-close" onClick={onClose} type="button">
          <IconClose />
        </button>
        <header className="persona-panel-header">
          <div className="persona-panel-heading">
            <h1 className="persona-panel-title" id="vanilla-context-title">{title}</h1>
            <p className="persona-panel-subtitle">Captured during project setup and used as context by the AI assistant.</p>
          </div>
        </header>
        <div className="vanilla-context-body app-scrollbar">
          <p>{content || "No content was provided during setup."}</p>
        </div>
      </section>
    </div>
  );
}

function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}
