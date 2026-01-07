# Action Plan: Robustness & Reliability Audit (Jan 3, 2026)

## Phase 1: Critical Reliability Fixes
- [x] **Options Loader Robustness**: Add retry logic and better error handling for the 60MB master file download. [completed]
- [x] **Database Connection Resilience**: Implement retry logic for SQLAlchemy engine to handle transient DB disconnects. [completed]
- [x] **Memory Optimization**: Optimize `OptionsLoaderService` to clear raw JSON data after processing to save memory. [completed]

## Phase 2: Testing & Validation
- [x] **Dockerized Test Runner**: Create a script to run tests inside the Docker container to avoid local dependency issues. [completed]
- [x] **Integration Test**: Add a test case for the full signal-to-trade flow using a mock Upstox client. [completed]
- [x] **Schema Validation**: Add a startup check to verify all DB tables and columns (especially `tick_id` nullability) are correct. [completed]
- [x] **Test Suite Execution**: Run all tests and fix failures. [completed]
- [x] **Coverage Expansion**: Added tests for RiskManager, OptionsLoader, ML Pipeline, and API routes. [completed]

## Phase 3: Monitoring & Logging
- [x] **Health Check Endpoint**: Add a `/health` endpoint that checks DB, Redis, and Upstox API connectivity. [completed]
- [x] **Alerting**: Implement a basic log-based alerting for "Critical" errors (e.g., master file download failure). [completed]

---
*Note: Mark tasks as [completed] once finished.*
