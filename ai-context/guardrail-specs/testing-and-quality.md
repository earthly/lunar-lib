# Testing and Quality Guardrails

This document specifies possible policies for the **Testing and Quality** category. These guardrails cover unit testing standards, code coverage requirements, integration testing, performance testing, test quality metrics, test framework standards, and CI test execution requirements.

---

## Test Execution and CI Integration

### Tests Run in Pipeline

* `test-executed-in-ci` **Tests are executed in CI pipeline**: All components must have tests that run automatically in the CI/CD pipeline for every code change.
  * Collector(s): Detect test execution in CI pipeline by parsing CI configuration files and/or instrumenting CI jobs to capture test runner invocations
  * Component JSON:
    * `.testing.executed` - Boolean indicating tests were run in CI
    * `.testing.source.integration` - How tests were detected (ci, code)
    * `.ci.steps_executed.unit_test` - Boolean indicating unit tests step ran
  * Policy: Assert that tests were executed in CI
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-pass-default-branch` **Tests pass on the default branch**: The default branch must have passing tests at all times.
  * Collector(s): Query CI system for latest test results on default branch, or capture test results from CI pipeline runs
  * Component JSON:
    * `.testing.all_passing` - Boolean indicating all tests pass
    * `.testing.results.failed` - Number of failed tests
    * `.testing.branch` - Branch where tests were run
  * Policy: Assert that all tests pass on the default branch
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-results-captured` **Test results are captured and reported**: Test execution must produce machine-readable results (JUnit XML, JSON) that are collected and stored.
  * Collector(s): Detect test result artifacts in CI pipeline outputs or configured artifact locations
  * Component JSON:
    * `.testing.results_captured` - Boolean indicating results were captured
    * `.testing.results_format` - Format of captured results (junit, json, tap)
    * `.testing.results_path` - Path or URL to test results
  * Policy: Assert that test results are captured in a standard format
  * Configuration: Accepted result formats (default: ["junit", "json"])
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-run-on-pr` **Tests run on pull requests**: Tests must be executed on every pull request before merge.
  * Collector(s): Check CI configuration for PR triggers and verify test execution in PR context
  * Component JSON:
    * `.ci.pr_tests_enabled` - Boolean indicating tests run on PRs
    * `.vcs.branch_protection.required_checks` - Required status checks including tests
  * Policy: Assert that test execution is required for PRs
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-post-deployment` **Tests run against deployed version**: After deployment, tests should run against the deployed service to verify successful rollout.
  * Collector(s): Detect post-deployment test execution in CD pipeline or deployment hooks
  * Component JSON:
    * `.testing.post_deployment.executed` - Boolean for post-deploy tests
    * `.testing.post_deployment.environment` - Environment tested (staging, production)
    * `.testing.post_deployment.passed` - Boolean for test success
  * Policy: Assert that post-deployment tests are executed for production deployments
  * Configuration: Tags requiring post-deployment tests (e.g., ["production", "tier1"])
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### Test Execution Performance

* `test-suite-time-limit` **Test suite completes within time limit**: The full test suite should complete within a reasonable time to maintain fast feedback loops.
  * Collector(s): Capture test execution duration from CI pipeline or test runner output
  * Component JSON:
    * `.testing.duration_seconds` - Total test execution time in seconds
    * `.testing.duration_exceeded` - Boolean indicating duration exceeded threshold
  * Policy: Assert that test execution time is within the configured limit
  * Configuration: Maximum test duration in seconds (default: 600 for unit tests, 1800 for integration tests)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-individual-fast` **Individual test execution is fast**: Each individual test case should complete quickly to prevent slow test suites.
  * Collector(s): Parse test results for individual test execution times
  * Component JSON:
    * `.testing.slow_tests` - Array of tests exceeding time threshold
    * `.testing.slow_test_count` - Number of slow tests
    * `.testing.max_test_duration_seconds` - Duration of slowest test
  * Policy: Assert that no individual test exceeds the configured time limit
  * Configuration: Maximum individual test duration (default: 30 seconds for unit tests)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-parallelization-enabled` **Test parallelization is enabled**: Test suites should run in parallel where possible to minimize execution time.
  * Collector(s): Analyze test runner configuration and CI pipeline for parallelization settings
  * Component JSON:
    * `.testing.parallelization.enabled` - Boolean for parallel execution
    * `.testing.parallelization.workers` - Number of parallel workers
    * `.testing.parallelization.split_method` - How tests are split (file, class, method)
  * Policy: Assert that test parallelization is enabled for large test suites
  * Configuration: Minimum test count requiring parallelization (default: 100)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

---

## Unit Testing Standards

### Test Existence

* `test-unit-tests-exist` **Unit tests exist for the codebase**: Every codebase must have unit tests covering business logic.
  * Collector(s): Scan repository for test files matching language-specific patterns (test_*.py, *_test.go, *.test.js, *Test.java)
  * Component JSON:
    * `.testing.unit_tests.exist` - Boolean indicating unit tests are present
    * `.testing.unit_tests.file_count` - Number of test files found
    * `.testing.unit_tests.test_count` - Number of test cases found
  * Policy: Assert that unit tests exist
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-to-source-ratio` **Test-to-source ratio is adequate**: The number of test files should be proportional to source files.
  * Collector(s): Count test files and source files, calculate ratio
  * Component JSON:
    * `.testing.unit_tests.file_count` - Number of test files
    * `.repo.source_file_count` - Number of source files
    * `.testing.unit_tests.test_to_source_ratio` - Ratio of test files to source files
  * Policy: Assert that test-to-source ratio meets minimum threshold
  * Configuration: Minimum ratio (default: 0.5, meaning at least 1 test file per 2 source files)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Code Coverage

* `test-coverage-measured` **Code coverage is measured**: Test execution must produce code coverage metrics.
  * Collector(s): Detect coverage tool execution in CI and collect coverage reports (language-specific: go tool cover, coverage.py, nyc/istanbul, jacoco)
  * Component JSON:
    * `.testing.coverage` - Coverage data object (presence indicates coverage is measured)
    * `.testing.coverage.source.tool` - Coverage tool used
    * `.testing.coverage.source.integration` - How coverage was collected (ci)
  * Policy: Assert that code coverage is collected
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-coverage-minimum-threshold` **Overall code coverage meets minimum threshold**: The codebase must achieve a minimum percentage of code coverage.
  * Collector(s): Parse coverage reports and extract overall coverage percentage (language-specific collectors)
  * Component JSON:
    * `.testing.coverage.percentage` - Overall coverage percentage
    * `.testing.coverage.meets_threshold` - Boolean indicating threshold is met
    * `.testing.coverage.threshold` - Configured threshold
  * Policy: Assert that coverage percentage meets or exceeds the threshold
  * Configuration: Minimum coverage percentage (default: 80%)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-line-coverage-threshold` **Line coverage meets minimum threshold**: Specifically, line coverage must meet organizational standards.
  * Collector(s): Extract line coverage from coverage reports
  * Component JSON:
    * `.testing.coverage.lines.covered` - Number of covered lines
    * `.testing.coverage.lines.total` - Total lines
    * `.testing.coverage.lines.percentage` - Line coverage percentage
  * Policy: Assert that line coverage meets minimum threshold
  * Configuration: Minimum line coverage percentage (default: 80%)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-branch-coverage-threshold` **Branch coverage meets minimum threshold**: Branch/decision coverage should meet organizational standards for thorough testing.
  * Collector(s): Extract branch coverage from coverage reports (not all tools support this)
  * Component JSON:
    * `.testing.coverage.branches.covered` - Number of covered branches
    * `.testing.coverage.branches.total` - Total branches
    * `.testing.coverage.branches.percentage` - Branch coverage percentage
  * Policy: Assert that branch coverage meets minimum threshold
  * Configuration: Minimum branch coverage percentage (default: 70%)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-coverage-no-decrease` **Coverage does not decrease**: Code coverage should not regress between commits or releases.
  * Collector(s): Compare current coverage with previous coverage from stored history or baseline
  * Component JSON:
    * `.testing.coverage.percentage` - Current coverage
    * `.testing.coverage.previous_percentage` - Previous coverage (from baseline)
    * `.testing.coverage.delta` - Change in coverage (can be negative)
  * Policy: Assert that coverage delta is not negative (or within acceptable margin)
  * Configuration: Allowed coverage decrease margin (default: 0, no decrease allowed)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-critical-path-coverage` **Critical paths have higher coverage**: Core business logic modules must have higher coverage than the overall threshold.
  * Collector(s): Parse coverage reports with per-file/package breakdown, filter by critical path patterns
  * Component JSON:
    * `.testing.coverage.files` - Array of per-file coverage data
    * `.testing.coverage.critical_paths` - Array of coverage for critical modules
    * `.testing.coverage.critical_path_percentage` - Average coverage for critical paths
  * Policy: Assert that critical path modules meet elevated coverage threshold
  * Configuration: Critical path patterns (e.g., ["src/core/", "lib/payments/"]), elevated threshold (default: 90%)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-no-zero-coverage-files` **No files with zero coverage**: All source files should have at least some test coverage.
  * Collector(s): Parse coverage reports and identify files with 0% coverage
  * Component JSON:
    * `.testing.coverage.files` - Array of per-file coverage
    * `.testing.coverage.zero_coverage_files` - Array of files with 0% coverage
    * `.testing.coverage.has_zero_coverage_files` - Boolean for presence of uncovered files
  * Policy: Assert that no source files have zero coverage
  * Configuration: Excluded file patterns (e.g., generated files, migrations)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-new-code-coverage` **New code has coverage**: Code added in a PR should have test coverage, not just the overall codebase.
  * Collector(s): Compare coverage report with PR diff to calculate coverage of changed lines
  * Component JSON:
    * `.testing.coverage.new_code_percentage` - Coverage of lines added in PR
    * `.testing.coverage.new_lines_covered` - Covered lines in PR
    * `.testing.coverage.new_lines_total` - Total new lines in PR
  * Policy: Assert that new code coverage meets threshold
  * Configuration: Minimum new code coverage (default: 80%)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### Test Organization

* `test-file-naming-convention` **Test files follow naming conventions**: Test files must follow language-specific naming conventions for discoverability.
  * Collector(s): Scan for test files and validate naming against language conventions
  * Component JSON:
    * `.testing.unit_tests.files` - Array of test file paths
    * `.testing.unit_tests.naming_violations` - Array of files not following convention
    * `.testing.unit_tests.naming_compliant` - Boolean for all files compliant
  * Policy: Assert that all test files follow naming conventions
  * Configuration: Naming patterns per language (e.g., Python: "test_*.py", Go: "*_test.go")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-organization` **Tests are co-located or in standard directories**: Tests should be organized in predictable locations (co-located with source or in test directories).
  * Collector(s): Analyze test file locations and compare to source structure
  * Component JSON:
    * `.testing.unit_tests.organization` - Test organization pattern (colocated, separate, mixed)
    * `.testing.unit_tests.test_directories` - Array of test directory paths
  * Policy: Assert that tests follow approved organization pattern
  * Configuration: Allowed organization patterns (default: ["colocated", "tests/", "test/", "__tests__/"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-no-production-code` **Test files do not contain production code**: Test files should only contain test code, not business logic that gets imported by production code.
  * Collector(s): Analyze imports in source code to detect imports from test files
  * Component JSON:
    * `.testing.unit_tests.imported_by_source` - Array of test files imported by source
    * `.testing.unit_tests.clean_separation` - Boolean indicating proper separation
  * Policy: Assert that no test files are imported by production code
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Integration Testing

### Integration Test Existence

* `test-integration-exists` **Integration tests exist for services**: Services (especially API services) must have integration tests.
  * Collector(s): Scan for integration test files in standard locations (integration/, e2e/, or files matching *_integration_test.*, *_e2e_test.*)
  * Component JSON:
    * `.testing.integration_tests.exist` - Boolean indicating integration tests present
    * `.testing.integration_tests.file_count` - Number of integration test files
    * `.testing.integration_tests.test_count` - Number of integration test cases
  * Policy: Assert that integration tests exist for service-type components
  * Configuration: Tags requiring integration tests (e.g., ["service", "api", "backend"])
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 8 (File Parsing and Schema Extraction)

* `test-integration-in-ci` **Integration tests run in CI**: Integration tests must be executed as part of the CI pipeline.
  * Collector(s): Detect integration test execution in CI configuration or pipeline runs
  * Component JSON:
    * `.testing.integration_tests.executed_in_ci` - Boolean for CI execution
    * `.ci.steps_executed.integration_test` - Boolean for integration test step
  * Policy: Assert that integration tests are executed in CI
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 8 (File Parsing and Schema Extraction)

* `test-api-endpoint-coverage` **API endpoints have integration test coverage**: All API endpoints should have at least one integration test.
  * Collector(s): Extract API endpoints from OpenAPI spec or route definitions, cross-reference with integration tests
  * Component JSON:
    * `.api.endpoints` - Array of API endpoints
    * `.testing.integration_tests.endpoints_covered` - Array of endpoints with tests
    * `.testing.integration_tests.endpoint_coverage_percentage` - Percentage of endpoints tested
  * Policy: Assert that endpoint coverage meets threshold
  * Configuration: Minimum endpoint coverage percentage (default: 100%)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Contract Testing

* `test-contract-tests-exist` **Consumer contract tests exist**: Services consuming APIs should have contract tests to verify API compatibility.
  * Collector(s): Scan for contract test files (Pact, Spring Cloud Contract, etc.)
  * Component JSON:
    * `.testing.contract_tests.exist` - Boolean for contract tests presence
    * `.testing.contract_tests.tool` - Contract testing tool used (pact, spring-cloud-contract)
    * `.testing.contract_tests.consumers` - Array of tested consumer contracts
  * Policy: Assert that contract tests exist for services with declared dependencies
  * Configuration: Tags requiring contract tests
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-contract-provider-verified` **Provider contract verification runs**: API providers must verify contracts from consumers.
  * Collector(s): Detect contract verification step in CI or contract broker integration
  * Component JSON:
    * `.testing.contract_tests.provider_verified` - Boolean for provider verification
    * `.testing.contract_tests.contracts_verified` - Number of contracts verified
    * `.testing.contract_tests.verification_passed` - Boolean for all contracts passing
  * Policy: Assert that provider verification is enabled and passing
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-contract-published` **Contract tests are published to broker**: Contract test results should be published to a central broker for visibility.
  * Collector(s): Check for contract broker publishing step in CI or broker API query
  * Component JSON:
    * `.testing.contract_tests.published` - Boolean for publication to broker
    * `.testing.contract_tests.broker_url` - Contract broker URL
  * Policy: Assert that contracts are published to the central broker
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### End-to-End Testing

* `test-e2e-exists` **End-to-end tests exist for critical user journeys**: Critical user-facing services must have E2E tests covering key user journeys.
  * Collector(s): Scan for E2E test files (Cypress, Playwright, Selenium patterns)
  * Component JSON:
    * `.testing.e2e_tests.exist` - Boolean for E2E tests presence
    * `.testing.e2e_tests.framework` - E2E framework used
    * `.testing.e2e_tests.test_count` - Number of E2E tests
  * Policy: Assert that E2E tests exist for user-facing services
  * Configuration: Tags requiring E2E tests (e.g., ["frontend", "user-facing", "web"])
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-e2e-journey-coverage` **E2E tests cover critical user journeys**: E2E tests should cover documented critical paths.
  * Collector(s): Cross-reference E2E test names/descriptions with documented user journeys
  * Component JSON:
    * `.testing.e2e_tests.journeys_documented` - Array of documented critical journeys
    * `.testing.e2e_tests.journeys_covered` - Array of journeys with E2E tests
    * `.testing.e2e_tests.journey_coverage_percentage` - Percentage of journeys tested
  * Policy: Assert that all documented critical journeys have E2E tests
  * Configuration: Journey documentation location
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-e2e-staging-gate` **E2E tests run in staging before production deployment**: E2E tests must pass against staging before production release.
  * Collector(s): Check deployment pipeline for E2E test gate on staging
  * Component JSON:
    * `.testing.e2e_tests.staging_execution` - Boolean for staging test execution
    * `.testing.e2e_tests.staging_passed` - Boolean for staging tests passing
    * `.deployment.gates.e2e_staging` - Boolean for E2E gate configured
  * Policy: Assert that E2E tests are a deployment gate for production
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

---

## Performance Testing

### Performance Test Existence

* `test-performance-exists` **Performance tests exist**: Production services must have performance tests to validate behavior under load.
  * Collector(s): Scan for performance test files (k6, Gatling, JMeter, Locust patterns)
  * Component JSON:
    * `.testing.performance_tests.exist` - Boolean for performance tests presence
    * `.testing.performance_tests.framework` - Performance testing framework used
    * `.testing.performance_tests.test_count` - Number of performance test scenarios
  * Policy: Assert that performance tests exist for production services
  * Configuration: Tags requiring performance tests (e.g., ["production", "tier1", "tier2"])
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-performance-scheduled` **Performance tests run regularly**: Performance tests should run on a schedule, not just ad-hoc.
  * Collector(s): Check CI configuration for scheduled performance test jobs
  * Component JSON:
    * `.testing.performance_tests.scheduled` - Boolean for scheduled execution
    * `.testing.performance_tests.schedule` - Cron schedule or frequency
    * `.testing.performance_tests.last_run` - Timestamp of last execution
  * Policy: Assert that performance tests are scheduled to run regularly
  * Configuration: Minimum frequency (default: weekly)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-performance-results-stored` **Performance test results are stored**: Performance test results should be stored for trend analysis.
  * Collector(s): Check for performance result storage (Grafana, dedicated performance platform)
  * Component JSON:
    * `.testing.performance_tests.results_stored` - Boolean for result storage
    * `.testing.performance_tests.results_url` - URL to performance dashboard
  * Policy: Assert that performance results are stored
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### Load Testing

* `test-load-realistic-traffic` **Load tests simulate production traffic patterns**: Load tests should use realistic traffic patterns based on production data.
  * Collector(s): Analyze load test configuration for traffic modeling
  * Component JSON:
    * `.testing.load_tests.exist` - Boolean for load tests presence
    * `.testing.load_tests.traffic_model` - Traffic model type (realistic, synthetic)
    * `.testing.load_tests.scenarios` - Array of load test scenarios
  * Policy: Assert that load tests use realistic traffic patterns
  * Configuration: Tags requiring realistic traffic models
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-load-thresholds-defined` **Load test thresholds are defined**: Load tests must have pass/fail thresholds for key metrics.
  * Collector(s): Parse load test configuration for threshold definitions
  * Component JSON:
    * `.testing.load_tests.thresholds_defined` - Boolean for threshold presence
    * `.testing.load_tests.thresholds` - Array of defined thresholds (response_time, error_rate, throughput)
  * Policy: Assert that load test thresholds are defined
  * Configuration: Required threshold metrics (default: ["response_time_p95", "error_rate"])
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-load-meets-slos` **Load tests achieve performance SLOs**: Load test results should demonstrate the service meets its SLOs.
  * Collector(s): Parse load test results and compare against SLO definitions
  * Component JSON:
    * `.testing.load_tests.slo_validation` - Boolean for SLO validation
    * `.testing.load_tests.slo_results` - Array of SLO validation results
    * `.testing.load_tests.slos_met` - Boolean for all SLOs passing
  * Policy: Assert that load tests validate and meet SLOs
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### Benchmark Testing

* `test-benchmarks-exist` **Benchmark tests exist for critical operations**: Performance-critical code should have micro-benchmarks.
  * Collector(s): Scan for benchmark test files (language-specific: go test -bench, pytest-benchmark, JMH)
  * Component JSON:
    * `.testing.benchmarks.exist` - Boolean for benchmark presence
    * `.testing.benchmarks.framework` - Benchmarking framework used
    * `.testing.benchmarks.benchmark_count` - Number of benchmarks
  * Policy: Assert that benchmarks exist for performance-critical components
  * Configuration: Tags requiring benchmarks (e.g., ["performance-critical", "core-library"])
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-benchmarks-tracked` **Benchmark results are tracked over time**: Benchmark results should be stored for regression detection.
  * Collector(s): Check for benchmark result storage and tracking configuration
  * Component JSON:
    * `.testing.benchmarks.tracked` - Boolean for tracking enabled
    * `.testing.benchmarks.history_url` - URL to benchmark history
  * Policy: Assert that benchmark results are tracked
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-no-benchmark-regressions` **No performance regressions in benchmarks**: Benchmark results should not show significant regressions.
  * Collector(s): Compare current benchmark results with historical baseline
  * Component JSON:
    * `.testing.benchmarks.regression_detected` - Boolean for regression presence
    * `.testing.benchmarks.regressions` - Array of benchmarks with regressions
    * `.testing.benchmarks.regression_percentage` - Worst regression percentage
  * Policy: Assert that no benchmark shows regression beyond threshold
  * Configuration: Maximum allowed regression percentage (default: 10%)
  * Strategy: Strategy 14 (Historical Trend Analysis via Component JSON History) or Strategy 1 (CI Tool Execution Detection)

---

## Test Quality

### Flaky Test Detection

* `test-flaky-tracked` **Flaky tests are tracked**: The system must track and identify flaky tests that have inconsistent results.
  * Collector(s): Analyze test execution history to detect tests with intermittent failures
  * Component JSON:
    * `.testing.flaky_tests.tracking_enabled` - Boolean for flaky test tracking
    * `.testing.flaky_tests.count` - Number of identified flaky tests
    * `.testing.flaky_tests.tests` - Array of flaky test identifiers
  * Policy: Assert that flaky test tracking is enabled
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-flaky-within-limits` **Flaky test count is within limits**: The number of known flaky tests should not exceed acceptable thresholds.
  * Collector(s): Query test tracking system for current flaky test count
  * Component JSON:
    * `.testing.flaky_tests.count` - Number of flaky tests
    * `.testing.flaky_tests.percentage` - Percentage of total tests that are flaky
  * Policy: Assert that flaky test count/percentage is within limits
  * Configuration: Maximum flaky tests (default: 5), maximum flaky percentage (default: 1%)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-no-new-flaky` **No new flaky tests introduced**: PRs should not introduce new flaky tests.
  * Collector(s): Compare flaky test list before and after PR changes
  * Component JSON:
    * `.testing.flaky_tests.new_in_pr` - Array of new flaky tests in PR
    * `.testing.flaky_tests.introduced_count` - Count of new flaky tests
  * Policy: Assert that no new flaky tests are introduced
  * Configuration: None
  * Strategy: Strategy 14 (Historical Trend Analysis via Component JSON History) or Strategy 1 (CI Tool Execution Detection)

* `test-flaky-quarantined` **Flaky tests are quarantined**: Known flaky tests should be quarantined and tracked separately.
  * Collector(s): Check test configuration for quarantine annotations or skip markers
  * Component JSON:
    * `.testing.flaky_tests.quarantined` - Array of quarantined tests
    * `.testing.flaky_tests.quarantine_percentage` - Percentage quarantined vs total flaky
  * Policy: Assert that identified flaky tests are properly quarantined
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### Test Independence

* `test-order-independent` **Tests do not depend on execution order**: Tests should be able to run in any order without failures.
  * Collector(s): Run tests in random order and detect order-dependent failures
  * Component JSON:
    * `.testing.quality.random_order_tested` - Boolean for random order testing
    * `.testing.quality.order_dependent_tests` - Array of tests failing with random order
    * `.testing.quality.is_order_independent` - Boolean for order independence
  * Policy: Assert that tests pass when run in random order
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `test-no-shared-state` **Tests do not share mutable state**: Tests should not rely on or modify shared mutable state.
  * Collector(s): Static analysis for shared state patterns, or detection via parallel test failures
  * Component JSON:
    * `.testing.quality.shared_state_detected` - Boolean for shared state detection
    * `.testing.quality.shared_state_violations` - Array of tests with shared state
  * Policy: Assert that no shared mutable state is detected in tests
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-cleanup` **Tests clean up after themselves**: Tests that create resources should clean them up after execution.
  * Collector(s): Static analysis for cleanup patterns, or runtime detection of resource leaks
  * Component JSON:
    * `.testing.quality.cleanup_verified` - Boolean for cleanup verification
    * `.testing.quality.resource_leaks` - Array of tests with potential resource leaks
  * Policy: Assert that tests properly clean up resources
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Test Assertions

* `test-meaningful-assertions` **Tests have meaningful assertions**: Tests must contain actual assertions, not just run code without verification.
  * Collector(s): Static analysis to detect tests without assertion statements
  * Component JSON:
    * `.testing.quality.tests_without_assertions` - Array of tests missing assertions
    * `.testing.quality.assertion_count` - Total number of assertions
    * `.testing.quality.assertions_per_test` - Average assertions per test
  * Policy: Assert that all tests have at least one assertion
  * Configuration: Minimum assertions per test (default: 1)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-error-path-tested` **Tests verify expected failures**: Error paths should be tested with expected exception assertions.
  * Collector(s): Analyze test code for exception/error testing patterns
  * Component JSON:
    * `.testing.quality.error_tests_exist` - Boolean for error path testing
    * `.testing.quality.error_assertion_count` - Number of error/exception assertions
  * Policy: Assert that error path testing exists
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-no-exception-suppression` **Tests do not suppress exceptions**: Tests should not catch and ignore exceptions that could hide failures.
  * Collector(s): Static analysis to detect try-catch blocks in tests without assertions
  * Component JSON:
    * `.testing.quality.exception_suppression` - Array of tests suppressing exceptions
    * `.testing.quality.has_exception_suppression` - Boolean for suppression presence
  * Policy: Assert that no tests suppress exceptions
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Test Framework and Tool Standards

### Approved Frameworks

* `test-approved-framework` **Tests use approved testing framework**: Tests must use organization-approved testing frameworks.
  * Collector(s): Detect testing framework from configuration files and import statements (language-specific)
  * Component JSON:
    * `.testing.framework` - Primary testing framework detected
    * `.testing.frameworks_used` - Array of all testing frameworks detected
    * `.testing.uses_approved_framework` - Boolean for approved framework usage
  * Policy: Assert that the testing framework is from the approved list
  * Configuration: Approved frameworks per language (e.g., Python: ["pytest"], Go: ["testing"], JS: ["jest", "vitest"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-approved-mocking-library` **Mock/stub library is from approved list**: Mocking libraries should be standardized across the organization.
  * Collector(s): Detect mocking library from imports and configuration
  * Component JSON:
    * `.testing.mocking_library` - Mocking library detected
    * `.testing.uses_approved_mocking` - Boolean for approved library
  * Policy: Assert that mocking library is from approved list
  * Configuration: Approved mocking libraries per language
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-coverage-tool-configured` **Coverage tool is configured correctly**: Coverage collection should use the standard tool with proper configuration.
  * Collector(s): Parse coverage tool configuration files
  * Component JSON:
    * `.testing.coverage.source.tool` - Coverage tool used
    * `.testing.coverage.configuration_valid` - Boolean for valid configuration
    * `.testing.coverage.excludes` - Array of excluded paths
  * Policy: Assert that coverage tool is properly configured
  * Configuration: Required coverage tool settings, mandatory excludes
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### Test Configuration

* `test-config-exists` **Test configuration exists**: A proper test configuration file should exist for the testing framework.
  * Collector(s): Check for test configuration files (pytest.ini, jest.config.js, etc.)
  * Component JSON:
    * `.testing.config_file_exists` - Boolean for configuration presence
    * `.testing.config_file_path` - Path to test configuration
  * Policy: Assert that test configuration file exists
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-timeouts-configured` **Test timeouts are configured**: Global test timeout should be configured to prevent hanging tests.
  * Collector(s): Parse test configuration for timeout settings
  * Component JSON:
    * `.testing.timeout_configured` - Boolean for timeout configuration
    * `.testing.timeout_seconds` - Configured timeout value
  * Policy: Assert that test timeout is configured
  * Configuration: Maximum allowed timeout (default: 60 seconds)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `test-retries-limited` **Test retries are limited**: Automatic test retries should be limited to prevent masking flaky tests.
  * Collector(s): Parse test configuration for retry settings
  * Component JSON:
    * `.testing.retry_configured` - Boolean for retry configuration
    * `.testing.retry_count` - Number of retries configured
  * Policy: Assert that retries are limited to acceptable count
  * Configuration: Maximum allowed retries (default: 2)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Test Data and Mocking

### Test Data Management

* **Tests do not use production data**: Tests must not connect to or use production databases/services.
  * Collector(s): Scan test code for production URLs, credentials, or connection strings
  * Component JSON:
    * `.testing.data.uses_production_data` - Boolean for production data usage
    * `.testing.data.production_references` - Array of production references found
  * Policy: Assert that no production data references exist in tests
  * Configuration: Production URL patterns to detect

* **Test fixtures are properly managed**: Test data fixtures should be in standard locations and formats.
  * Collector(s): Scan for test fixture files and validate organization
  * Component JSON:
    * `.testing.data.fixtures_exist` - Boolean for fixture presence
    * `.testing.data.fixture_paths` - Array of fixture file paths
    * `.testing.data.fixtures_organized` - Boolean for proper organization
  * Policy: Assert that test fixtures are properly organized
  * Configuration: Expected fixture locations

* **Sensitive data is not in test fixtures**: Test fixtures should not contain real PII or sensitive data.
  * Collector(s): Scan test fixtures for PII patterns (SSN, credit card, email patterns)
  * Component JSON:
    * `.testing.data.sensitive_data_detected` - Boolean for sensitive data presence
    * `.testing.data.sensitive_data_locations` - Array of files with sensitive data
  * Policy: Assert that no sensitive data exists in test fixtures
  * Configuration: Sensitive data patterns to detect

* **Test databases are isolated**: Tests using databases should use isolated test databases, not shared instances.
  * Collector(s): Analyze test configuration for database connection settings
  * Component JSON:
    * `.testing.data.database_isolation` - Boolean for database isolation
    * `.testing.data.database_strategy` - Database strategy (in-memory, container, dedicated)
  * Policy: Assert that test databases are properly isolated
  * Configuration: Approved database isolation strategies

### Mocking Standards

* **External services are mocked in unit tests**: Unit tests should mock external service calls, not make real requests.
  * Collector(s): Static analysis to detect unmocked HTTP/gRPC calls in unit tests
  * Component JSON:
    * `.testing.mocking.external_services_mocked` - Boolean for proper mocking
    * `.testing.mocking.unmocked_external_calls` - Array of unmocked external calls
  * Policy: Assert that all external services are mocked in unit tests
  * Configuration: External service patterns to check

* **Mocks verify interactions**: Mocks should verify expected interactions, not just stub responses.
  * Collector(s): Static analysis to detect mock usage patterns
  * Component JSON:
    * `.testing.mocking.verification_used` - Boolean for mock verification
    * `.testing.mocking.verify_calls_percentage` - Percentage of mocks with verification
  * Policy: Assert that mocks include interaction verification
  * Configuration: Minimum verification percentage (default: 50%)

* **No excessive mocking**: Tests should not mock so extensively that they don't test real behavior.
  * Collector(s): Analyze mock-to-assertion ratio in tests
  * Component JSON:
    * `.testing.mocking.mock_count` - Total mocks in test suite
    * `.testing.mocking.mock_per_test_ratio` - Average mocks per test
  * Policy: Assert that mocking is not excessive
  * Configuration: Maximum mocks per test (default: 10)

---

## Security Testing

### Security Test Coverage

* **Security-focused tests exist**: Components handling sensitive data should have security-focused test cases.
  * Collector(s): Scan for security test files or security-tagged tests
  * Component JSON:
    * `.testing.security_tests.exist` - Boolean for security tests presence
    * `.testing.security_tests.test_count` - Number of security tests
    * `.testing.security_tests.categories` - Array of security categories tested
  * Policy: Assert that security tests exist for components tagged as sensitive
  * Configuration: Tags requiring security tests (e.g., ["pci", "pii", "auth"])

* **Authentication tests exist**: Components with authentication should have tests verifying auth behavior.
  * Collector(s): Detect auth-related tests from test names/patterns
  * Component JSON:
    * `.testing.security_tests.auth_tests_exist` - Boolean for auth tests
    * `.testing.security_tests.auth_scenarios_covered` - Array of auth scenarios tested
  * Policy: Assert that authentication tests exist for auth components
  * Configuration: Tags requiring auth tests (e.g., ["auth", "login", "identity"])

* **Authorization tests exist**: Components with authorization should test permission boundaries.
  * Collector(s): Detect authorization-related tests from test names/patterns
  * Component JSON:
    * `.testing.security_tests.authz_tests_exist` - Boolean for authorization tests
    * `.testing.security_tests.authz_scenarios_covered` - Array of authorization scenarios tested
  * Policy: Assert that authorization tests exist for protected resources
  * Configuration: Tags requiring authorization tests

* **Input validation tests exist**: APIs should have tests for input validation and rejection of malformed input.
  * Collector(s): Detect validation-related tests from test names/patterns
  * Component JSON:
    * `.testing.security_tests.validation_tests_exist` - Boolean for validation tests
    * `.testing.security_tests.validation_test_count` - Number of validation tests
  * Policy: Assert that input validation tests exist for API components
  * Configuration: Tags requiring validation tests (e.g., ["api", "service"])

### Security Scanning in Tests

* **SAST runs as part of test pipeline**: Static application security testing should run alongside tests.
  * Collector(s): Check CI configuration for SAST tool execution
  * Component JSON:
    * `.sast` - SAST scan data (presence indicates execution)
    * `.ci.steps_executed.security_scan` - Boolean for security scan step
  * Policy: Assert that SAST is executed in CI
  * Configuration: None

* **Dependency vulnerability scanning runs with tests**: SCA should run as part of the test pipeline.
  * Collector(s): Check CI configuration for SCA tool execution
  * Component JSON:
    * `.sca` - SCA scan data (presence indicates execution)
    * `.ci.steps_executed.dependency_scan` - Boolean for dependency scan step
  * Policy: Assert that dependency scanning is executed in CI
  * Configuration: None

---

## Test Documentation

### Test Documentation Standards

* **Test purpose is documented**: Complex tests should have documentation explaining what they test and why.
  * Collector(s): Parse test files for docstrings, comments, or description annotations
  * Component JSON:
    * `.testing.documentation.tests_with_docs` - Number of tests with documentation
    * `.testing.documentation.documentation_percentage` - Percentage of tests documented
  * Policy: Assert that test documentation meets minimum percentage
  * Configuration: Minimum documentation percentage (default: 50% for complex tests)

* **Test naming is descriptive**: Test names should clearly describe what is being tested and expected outcome.
  * Collector(s): Analyze test names for descriptive patterns (should_, when_, given_)
  * Component JSON:
    * `.testing.documentation.descriptive_names` - Number of descriptively named tests
    * `.testing.documentation.naming_score` - Score for naming quality
  * Policy: Assert that test naming follows descriptive conventions
  * Configuration: Required naming patterns

* **Test README exists**: Test directory should contain documentation on running tests and test organization.
  * Collector(s): Check for README in test directories
  * Component JSON:
    * `.testing.documentation.readme_exists` - Boolean for test README presence
    * `.testing.documentation.readme_path` - Path to test README
  * Policy: Assert that test README exists
  * Configuration: None

---

## Language-Specific Testing Standards

### Go Testing

* **Go tests use table-driven pattern**: Go tests should use table-driven test patterns for comprehensive coverage.
  * Collector(s): Static analysis of Go test files for table-driven patterns
  * Component JSON:
    * `.lang.go.testing.table_driven_tests` - Number of table-driven tests
    * `.lang.go.testing.table_driven_percentage` - Percentage using table-driven pattern
  * Policy: Assert that Go tests predominantly use table-driven patterns
  * Configuration: Minimum table-driven percentage (default: 70%)

* **Go tests use testify or standard assertions**: Go tests should use consistent assertion libraries.
  * Collector(s): Analyze Go test imports for assertion libraries
  * Component JSON:
    * `.lang.go.testing.assertion_library` - Assertion library used (testify, standard)
    * `.lang.go.testing.uses_approved_assertions` - Boolean for approved library
  * Policy: Assert that Go tests use approved assertion library
  * Configuration: Approved Go assertion libraries

* **Go test race detection is enabled in CI**: Go tests should run with race detection enabled.
  * Collector(s): Check CI configuration for -race flag in go test commands
  * Component JSON:
    * `.lang.go.testing.race_detection_enabled` - Boolean for race detection
  * Policy: Assert that race detection is enabled in CI
  * Configuration: None

### Python Testing

* **Python tests use pytest**: Python projects should use pytest as the testing framework.
  * Collector(s): Check for pytest configuration and usage
  * Component JSON:
    * `.lang.python.testing.framework` - Testing framework detected
    * `.lang.python.testing.uses_pytest` - Boolean for pytest usage
  * Policy: Assert that Python tests use pytest
  * Configuration: Allowed Python testing frameworks

* **Python tests use appropriate fixtures**: Pytest fixtures should be properly scoped and organized.
  * Collector(s): Analyze conftest.py files and fixture usage
  * Component JSON:
    * `.lang.python.testing.fixtures_exist` - Boolean for fixture presence
    * `.lang.python.testing.fixture_count` - Number of fixtures defined
    * `.lang.python.testing.conftest_exists` - Boolean for conftest.py presence
  * Policy: Assert that fixtures are properly organized
  * Configuration: None

* **Python tests use type hints**: Test function signatures should include type hints for clarity.
  * Collector(s): Static analysis of Python test files for type annotations
  * Component JSON:
    * `.lang.python.testing.type_hints_percentage` - Percentage of tests with type hints
  * Policy: Assert that test type hint coverage meets minimum
  * Configuration: Minimum type hint percentage (default: 50%)

### JavaScript/TypeScript Testing

* **JS/TS tests use Jest or Vitest**: JavaScript/TypeScript projects should use approved test runners.
  * Collector(s): Check package.json and test configuration for test runner
  * Component JSON:
    * `.lang.javascript.testing.framework` - Testing framework detected
    * `.lang.javascript.testing.uses_approved_framework` - Boolean for approved framework
  * Policy: Assert that JS/TS tests use approved framework
  * Configuration: Approved frameworks (default: ["jest", "vitest"])

* **React components have testing library tests**: React components should be tested with React Testing Library.
  * Collector(s): Check for @testing-library/react usage in test files
  * Component JSON:
    * `.lang.javascript.testing.uses_testing_library` - Boolean for Testing Library usage
    * `.lang.javascript.testing.enzyme_detected` - Boolean for legacy Enzyme usage
  * Policy: Assert that React tests use Testing Library, not Enzyme
  * Configuration: None

* **Snapshot tests are minimized**: Snapshot testing should be limited to avoid brittle tests.
  * Collector(s): Count snapshot assertions in test files
  * Component JSON:
    * `.lang.javascript.testing.snapshot_count` - Number of snapshot assertions
    * `.lang.javascript.testing.snapshot_percentage` - Percentage of tests using snapshots
  * Policy: Assert that snapshot usage is within limits
  * Configuration: Maximum snapshot percentage (default: 20%)

### Java Testing

* **Java tests use JUnit 5**: Java projects should use JUnit 5 (Jupiter) for testing.
  * Collector(s): Check for JUnit 5 dependencies and annotations
  * Component JSON:
    * `.lang.java.testing.framework` - Testing framework detected
    * `.lang.java.testing.junit_version` - JUnit version (4 or 5)
  * Policy: Assert that Java tests use JUnit 5
  * Configuration: Minimum JUnit version required

* **Java tests use AssertJ or Hamcrest**: Java tests should use fluent assertion libraries.
  * Collector(s): Check for assertion library imports
  * Component JSON:
    * `.lang.java.testing.assertion_library` - Assertion library detected
    * `.lang.java.testing.uses_fluent_assertions` - Boolean for fluent assertions
  * Policy: Assert that Java tests use fluent assertion library
  * Configuration: Approved assertion libraries (default: ["assertj", "hamcrest"])

* **Java integration tests use Spring Test or Testcontainers**: Java integration tests should use approved frameworks.
  * Collector(s): Check for integration testing framework dependencies
  * Component JSON:
    * `.lang.java.testing.integration_framework` - Integration test framework
    * `.lang.java.testing.uses_testcontainers` - Boolean for Testcontainers usage
  * Policy: Assert that approved integration testing patterns are used
  * Configuration: Approved integration testing frameworks

---

## Test Quality Patterns (AST-Based)

These guardrails use Strategy 16 (AST-Based Code Pattern Extraction) to detect test quality issues via structural analysis.

### Test Assertions

* `test-has-assertions` **Test functions contain assertions**: Test functions must include assertion statements, not just run code.
  * Collector(s): Use ast-grep to detect test functions without any assertion calls (assert, expect, require, t.Error)
  * Component JSON:
    * `.code_patterns.testing.tests_without_assertions` - Array of test functions missing assertions
    * `.code_patterns.testing.tests_without_assertions_count` - Count of tests without assertions
    * `.code_patterns.testing.all_have_assertions` - Boolean indicating all tests have assertions
  * Policy: Assert that all test functions contain at least one assertion
  * Configuration: Assertion patterns per language
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `test-no-print-assertions` **Tests use assertions not print statements**: Tests must use proper assertions, not print statements to manually verify output.
  * Collector(s): Use ast-grep to detect print/log statements in test functions without accompanying assertions
  * Component JSON:
    * `.code_patterns.testing.print_only_tests` - Array of tests using print instead of assert
    * `.code_patterns.testing.print_only_tests_count` - Count of such tests
  * Policy: Assert that tests use assertions, not print statements
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Error Handling in Tests

* `test-no-empty-catch` **Tests do not have empty catch blocks**: Test catch/except blocks must not be empty, which can hide failures.
  * Collector(s): Use ast-grep to detect empty `catch {}`, `except: pass`, or `catch (e) {}` in test files
  * Component JSON:
    * `.code_patterns.testing.empty_catch_blocks` - Array of empty catch blocks in tests
    * `.code_patterns.testing.empty_catch_count` - Count of empty catch blocks
    * `.code_patterns.testing.no_empty_catches` - Boolean for no empty catches
  * Policy: Assert that no empty catch blocks exist in tests
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `test-errors-checked` **Test error returns are checked**: Tests must check error return values, not ignore them.
  * Collector(s): Use ast-grep to detect ignored error returns in test code (e.g., `result, _ := funcThatReturnsError()`)
  * Component JSON:
    * `.code_patterns.testing.ignored_errors` - Array of ignored errors in tests
    * `.code_patterns.testing.ignored_errors_count` - Count of ignored errors
  * Policy: Assert that test code checks error returns
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Test Structure

* `test-no-sleep-delays` **Tests do not use arbitrary sleep delays**: Tests should use proper synchronization, not sleep delays which cause flakiness.
  * Collector(s): Use ast-grep to detect `time.Sleep()`, `Thread.sleep()`, `asyncio.sleep()` in test files
  * Component JSON:
    * `.code_patterns.testing.sleep_usage` - Array of sleep calls in tests
    * `.code_patterns.testing.sleep_count` - Count of sleep usages
    * `.code_patterns.testing.no_sleeps` - Boolean for no sleep delays
  * Policy: Assert that tests do not use arbitrary sleep delays (may be advisory)
  * Configuration: Allowed sleep patterns (e.g., test utilities)
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `test-no-hardcoded-values` **Tests do not hardcode environment-specific values**: Tests must not contain hardcoded URLs, ports, or paths that vary by environment.
  * Collector(s): Use ast-grep to detect hardcoded localhost URLs, file paths, or port numbers in tests
  * Component JSON:
    * `.code_patterns.testing.hardcoded_values` - Array of hardcoded values in tests
    * `.code_patterns.testing.hardcoded_count` - Count of hardcoded values
  * Policy: Assert that tests use configuration or fixtures, not hardcoded values
  * Configuration: Patterns considered hardcoded
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Mock Usage

* `test-mocks-have-expectations` **Mocks verify expected calls**: Mock objects should verify that expected methods were called.
  * Collector(s): Use ast-grep to detect mock creation without corresponding verification (e.g., `mock.Mock()` without `mock.assert_called`)
  * Component JSON:
    * `.code_patterns.testing.unverified_mocks` - Array of mocks without verification
    * `.code_patterns.testing.unverified_mocks_count` - Count of unverified mocks
  * Policy: Assert that mocks include call verification (may be advisory)
  * Configuration: Mock patterns per language
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `test-no-production-dependencies` **Tests do not import production secrets or configs**: Test code must not import production configuration modules.
  * Collector(s): Use ast-grep to detect imports of production config modules in test files
  * Component JSON:
    * `.code_patterns.testing.production_imports` - Array of production imports in tests
    * `.code_patterns.testing.production_imports_count` - Count of such imports
  * Policy: Assert that tests do not import production configuration
  * Configuration: Production module patterns to detect
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

---

## Summary Policies

* **All required test types exist**: Aggregate check that all required test types (unit, integration, etc.) are present.
  * Collector(s): Aggregate test type existence checks
  * Component JSON:
    * `.testing.unit_tests.exist` - Unit tests present
    * `.testing.integration_tests.exist` - Integration tests present
    * `.testing.e2e_tests.exist` - E2E tests present (if required)
    * `.testing.all_required_types_present` - Boolean for all required types
  * Policy: Assert that all required test types exist based on component tags
  * Configuration: Required test types per component tag

* **Test suite health score**: Aggregate score reflecting overall test suite quality.
  * Collector(s): Calculate composite score from coverage, flaky tests, execution time, etc.
  * Component JSON:
    * `.testing.health_score` - Numeric score (0-100)
    * `.testing.health_factors` - Array of contributing factors
  * Policy: Assert that test suite health score meets minimum threshold
  * Configuration: Minimum health score (default: 70), factor weights

* **Testing compliance is complete**: Meta-check that all applicable testing guardrails pass.
  * Collector(s): Aggregate results from all testing-related policy checks
  * Component JSON:
    * `.testing.compliance.passing_checks` - Number of passing checks
    * `.testing.compliance.total_checks` - Total applicable checks
    * `.testing.compliance.percentage` - Compliance percentage
  * Policy: Assert that testing compliance percentage meets threshold
  * Configuration: Minimum compliance percentage (default: 90%)
