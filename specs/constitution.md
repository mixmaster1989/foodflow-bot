# FoodFlow Bot Constitution

**Version**: 1.0.0 | **Ratified**: 2025-11-25 | **Last Amended**: 2025-11-25

## Philosophy

**Spec-Driven Development. Quality first. Automated testing is mandatory for new features.**

---

## Core Principles

### I. Spec-Driven Development

All features must start with specifications before implementation. Specifications define user scenarios, acceptance criteria, and success metrics. No code is written without a spec that has been reviewed and approved.

### II. Quality First

Code quality is non-negotiable. Automated testing is mandatory for all new features. Test-Driven Development (TDD) is preferred: write tests → get approval → tests fail → implement. Code reviews must verify test coverage and quality standards.

### III. Architecture Evolution

- **Current**: Monolithic Telegram Bot (SQLite)
- **Target**: Modular Monolith (PostgreSQL) → Microservices (when scale demands)
- Migration path must be documented and incremental.

### IV. Technology Stack Standards

- **Backend**: Python 3.10+, aiogram 3.x, SQLAlchemy 2.0 (Async)
- **Database**: PostgreSQL (production), SQLite (development only)
- **Caching**: Redis (planned)
- **Testing**: pytest, pytest-asyncio
- **CI/CD**: GitHub Actions (planned)

### V. Observability & Monitoring

Structured logging is mandatory (JSON format preferred). All external API calls must be logged with timing and error tracking. Critical paths must have metrics and alerting.

### VI. Security & Privacy

No secrets in code or version control (.env files excluded via .gitignore). API keys managed via environment variables. User data privacy: minimal data collection, secure storage.

---

## Architecture Constraints

- Monolithic structure is acceptable for current scale (<10k users)
- Database migrations must be versioned and reversible
- External API integrations must have fallback mechanisms
- No breaking changes to Telegram Bot API without migration plan

---

## Development Workflow

- All features require spec → plan → tasks → implementation flow
- PRs must include tests and pass CI checks
- Code reviews verify spec compliance and test coverage
- Technical debt items must be tracked in roadmap

---

## Governance

- Constitution supersedes all other practices
- Amendments require documentation, approval, and migration plan
- All PRs/reviews must verify compliance with constitution
- Complexity must be justified; simpler alternatives preferred (YAGNI)

---

## Related Documents

- [Current Architecture](current_architecture.yml)
- [Roadmap v1.0](../plans/roadmap_v1.md)
- [Architecture Analysis](../ARCHITECTURE_ANALYSIS.md)



