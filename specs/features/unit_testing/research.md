# Research: Unit Testing Implementation

**Date**: 2025-11-25  
**Feature**: Unit Testing Suite

## Testing Framework Research

### pytest vs unittest

| Framework | Async Support | Fixtures | Mocking | Decision |
|-----------|---------------|----------|---------|----------|
| **pytest** | ✅ Excellent (pytest-asyncio) | ✅ Rich fixture system | ✅ pytest-mock | ✅ **Selected** |
| unittest | ⚠️ Limited | ⚠️ Basic | ✅ unittest.mock | ❌ Less feature-rich |

**Decision**: pytest - already configured, better async support, richer fixtures.

### Mocking Libraries Comparison

| Library | Purpose | Ease of Use | Decision |
|---------|---------|-------------|----------|
| **pytest-mock** | General mocking | ⭐⭐⭐⭐⭐ | ✅ **Selected** |
| **aioresponses** | Mock aiohttp calls | ⭐⭐⭐⭐⭐ | ✅ **Selected** |
| **unittest.mock** | Built-in mocking | ⭐⭐⭐⭐ | ✅ Use for simple cases |
| **responses** | Mock requests (sync) | ⭐⭐⭐ | ❌ Not needed (using aiohttp) |

**Decision**: Use pytest-mock for general mocking, aioresponses for aiohttp calls.

### Database Testing Strategy

| Strategy | Pros | Cons | Decision |
|----------|------|------|----------|
| **In-memory SQLite** | Fast, no setup, realistic | SQLite-specific | ✅ **Selected** |
| **Mock database calls** | Fast, no DB needed | Less realistic, more complex | ❌ Rejected |
| **Test PostgreSQL** | Most realistic | Requires setup, slower | ❌ Overkill for unit tests |

**Decision**: In-memory SQLite - fast, realistic enough, works with existing SQLAlchemy setup.

### Coverage Tools

| Tool | Integration | Reporting | Decision |
|------|-------------|-----------|----------|
| **pytest-cov** | ✅ Excellent | ✅ HTML/terminal | ✅ **Selected** |
| **coverage.py** | ⚠️ Manual | ✅ Good | ❌ Less integrated |

**Decision**: pytest-cov - integrates seamlessly with pytest.

## Test Structure Research

### Standard pytest Structure

```
tests/
├── conftest.py          # Shared fixtures and configuration
├── unit/                # Unit tests (isolated, fast)
│   ├── test_services.py
│   └── test_handlers.py
└── integration/         # Integration tests (future)
```

**Rationale**: Clear separation, easy to run subsets (`pytest tests/unit/`), standard pattern.

### Fixture Design

**Database Fixture**:
- Create in-memory SQLite database
- Create all tables
- Provide session
- Cleanup after test

**API Mock Fixtures**:
- Mock OpenRouter API responses
- Mock Perplexity API responses
- Provide different response scenarios (success, failure, timeout)

**Telegram Mock Fixtures**:
- Mock Message objects
- Mock CallbackQuery objects
- Mock Bot object
- Mock FSMContext

## Test Cases Design

### OCRService Tests

1. **test_parse_receipt_success**: Mock successful API response, verify parsed receipt
2. **test_parse_receipt_all_models_fail**: Mock all models failing, verify exception
3. **test_parse_receipt_retry_logic**: Mock first attempt failing, second succeeding
4. **test_parse_receipt_invalid_json**: Mock API returning invalid JSON, verify handling
5. **test_parse_receipt_empty_items**: Mock API returning empty items list

### NormalizationService Tests

1. **test_normalize_products_success**: Mock successful API, verify normalized products
2. **test_normalize_products_empty_list**: Verify empty list returns empty list
3. **test_normalize_products_all_models_fail**: Mock all failures, verify raw items returned
4. **test_normalize_products_partial_match**: Mock partial normalization, verify merge logic
5. **test_normalize_products_invalid_json**: Mock invalid JSON, verify fallback

### Fridge Handler Tests

1. **test_show_fridge_summary_empty**: Mock empty fridge, verify empty message
2. **test_show_fridge_summary_with_products**: Mock products, verify summary
3. **test_fridge_list_pagination**: Mock multiple products, verify pagination
4. **test_fridge_list_empty**: Mock empty list, verify empty state

### Recipes Handler Tests

1. **test_show_recipe_categories**: Verify category buttons displayed
2. **test_generate_recipes_success**: Mock AI service, verify recipes generated
3. **test_generate_recipes_no_ingredients**: Mock no ingredients, verify empty state
4. **test_generate_recipes_cache_hit**: Mock cached recipes, verify cache used

### Shopping Handler Tests

1. **test_start_shopping_new_session**: Verify new session created
2. **test_start_shopping_existing_session**: Verify existing session reused
3. **test_scan_label_success**: Mock OCR service, verify label saved
4. **test_scan_label_no_session**: Verify error when no active session

## Dependencies Research

**Required Packages**:
- `pytest` - Already in pyproject.toml
- `pytest-asyncio` - For async test support
- `pytest-mock` - For mocking
- `aioresponses` - For mocking aiohttp calls
- `pytest-cov` - For coverage reporting (optional but recommended)

**Installation**:
```bash
pip install pytest pytest-asyncio pytest-mock aioresponses pytest-cov
```

## Performance Considerations

**Expected Test Runtime**:
- Setup/teardown: ~1s
- OCRService tests: ~2-3s (5 tests)
- NormalizationService tests: ~2-3s (5 tests)
- Handler tests: ~5-10s (10-15 tests)
- **Total**: ~10-17s (well under 30s target)

**Optimization**:
- Use fixtures efficiently (reuse database session)
- Mock all external calls (no network delays)
- Run tests in parallel (pytest-xdist) if needed

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [aioresponses](https://github.com/pnuckowski/aioresponses)
- [pytest-mock](https://pytest-mock.readthedocs.io/)


