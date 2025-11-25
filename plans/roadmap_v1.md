# FoodFlow Bot Roadmap v1.0
**Created**: 2025-11-25  
**Status**: Active  
**Target Completion**: Q1 2026

## Overview

This roadmap addresses critical technical debt and establishes foundation for scalable growth. All items align with the [Constitution](specs/constitution.yml) and [Current Architecture](specs/current_architecture.yml).

---

## Immediate Goals (Priority: High)

### 1. Add CI/CD Workflow for Linting and Testing

**Status**: ✅ Completed  
**Priority**: P1 (Critical)  
**Estimated Effort**: 2-3 days  
**Completed**: 2025-11-25

**Tasks**:
- [x] Set up GitHub Actions workflow (`.github/workflows/ci.yml`)
- [x] Configure Python linting (ruff or black + flake8)
- [x] Set up pytest test framework
- [ ] Add test coverage reporting (coverage.py) - *Deferred to when tests are added*
- [ ] Configure pre-commit hooks (optional but recommended) - *Future enhancement*
- [x] Add quality gates (tests must pass, coverage threshold)

**Success Criteria**:
- ✅ All PRs automatically run linting and tests
- ⏳ Test coverage > 70% for new code - *Pending test creation*
- ✅ CI fails on linting errors or test failures

**Dependencies**: None

**Implementation Notes**:
- Created `.github/workflows/ci.yml` with GitHub Actions workflow
- Created `pyproject.toml` with Ruff configuration
- Workflow runs on push to `main` and PRs
- Supports Python 3.10, 3.11, 3.12
- Includes dependency caching for faster runs
- Gracefully handles missing tests directory
- See [specs/features/ci_cd_pipeline/](specs/features/ci_cd_pipeline/) for full documentation

---

### 2. Migrate Database to PostgreSQL (asyncpg)

**Status**: Not Started  
**Priority**: P1 (Critical)  
**Estimated Effort**: 3-5 days

**Tasks**:
- [ ] Set up PostgreSQL database (local dev + production)
- [ ] Update `DATABASE_URL` configuration
- [ ] Create Alembic migrations (replace manual migrations.py)
- [ ] Migrate existing SQLite data (if any production data exists)
- [ ] Update `database/base.py` to use asyncpg
- [ ] Test database connection and queries
- [ ] Update deployment configuration
- [ ] Document migration process

**Success Criteria**:
- PostgreSQL is primary database
- All migrations are versioned (Alembic)
- SQLite removed from production (kept for local dev only)
- Zero data loss during migration

**Dependencies**: None (can be done in parallel with CI/CD)

---

### 3. Refactor Shopping Mode Logic to Match Plan

**Status**: Partially Complete  
**Priority**: P2 (High)  
**Estimated Effort**: 5-7 days

**Tasks**:
- [ ] Review `SHOPPING_MODE_PLAN.md` checklist
- [ ] Complete missing Shopping Mode features:
  - [ ] Full integration with receipt processing
  - [ ] UI for unmatched items correction
  - [ ] Fuzzy matching improvements
- [ ] Add comprehensive tests for Shopping Mode
- [ ] Update documentation

**Success Criteria**:
- All items in SHOPPING_MODE_PLAN.md are completed
- Shopping Mode is fully functional end-to-end
- Test coverage > 80% for Shopping Mode handlers

**Dependencies**: CI/CD setup (for testing)

---

### 4. Implement Comprehensive Logging (Structured Logs)

**Status**: Not Started  
**Priority**: P2 (High)  
**Estimated Effort**: 2-3 days

**Tasks**:
- [ ] Replace current logging with structured logging (JSON format)
- [ ] Add log levels configuration (DEBUG, INFO, WARNING, ERROR)
- [ ] Implement log rotation (logrotate or Python logging.handlers)
- [ ] Add request ID tracking for correlation
- [ ] Add performance metrics logging (timing, API call durations)
- [ ] Configure log aggregation (optional: ELK stack or similar)

**Success Criteria**:
- All logs are structured (JSON format)
- Log rotation prevents disk space issues
- Request correlation possible via request IDs
- Performance metrics logged for critical paths

**Dependencies**: None

---

## Short-term Goals (Priority: Medium)

### 5. Add Unit Tests for Core Services

**Status**: Not Started  
**Priority**: P2 (High)  
**Estimated Effort**: 5-7 days

**Tasks**:
- [ ] Create `tests/` directory structure
- [ ] Write unit tests for OCR service
- [ ] Write unit tests for normalization service
- [ ] Write unit tests for matching service
- [ ] Write unit tests for AI service
- [ ] Add integration tests for receipt processing flow
- [ ] Add integration tests for Shopping Mode flow

**Success Criteria**:
- Test coverage > 70% overall
- All critical paths have tests
- Tests run in CI/CD pipeline

**Dependencies**: CI/CD setup

---

### 6. Implement Redis Caching Layer

**Status**: Not Started  
**Priority**: P3 (Medium)  
**Estimated Effort**: 3-4 days

**Tasks**:
- [ ] Set up Redis instance (local + production)
- [ ] Add Redis client (redis-py or aioredis)
- [ ] Implement caching for:
  - [ ] OCR results (cache by image hash)
  - [ ] Recipe generation (cache by ingredients hash)
  - [ ] Price search results (TTL: 24 hours)
- [ ] Add cache invalidation logic
- [ ] Configure cache TTLs appropriately

**Success Criteria**:
- Redis is integrated and working
- Cache hit rate > 50% for OCR requests
- Reduced external API calls by 30%+

**Dependencies**: PostgreSQL migration (for production setup)

---

### 7. Add API Rate Limiting and Queue System

**Status**: Not Started  
**Priority**: P3 (Medium)  
**Estimated Effort**: 4-5 days

**Tasks**:
- [ ] Implement rate limiting for external API calls
- [ ] Add request queue for OCR processing (Redis Queue or Celery)
- [ ] Implement retry logic with exponential backoff
- [ ] Add monitoring for API usage and limits
- [ ] Configure rate limits per API (OpenRouter, Perplexity)

**Success Criteria**:
- No API rate limit errors
- Queue system handles peak loads gracefully
- Retry logic prevents transient failures

**Dependencies**: Redis caching

---

## Long-term Goals (Priority: Low)

### 8. Extract Microservices (When Scale Demands)

**Status**: Not Started  
**Priority**: P4 (Future)  
**Estimated Effort**: 2-3 weeks

**Tasks**:
- [ ] Design service boundaries
- [ ] Extract OCR Service (standalone API)
- [ ] Extract Recipe Service (standalone API)
- [ ] Extract Price Service (standalone API)
- [ ] Add API Gateway
- [ ] Implement service-to-service communication
- [ ] Add service discovery

**Success Criteria**:
- Services are independently deployable
- Services can scale independently
- No breaking changes to Telegram Bot interface

**Dependencies**: Significant user growth (>10k active users)

---

### 9. Add REST API for Web/Mobile Clients

**Status**: Not Started  
**Priority**: P4 (Future)  
**Estimated Effort**: 1-2 weeks

**Tasks**:
- [ ] Design REST API (OpenAPI spec)
- [ ] Implement FastAPI or Flask REST endpoints
- [ ] Add authentication (JWT tokens)
- [ ] Add API documentation (Swagger/OpenAPI)
- [ ] Version API endpoints

**Success Criteria**:
- REST API is documented and versioned
- Authentication is secure
- API can serve web/mobile clients

**Dependencies**: Microservices extraction (optional, can be done before)

---

## Progress Tracking

**Last Updated**: 2025-11-25

| Goal | Status | Progress | Blockers |
|------|--------|----------|----------|
| CI/CD Workflow | ✅ Completed | 100% | None |
| PostgreSQL Migration | Not Started | 0% | None |
| Shopping Mode Refactor | In Progress | 40% | None |
| Structured Logging | Not Started | 0% | None |
| Unit Tests | Not Started | 0% | ~~CI/CD setup~~ ✅ Ready |
| Redis Caching | Not Started | 0% | PostgreSQL migration |
| Rate Limiting | Not Started | 0% | Redis caching |
| Microservices | Not Started | 0% | Scale requirements |
| REST API | Not Started | 0% | None |

---

## Notes

- All goals follow Spec-Driven Development principles
- Each goal should have a spec before implementation
- Technical debt items are prioritized based on impact
- Roadmap is reviewed and updated monthly

