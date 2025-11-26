# Implementation Plan: Unit Testing Suite

**Branch**: `unit-testing` | **Date**: 2025-11-25 | **Spec**: [specs/features/unit_testing.md](../unit_testing.md)

**Input**: Feature specification from `/specs/features/unit_testing.md`

## Summary

Implement comprehensive unit test suite for FoodFlow Bot covering core services (OCRService, NormalizationService) and handlers (fridge, recipes, shopping). Tests will use pytest with async support, mock all external APIs, and achieve 50%+ coverage for target modules.

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**: pytest, pytest-asyncio, pytest-mock, aioresponses  
**Storage**: In-memory SQLite for database tests  
**Testing**: pytest with async support  
**Target Platform**: Local development and CI/CD  
**Project Type**: Single Python project (Telegram Bot)  
**Performance Goals**: Test suite completes in under 30 seconds  
**Constraints**: Must mock all external APIs, no real API calls, no Telegram Bot token required  
**Scale/Scope**: Unit tests for 2 services + 3 handlers, ~20-30 test cases

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

✅ **Constitution Compliance**:
- **Spec-Driven Development**: ✅ Spec created before implementation
- **Quality First**: ✅ Automated testing infrastructure (mandatory per constitution)
- **Technology Stack**: ✅ pytest, pytest-asyncio (standard Python testing)
- **Development Workflow**: ✅ Tests enable CI/CD quality gates

## Project Structure

### Documentation (this feature)

```text
specs/features/unit_testing/
├── plan.md              # This file
├── research.md          # Phase 0 output (below)
└── tasks.md             # Phase 2 output (to be generated)
```

### Source Code (repository root)

```text
tests/
├── conftest.py          # Pytest fixtures (database, mocks, etc.)
├── unit/
│   ├── test_services.py # Tests for OCRService, NormalizationService
│   └── test_handlers.py # Tests for fridge, recipes, shopping handlers
└── integration/         # Future integration tests (empty for now)
```

**Structure Decision**: Standard pytest structure with `conftest.py` for shared fixtures, `unit/` for unit tests, `integration/` reserved for future integration tests.

## Phase 0: Research

### Testing Framework Selection

**pytest**: ✅ Already configured in `pyproject.toml`
- **Rationale**: Standard Python testing framework, excellent async support
- **Async Support**: pytest-asyncio plugin

**Mocking Libraries**:
- **pytest-mock**: ✅ Standard pytest mocking plugin
- **aioresponses**: ✅ For mocking aiohttp calls (used by services)
- **unittest.mock**: ✅ Built-in, works with pytest

**Database Testing**:
- **In-memory SQLite**: ✅ Fast, no setup required, works with existing SQLAlchemy setup
- **Alternative**: Mock database calls (more complex, less realistic)

### Test Structure Research

**Standard pytest structure**:
```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Unit tests (isolated, fast)
└── integration/         # Integration tests (slower, real dependencies)
```

**Fixtures needed**:
- Database session (in-memory SQLite)
- Mocked OpenRouter API responses
- Mocked Perplexity API responses
- Mocked Telegram Bot objects (Message, CallbackQuery, etc.)
- Mocked FSM context

### Coverage Tools

**pytest-cov**: ✅ Standard coverage plugin for pytest
- Generates coverage reports
- Can set coverage thresholds
- Integrates with CI/CD

## Phase 1: Design

### Data Model

N/A - Tests don't persist data, use in-memory database.

### Quickstart

1. Create `tests/` directory structure
2. Create `tests/conftest.py` with fixtures
3. Create `tests/unit/test_services.py` with service tests
4. Create `tests/unit/test_handlers.py` with handler tests
5. Update `pyproject.toml` with test dependencies
6. Run `pytest tests/ -v` to verify

### Contracts

**Test Fixture Contract**:
- Input: None (fixtures are auto-injected)
- Output: Mocked objects (database, APIs, Telegram)
- Side effects: None (tests are isolated)

**Service Test Contract**:
- Input: Mocked API responses
- Output: Assertions on service return values
- Side effects: None (mocked APIs)

**Handler Test Contract**:
- Input: Mocked Telegram objects, mocked database
- Output: Assertions on handler responses/state changes
- Side effects: None (mocked database)

## Phase 2: Implementation Tasks

See `tasks.md` (to be generated).

## Complexity Tracking

> **No violations** - Standard pytest structure, no unnecessary complexity.

## Risk Assessment

**Low Risk Items**:
- pytest is well-documented and standard
- Mocking libraries are mature
- In-memory SQLite is straightforward

**Mitigation**:
- Start with simple tests, expand gradually
- Use fixtures to reduce duplication
- Mock external dependencies completely

## Implementation Order

1. Create test directory structure
2. Create `conftest.py` with fixtures
3. Create `test_services.py` with OCRService and NormalizationService tests
4. Create `test_handlers.py` with handler tests
5. Update `pyproject.toml` with dependencies
6. Run tests locally
7. Verify CI/CD runs tests
8. Update roadmap



