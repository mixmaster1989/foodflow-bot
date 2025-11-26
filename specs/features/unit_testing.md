# Feature Specification: Unit Testing Suite

**Feature Branch**: `unit-testing`  
**Created**: 2025-11-25  
**Status**: Draft  
**Input**: User description: "Create unit tests for Telegram bot to achieve 50%+ test coverage for core services and handlers"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Test Core Services (Priority: P1)

As a developer, I want core services (OCRService, NormalizationService) to have unit tests, so that I can verify they work correctly and catch regressions early.

**Why this priority**: Services contain critical business logic and external API calls. Testing them ensures reliability and helps with debugging.

**Independent Test**: Can be fully tested by mocking external APIs and verifying service methods return expected results. Tests can run independently without database or Telegram Bot API.

**Acceptance Scenarios**:

1. **Given** OCRService receives image bytes, **When** parse_receipt is called with mocked OpenRouter API, **Then** it should return parsed receipt data
2. **Given** OCRService receives invalid image, **When** all models fail, **Then** it should raise appropriate exception
3. **Given** NormalizationService receives raw product list, **When** normalize_products is called with mocked API, **Then** it should return normalized products with categories and calories
4. **Given** NormalizationService receives empty list, **When** normalize_products is called, **Then** it should return empty list
5. **Given** NormalizationService API fails, **When** all models fail, **Then** it should return raw items as fallback

---

### User Story 2 - Test Core Handlers (Priority: P1)

As a developer, I want core handlers (fridge, recipes, shopping) to have unit tests, so that I can verify user interactions work correctly.

**Why this priority**: Handlers are the main entry points for user interactions. Testing them ensures the bot responds correctly to user actions.

**Independent Test**: Can be tested by mocking database calls and Telegram Bot API, verifying handlers return correct responses and update state correctly.

**Acceptance Scenarios**:

1. **Given** user clicks "menu_fridge", **When** show_fridge_summary is called, **Then** it should return fridge summary with product count
2. **Given** user clicks "menu_recipes", **When** show_recipe_categories is called, **Then** it should show recipe category buttons
3. **Given** user selects recipe category, **When** generate_recipes_by_category is called, **Then** it should generate recipes from available ingredients
4. **Given** user starts shopping mode, **When** start_shopping is called, **Then** it should create shopping session and set FSM state
5. **Given** user scans label in shopping mode, **When** scan_label is called, **When** it should process label and save to database

---

### User Story 3 - Test Coverage Reporting (Priority: P2)

As a developer, I want test coverage reports, so that I can see which parts of the codebase are tested.

**Why this priority**: Coverage reports help identify untested code and guide testing efforts.

**Independent Test**: Can be tested by running pytest with coverage and verifying coverage report is generated.

**Acceptance Scenarios**:

1. **Given** tests are run, **When** pytest --cov is executed, **Then** it should generate coverage report
2. **Given** coverage report exists, **When** viewed, **Then** it should show coverage percentage for each module
3. **Given** coverage is below 50%, **When** CI runs, **Then** it should warn but not fail (for now)

---

### Edge Cases

- What happens when database connection fails during handler execution?
- How does system handle malformed API responses from OpenRouter?
- What happens when image bytes are empty or corrupted?
- How does system handle concurrent requests to same handler?
- What happens when FSM state is invalid or missing?
- How does system handle missing user data in database?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST have unit tests for OCRService with mocked OpenRouter API
- **FR-002**: System MUST have unit tests for NormalizationService with mocked API
- **FR-003**: System MUST have unit tests for at least 3 handlers (fridge, recipes, shopping)
- **FR-004**: System MUST use pytest with async support (pytest-asyncio)
- **FR-005**: System MUST mock external APIs (OpenRouter, Perplexity) in tests
- **FR-006**: System MUST provide test fixtures for database setup
- **FR-007**: System MUST provide test fixtures for mocking Telegram Bot API
- **FR-008**: System MUST achieve 50%+ test coverage for core services and handlers
- **FR-009**: Tests MUST run independently without external dependencies
- **FR-010**: Tests MUST be executable via `pytest tests/` command

### Key Entities *(include if feature involves data)*

- **Test Fixtures**: Reusable test setup (database, mocked APIs, Telegram mocks)
- **Unit Tests**: Tests for individual functions/methods
- **Mock Objects**: Simulated external dependencies (APIs, database)
- **Test Coverage**: Percentage of code covered by tests

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Test suite achieves 50%+ coverage for `services/ocr.py` and `services/normalization.py`
- **SC-002**: Test suite achieves 50%+ coverage for `handlers/fridge.py`, `handlers/recipes.py`, `handlers/shopping.py`
- **SC-003**: All tests pass locally with `pytest tests/ -v`
- **SC-004**: All tests pass in CI/CD pipeline
- **SC-005**: Test execution time is under 30 seconds for full suite
- **SC-006**: Tests can run without internet connection (all external APIs mocked)

## Technical Constraints

- Must use pytest (already in pyproject.toml)
- Must use pytest-asyncio for async support
- Must mock all external APIs (no real API calls in tests)
- Must use in-memory SQLite for database tests (or mock database)
- Must not require Telegram Bot API token for tests
- Must follow existing code structure and patterns

## Dependencies

- pytest (already configured)
- pytest-asyncio (for async test support)
- pytest-mock (for mocking)
- aioresponses (for mocking aiohttp calls) or unittest.mock
- SQLAlchemy test utilities (for database mocking)

