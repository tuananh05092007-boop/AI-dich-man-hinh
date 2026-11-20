# ADR 0003: CPU OCR and Hybrid Translation

- **Status:** Proposed
- **Decision:** Start OCR with PaddlePaddle CPU and use a hybrid NLLB/OpenAI translation interface.
- **Context:** The game shares a 6 GB laptop GPU with the application; the approved prompt explicitly selects CPU OCR and a hybrid translation design.
- **Consequences:** CPU OCR latency must be benchmarked. Local translation resource usage must be measured; cloud model IDs are configuration and must be verified against current API docs before selection.
