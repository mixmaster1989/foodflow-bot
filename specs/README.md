# Spec Kit Integration - FoodFlow Bot

This directory contains specifications and architecture documentation managed by GitHub Spec Kit.

## Structure

- **`constitution.yml`** / **`constitution.md`** - Core project principles and governance rules
- **`current_architecture.yml`** - Current architecture specification

## Usage

### Spec Kit Commands

Use these commands with your AI agent (Cursor):

- `/speckit.constitution` - Establish or update project principles
- `/speckit.specify` - Create baseline specification for a feature
- `/speckit.plan` - Create implementation plan
- `/speckit.tasks` - Generate actionable tasks
- `/speckit.implement` - Execute implementation

### Optional Commands

- `/speckit.clarify` - Ask structured questions to de-risk ambiguous areas
- `/speckit.analyze` - Cross-artifact consistency & alignment report
- `/speckit.checklist` - Generate quality checklists

## Related Documents

- [Roadmap v1.0](../plans/roadmap_v1.md) - Implementation roadmap
- [Architecture Analysis](../ARCHITECTURE_ANALYSIS.md) - Detailed project analysis

## Constitution Principles

1. **Spec-Driven Development** - All features start with specs
2. **Quality First** - Automated testing is mandatory
3. **Architecture Evolution** - Monolith → Modular Monolith → Microservices
4. **Technology Stack Standards** - Python 3.10+, aiogram 3.x, PostgreSQL
5. **Observability & Monitoring** - Structured logging required
6. **Security & Privacy** - No secrets in code, secure data handling

See [constitution.md](constitution.md) for full details.




