# Implementation Tasks: Unit Testing Suite

**Feature**: Unit Testing Suite  
**Branch**: `unit-testing`  
**Date**: 2025-11-25

## Task List

### Task 1: Create Test Directory Structure
**Priority**: P1  
**Estimated Time**: 5 minutes  
**Status**: Pending

**Description**: Create `tests/` directory with subdirectories for unit and integration tests.

**Acceptance Criteria**:
- [ ] Directory `tests/` exists
- [ ] Directory `tests/unit/` exists
- [ ] Directory `tests/integration/` exists (empty, for future)
- [ ] All directories have `__init__.py` files

---

### Task 2: Create conftest.py with Fixtures
**Priority**: P1  
**Estimated Time**: 30 minutes  
**Status**: Pending

**Description**: Create `tests/conftest.py` with pytest fixtures for database, mocked APIs, and Telegram objects.

**Acceptance Criteria**:
- [ ] Fixture `db_session` creates in-memory SQLite database
- [ ] Fixture `mock_openrouter_api` mocks OpenRouter API responses
- [ ] Fixture `mock_perplexity_api` mocks Perplexity API responses
- [ ] Fixture `mock_telegram_message` creates mock Message object
- [ ] Fixture `mock_callback_query` creates mock CallbackQuery object
- [ ] Fixture `mock_fsm_context` creates mock FSMContext
- [ ] All fixtures are properly scoped (function/session)

**Implementation Notes**:
- Use `aioresponses` for mocking aiohttp calls
- Use `pytest-mock` for general mocking
- Use in-memory SQLite: `sqlite+aiosqlite:///:memory:`

---

### Task 3: Create test_services.py
**Priority**: P1  
**Estimated Time**: 45 minutes  
**Status**: Pending

**Description**: Create unit tests for OCRService and NormalizationService.

**Acceptance Criteria**:
- [ ] File `tests/unit/test_services.py` exists
- [ ] Test `test_ocr_parse_receipt_success` passes
- [ ] Test `test_ocr_parse_receipt_all_models_fail` passes
- [ ] Test `test_ocr_parse_receipt_retry_logic` passes
- [ ] Test `test_normalize_products_success` passes
- [ ] Test `test_normalize_products_empty_list` passes
- [ ] Test `test_normalize_products_all_models_fail` passes
- [ ] All tests use mocked APIs (no real API calls)
- [ ] Test coverage for services is 50%+

**Implementation Notes**:
- Mock OpenRouter API responses using `aioresponses`
- Test both success and failure scenarios
- Verify retry logic works correctly

---

### Task 4: Create test_handlers.py
**Priority**: P1  
**Estimated Time**: 60 minutes  
**Status**: Pending

**Description**: Create unit tests for fridge, recipes, and shopping handlers.

**Acceptance Criteria**:
- [ ] File `tests/unit/test_handlers.py` exists
- [ ] Test `test_fridge_show_summary_empty` passes
- [ ] Test `test_fridge_show_summary_with_products` passes
- [ ] Test `test_recipes_show_categories` passes
- [ ] Test `test_recipes_generate_success` passes
- [ ] Test `test_shopping_start_new_session` passes
- [ ] Test `test_shopping_scan_label_success` passes
- [ ] All tests use mocked database and Telegram objects
- [ ] Test coverage for handlers is 50%+

**Implementation Notes**:
- Mock database calls using fixtures
- Mock Telegram Bot API objects
- Mock FSM context for state management
- Test both success and error paths

---

### Task 5: Update pyproject.toml with Test Dependencies
**Priority**: P1  
**Estimated Time**: 5 minutes  
**Status**: Pending

**Description**: Add test dependencies to `pyproject.toml`.

**Acceptance Criteria**:
- [ ] `pytest-asyncio` is listed in dependencies
- [ ] `pytest-mock` is listed in dependencies
- [ ] `aioresponses` is listed in dependencies
- [ ] `pytest-cov` is listed (optional, for coverage)
- [ ] Dependencies are installable via `pip install -e .[test]` or similar

**Implementation Notes**:
- Add optional test dependencies section
- Or add to requirements.txt for simplicity

---

### Task 6: Run Tests Locally and Fix Issues
**Priority**: P1  
**Estimated Time**: 30 minutes  
**Status**: Pending

**Description**: Run `pytest tests/ -v` and fix any issues.

**Acceptance Criteria**:
- [ ] All tests pass: `pytest tests/ -v` exits with code 0
- [ ] No import errors
- [ ] No fixture errors
- [ ] All assertions pass
- [ ] Test output is clear and readable

**Implementation Notes**:
- Fix any import issues
- Fix any fixture scope issues
- Fix any async/await issues
- Ensure all mocks work correctly

---

### Task 7: Verify CI/CD Runs Tests
**Priority**: P2  
**Estimated Time**: 15 minutes  
**Status**: Pending

**Description**: Commit and push to trigger CI/CD, verify tests run.

**Acceptance Criteria**:
- [ ] Tests run in GitHub Actions
- [ ] All tests pass in CI
- [ ] CI workflow shows test results
- [ ] No CI-specific issues (Python version, dependencies, etc.)

---

### Task 8: Update Roadmap
**Priority**: P2  
**Estimated Time**: 5 minutes  
**Status**: Pending

**Description**: Mark unit testing task as completed in roadmap.

**Acceptance Criteria**:
- [ ] `plans/roadmap_v1.md` updated
- [ ] Task "Add Unit Tests for Core Services" marked as [x]
- [ ] Progress table updated
- [ ] Status changed to "Completed"

---

## Implementation Order

1. Task 1: Create directory structure
2. Task 2: Create conftest.py with fixtures
3. Task 5: Update pyproject.toml
4. Task 3: Create test_services.py
5. Task 4: Create test_handlers.py
6. Task 6: Run tests locally and fix issues
7. Task 7: Verify CI/CD
8. Task 8: Update roadmap

## Dependencies

- Task 1 → Task 2 (directories needed for files)
- Task 2 → Task 3, Task 4 (fixtures needed for tests)
- Task 5 → Task 6 (dependencies needed to run tests)
- Task 3, Task 4 → Task 6 (tests needed to run)
- Task 6 → Task 7 (local tests must pass before CI)
- Task 7 → Task 8 (verify success before updating roadmap)



