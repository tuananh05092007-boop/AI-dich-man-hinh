# ADR 0002: Subtitle Generation Guard

- **Status:** Proposed
- **Decision:** Every subtitle instance has a stable subtitle_id; each replacement increments generation_id. Translation results are applied only when both identifiers match the active subtitle.
- **Context:** OCR and translation are asynchronous; completion order can differ from request order.
- **Consequences:** The tracker owns generation changes. Overlay update handling must reject stale results. Tests must force out-of-order completion.
