## 2026-03-29 - Contextual ARIA labels for dynamic subagent buttons
**Learning:** Action buttons that map to dynamic resources (like "Open child session" or "Cancel" for a specific subagent) need contextual `aria-label`s (e.g., `aria-label="Open child session: {title}"`) so screen reader users can distinguish between multiple identical buttons in a list.
**Action:** Always interpolate the target resource's title or identifier into the `aria-label` for repeated action buttons in lists or cards.
