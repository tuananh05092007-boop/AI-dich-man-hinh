# ADR 0001: Modular Monolith

- **Status:** Proposed
- **Decision:** Use a modular monolith with bounded queues and worker boundaries.
- **Context:** The project is a single-user Windows desktop application with tightly coupled real-time stages. Microservices add deployment and latency overhead without a demonstrated need.
- **Consequences:** Modules have explicit contracts; workers can use asyncio, threads or processes. Process boundaries remain implementation details, not network services. Revisit only with measurable evidence.
