# Phase 1A Configuration and Organization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first independently usable Phase 1 slice: configuration dictionaries, effective-dated organization tree, legal-entity relationships, organization leaders/BP scopes, cost allocation, revenue targets, and their PC administrator pages.

**Architecture:** Extend the existing FastAPI modular monolith without copying the legacy EHR schema. Keep SQLAlchemy persistence models explicit, move business decisions into focused application services, enforce date/version invariants in both PostgreSQL and services, and expose only `/api/v1` administrator APIs. The React/Ant Design administrator shell gains real configuration and organization workspaces while retaining the existing login/session flow.

**Tech Stack:** Python 3.13.14, FastAPI 0.118.0, Pydantic 2.10.3, SQLAlchemy 2.0.36, Alembic 1.14.0, PostgreSQL 16.14, Redis 7.4.10, React 19.2.0, TypeScript 5.9.3, Ant Design 6.5.2, Vitest 3.2.7.

## Global Constraints

- `coreHR` is a greenfield product; legacy EHR tables are research references only.
- PostgreSQL remains the only Phase 1–4 business fact store.
- All business APIs are under `/api/v1`; unknown permissions and unknown data scopes deny access.
- Effective dates use half-open periods: `effective_from` inclusive and `effective_to` inclusive at the API boundary, converted to `[from, to + 1 day)` for database overlap checks.
- Business facts are never physically deleted after publication; cancel or close them with audit history.
- All high-risk writes require `change_reason`, actor, Trace ID, expected version, and an idempotency key.
- Real employee values and credentials never enter source, tests, logs, fixtures, OpenAPI examples, or frontend artifacts.
- Preserve unrelated dirty-worktree changes; stage and commit only files named by the active task.
- Each task must leave backend tests, frontend tests, migration checks, and formatting checks no worse than before.

---

## File Map

### Backend files to create

- `apps/api/src/hris/core/concurrency.py`: request version and idempotency primitives.
- `apps/api/src/hris/modules/platform/configuration_schemas.py`: dictionary contracts.
- `apps/api/src/hris/modules/platform/configuration_service.py`: dictionary use cases.
- `apps/api/src/hris/modules/platform/configuration_api.py`: configuration routes.
- `apps/api/src/hris/modules/platform/governance_models.py`: minimal transactional outbox entity used by Phase 1A writes.
- `apps/api/src/hris/modules/workforce/organization_models.py`: organization event, leader, BP membership, and BP scope entities.
- `apps/api/src/hris/modules/workforce/organization_schemas.py`: organization and relation contracts.
- `apps/api/src/hris/modules/workforce/organization_policy.py`: pure date/tree/allocation/target rules.
- `apps/api/src/hris/modules/workforce/organization_service.py`: organization use cases.
- `apps/api/src/hris/modules/workforce/organization_api.py`: organization administrator routes.
- `apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py`: Phase 1A schema migration.
- `apps/api/tests/test_organization_policy.py`: pure rule tests.
- `apps/api/tests/test_configuration_schemas.py`: configuration contract tests.
- `apps/api/tests/integration/conftest.py`: isolated PostgreSQL integration fixtures.
- `apps/api/tests/integration/test_configuration_api.py`: dictionary API tests.
- `apps/api/tests/integration/test_organization_api.py`: organization API tests.
- `apps/api/tests/integration/test_organization_relations_api.py`: legal, leader, and BP tests.
- `apps/api/tests/integration/test_financial_dimensions_api.py`: cost and revenue tests.

### Backend files to modify

- `apps/api/src/hris/core/config.py`: integration-test and business-time configuration.
- `apps/api/src/hris/api/business_router.py`: register new `/api/v1` routers.
- `apps/api/src/hris/modules/platform/models.py`: add active-reference protection metadata if required.
- `apps/api/src/hris/modules/workforce/models.py`: add cost-center effective dates, revenue month relationship, and optimistic versions.
- `apps/api/src/hris/shared/db/business_models.py`: register all new models.
- `apps/api/tests/test_metadata.py`: assert new tables and non-JSON monthly target model.

### Frontend files to create

- `apps/web/src/business/AppShell.tsx`: authenticated shell and workspace selection.
- `apps/web/src/business/navigation.ts`: typed navigation keys.
- `apps/web/src/business/components/EffectiveDatePicker.tsx`: shared current/as-of control.
- `apps/web/src/business/features/configuration/DictionaryWorkspace.tsx`: dictionary list/editor.
- `apps/web/src/business/features/organization/OrganizationWorkspace.tsx`: tree and detail workspace.
- `apps/web/src/business/features/organization/OrganizationTree.tsx`: effective-dated tree.
- `apps/web/src/business/features/organization/OrganizationVersionDrawer.tsx`: create future version.
- `apps/web/src/business/features/organization/OrganizationRelationsTabs.tsx`: legal entity, leader, BP, cost, and revenue tabs.
- `apps/web/src/business/features/organization/api.ts`: typed Phase 1A client.
- `apps/web/src/business/features/organization/types.ts`: API contracts.
- `apps/web/src/business/features/organization/OrganizationWorkspace.test.tsx`: workspace behavior tests.
- `apps/web/src/business/features/configuration/DictionaryWorkspace.test.tsx`: dictionary behavior tests.

### Frontend files to modify

- `apps/web/src/business/BusinessApp.tsx`: delegate authenticated UI to `AppShell`.
- `apps/web/src/business/client.ts`: add reusable JSON request and conflict handling.
- `apps/web/src/business/business.css`: organization workspace layout.

---

### Task 1: Freeze the Current Business Migration Head

**Files:**
- Modify: `apps/api/src/hris/modules/platform/models.py`
- Modify: `apps/api/src/hris/modules/workforce/models.py`
- Modify: `apps/api/src/hris/shared/db/business_models.py`
- Modify: `apps/api/src/hris/shared/db/models.py`
- Modify: `apps/api/tests/test_metadata.py`
- Include: `apps/api/alembic/versions/e7b3d9a4c2f1_ehr_source_integration_models.py`
- Include: `docs/adr/ADR-0002-ehr-source-migration-boundary.md`
- Include: `docs/adr/README.md`
- Include: `docs/migration/ehr-corehr-assembly-plan.md`
- Include: `docs/migration/ehr-source-table-disposition.md`

**Interfaces:**
- Consumes: current migration revision `c91a7d225b60`.
- Produces: committed migration head `e7b3d9a4c2f1` and registered tables `data_dictionaries`, `data_dictionary_items`, `external_record_links`, `person_labels`.

- [ ] **Step 1: Verify the current metadata tests cover all four new tables**

```python
def test_ehr_integration_tables_are_registered() -> None:
    assert {
        "data_dictionaries",
        "data_dictionary_items",
        "external_record_links",
        "person_labels",
    } <= set(Base.metadata.tables)
```

- [ ] **Step 2: Run the focused tests**

Run: `docker run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src corehr-api pytest -q tests/test_metadata.py`

Expected: all metadata tests pass.

- [ ] **Step 3: Validate upgrade, downgrade, and metadata parity on an isolated database**

Run in order:

```powershell
docker compose -f deploy/compose.yaml exec -T db createdb -U corehr corehr_phase1a_migration_test
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_migration_test api alembic -c alembic-business.ini upgrade head
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_migration_test api alembic -c alembic-business.ini downgrade c91a7d225b60
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_migration_test api alembic -c alembic-business.ini upgrade head
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_migration_test api alembic -c alembic-business.ini check
docker compose -f deploy/compose.yaml exec -T db dropdb -U corehr corehr_phase1a_migration_test
```

Expected: upgrade/downgrade/re-upgrade pass; `alembic check` prints `No new upgrade operations detected.`

- [ ] **Step 4: Commit only the EHR integration baseline**

```powershell
git add -- apps/api/src/hris/modules/platform/models.py apps/api/src/hris/modules/workforce/models.py apps/api/src/hris/shared/db/business_models.py apps/api/src/hris/shared/db/models.py apps/api/tests/test_metadata.py apps/api/alembic/versions/e7b3d9a4c2f1_ehr_source_integration_models.py docs/adr/ADR-0002-ehr-source-migration-boundary.md docs/adr/README.md docs/migration/ehr-corehr-assembly-plan.md docs/migration/ehr-source-table-disposition.md
git commit -m "feat: add normalized EHR source integration boundary"
```

### Task 2: Add Real PostgreSQL Integration Test Fixtures

**Files:**
- Create: `apps/api/tests/integration/__init__.py`
- Create: `apps/api/tests/integration/conftest.py`
- Create: `apps/api/tests/integration/test_fixture_isolation.py`
- Modify: `apps/api/pyproject.toml`

**Interfaces:**
- Consumes: environment variable `TEST_DATABASE_URL`.
- Produces: fixtures `db_session: AsyncSession`, `business_client: AsyncClient`, `admin_token: str`, and `restricted_token: str`.

- [ ] **Step 1: Write a failing database isolation test**

```python
@pytest.mark.asyncio
async def test_database_fixture_rolls_back(db_session: AsyncSession) -> None:
    marker = OrganizationType(code="TEST_ONLY", name="测试", sort_order=0)
    db_session.add(marker)
    await db_session.flush()
    assert marker.id is not None
```

- [ ] **Step 2: Run the test without `TEST_DATABASE_URL`**

Run: `docker run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src corehr-api pytest -q tests/integration/test_fixture_isolation.py`

Expected: the test skips with the exact reason `TEST_DATABASE_URL is not configured`; it must never fall back to the development database.

- [ ] **Step 3: Implement transaction-scoped fixtures**

```python
@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
```

Override `get_db` so API tests use this session. Seed one wildcard administrator and one `ORGANIZATION_VIEW`-only role with synthetic identities.

- [ ] **Step 4: Create and migrate the isolated test database**

Run in order:

```powershell
docker compose -f deploy/compose.yaml exec -T db createdb -U corehr corehr_phase1a_test
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_test api alembic -c alembic-business.ini upgrade head
```

- [ ] **Step 5: Run fixture isolation twice**

Run these as two separate commands:

```powershell
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e TEST_DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_test api pytest -q tests/integration/test_fixture_isolation.py
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e TEST_DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_test api pytest -q tests/integration/test_fixture_isolation.py
```

Expected: both runs pass and the second run sees no row from the first.

- [ ] **Step 6: Commit the integration harness**

```powershell
git add -- apps/api/tests/integration apps/api/pyproject.toml
git commit -m "test: add isolated PostgreSQL integration harness"
```

### Task 3: Configuration Dictionary Administration

**Files:**
- Create: `apps/api/src/hris/modules/platform/configuration_schemas.py`
- Create: `apps/api/src/hris/modules/platform/configuration_service.py`
- Create: `apps/api/src/hris/modules/platform/configuration_api.py`
- Create: `apps/api/tests/test_configuration_schemas.py`
- Create: `apps/api/tests/integration/test_configuration_api.py`
- Modify: `apps/api/src/hris/api/business_router.py`

**Interfaces:**
- Consumes: `DataDictionary`, `DataDictionaryItem`, `require_permission`.
- Produces: `ConfigurationService.create_dictionary`, `create_item`, `update_item`, `deactivate_item`, `list_dictionaries`; routes under `/api/v1/configuration/dictionaries`.

- [ ] **Step 1: Write schema tests for stable codes and parent rules**

```python
def test_dictionary_code_is_stable_upper_snake_case() -> None:
    with pytest.raises(ValidationError):
        DictionaryCreate(code="employee type", name="人员类型")


def test_dictionary_item_requires_nonempty_name() -> None:
    with pytest.raises(ValidationError):
        DictionaryItemCreate(code="FORMAL", name="")
```

- [ ] **Step 2: Run the schema tests and observe failure**

Run: `docker run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src corehr-api pytest -q tests/test_configuration_schemas.py`

Expected: import failure because the new schemas do not exist.

- [ ] **Step 3: Implement exact request contracts**

```python
class DictionaryCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    english_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class DictionaryItemCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{0,99}$")
    name: str = Field(min_length=1, max_length=200)
    parent_item_id: UUID | None = None
    sort_order: int = Field(default=0, ge=0)
```

- [ ] **Step 4: Write API tests for create, duplicate, deactivate, and referenced deletion refusal**

Assert exact error codes: `DICTIONARY_CODE_CONFLICT`, `DICTIONARY_ITEM_CODE_CONFLICT`, `DICTIONARY_ITEM_PARENT_INVALID`, `DICTIONARY_ITEM_IN_USE`.

- [ ] **Step 5: Implement service and routes**

Implement these exact asynchronous methods on `ConfigurationService`:

- `create_dictionary(payload: DictionaryCreate) -> DataDictionary`
- `create_item(dictionary_id: UUID, payload: DictionaryItemCreate) -> DataDictionaryItem`
- `update_item(item_id: UUID, payload: DictionaryItemUpdate) -> DataDictionaryItem`
- `deactivate_item(item_id: UUID, reason: str) -> DataDictionaryItem`
- `list_dictionaries(limit: int, offset: int) -> tuple[list[DataDictionary], int]`

Use permissions `CONFIGURATION_VIEW` and `CONFIGURATION_ADMIN`; never expose physical delete.

- [ ] **Step 6: Run unit and integration tests**

Run: `docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e TEST_DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_test api pytest -q tests/test_configuration_schemas.py tests/integration/test_configuration_api.py`

Expected: all tests pass.

- [ ] **Step 7: Commit configuration administration**

```powershell
git add -- apps/api/src/hris/modules/platform/configuration_schemas.py apps/api/src/hris/modules/platform/configuration_service.py apps/api/src/hris/modules/platform/configuration_api.py apps/api/src/hris/api/business_router.py apps/api/tests/test_configuration_schemas.py apps/api/tests/integration/test_configuration_api.py
git commit -m "feat: add configuration dictionary administration"
```

### Task 4: Effective-Dated Organization Domain and Migration

**Files:**
- Create: `apps/api/src/hris/core/concurrency.py`
- Create: `apps/api/src/hris/modules/workforce/organization_models.py`
- Create: `apps/api/src/hris/modules/workforce/organization_policy.py`
- Create: `apps/api/src/hris/modules/workforce/organization_schemas.py`
- Create: `apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py`
- Create: `apps/api/tests/test_organization_policy.py`
- Modify: `apps/api/src/hris/modules/workforce/models.py`
- Modify: `apps/api/src/hris/shared/db/business_models.py`
- Modify: `apps/api/tests/test_metadata.py`

**Interfaces:**
- Consumes: migration head `e7b3d9a4c2f1`.
- Produces: `OrganizationEvent`, `OrganizationLeader`, `PersonBpMembership`, `BpServiceScope`, `RevenueTargetMonth`, `OutboxEvent`, `VersionCommand`, `assert_no_cycle`, `assert_allocation_total`, `assert_revenue_total`.

- [ ] **Step 1: Write failing pure policy tests**

```python
def test_cycle_is_rejected() -> None:
    parents = {"BG": "GROUP", "BU": "BG", "GROUP": None}
    with pytest.raises(DomainViolation, match="ORGANIZATION_CYCLE"):
        assert_no_cycle("GROUP", "BU", parents)


def test_cost_allocation_requires_exactly_one_hundred_percent() -> None:
    with pytest.raises(DomainViolation, match="ALLOCATION_TOTAL_INVALID"):
        assert_allocation_total([Decimal("60"), Decimal("39.9999")])


def test_monthly_revenue_must_equal_annual_revenue() -> None:
    with pytest.raises(DomainViolation, match="REVENUE_MONTH_TOTAL_INVALID"):
        assert_revenue_total(Decimal("120"), [Decimal("9")] * 12)
```

- [ ] **Step 2: Implement pure policies with Decimal quantization**

Use `Decimal("0.0001")` for allocation and currency amounts; reject any monthly target list whose months are not exactly integers 1 through 12.

- [ ] **Step 3: Add schema tests for expected version and idempotency key**

```python
class VersionCommand(BaseModel):
    expected_version: int = Field(ge=1)
    idempotency_key: UUID
    change_reason: str = Field(min_length=1, max_length=500)
```

- [ ] **Step 4: Implement the new persistence models**

`OrganizationEvent` fields: `organization_id`, `event_type`, `effective_date`, `status`, `payload`, `expected_version`, `idempotency_key`, `change_reason`, `applied_at`, `cancelled_at`.

`OrganizationLeader` fields: `organization_id`, `person_id`, `effective_from`, `effective_to`, `version`, `status`.

`PersonBpMembership` fields: `person_id`, `bp_type`, `effective_from`, `effective_to`, `version`, `status`.

`BpServiceScope` fields: `membership_id`, `organization_id`, `effective_from`, `effective_to`.

`RevenueTargetMonth` fields: `revenue_target_id`, `month`, `amount`; unique `(revenue_target_id, month)` and check `month BETWEEN 1 AND 12`.

`OutboxEvent` fields: `event_type`, `aggregate_type`, `aggregate_id`, `payload`, `occurred_at`, `published_at`, `attempt_count`; payload contains identifiers and version metadata only, never sensitive person values.

- [ ] **Step 5: Write the Alembic migration**

The migration must:

1. create `btree_gist`;
2. create the four organization relation/event tables, `revenue_target_months`, and `outbox_events`;
3. add `effective_from`, `effective_to`, and `version` to `cost_centers`;
4. migrate existing `revenue_targets.monthly_amounts` arrays using `jsonb_array_elements_text(revenue_targets.monthly_amounts) WITH ORDINALITY AS month_value(amount, month)`;
5. drop `revenue_targets.monthly_amounts` only after the copy succeeds;
6. add exclusion constraints for organization versions, leader duplicates, and BP membership periods;
7. seed `ORG_NUMBER` plus `CONFIGURATION_VIEW`, `CONFIGURATION_ADMIN`, `ORGANIZATION_VIEW`, `ORGANIZATION_ADMIN`, and `ORGANIZATION_EVENT_APPLY`;
8. provide a downgrade that reconstructs the monthly JSON in month order before dropping normalized rows.

- [ ] **Step 6: Run policy, metadata, and migration tests**

Run: `docker run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src corehr-api pytest -q tests/test_organization_policy.py tests/test_metadata.py`

Then run the exact isolated migration sequence:

```powershell
docker compose -f deploy/compose.yaml exec -T db createdb -U corehr corehr_phase1a_org_migration_test
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_org_migration_test api alembic -c alembic-business.ini upgrade head
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_org_migration_test api alembic -c alembic-business.ini downgrade e7b3d9a4c2f1
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_org_migration_test api alembic -c alembic-business.ini upgrade head
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_org_migration_test api alembic -c alembic-business.ini check
docker compose -f deploy/compose.yaml exec -T db dropdb -U corehr corehr_phase1a_org_migration_test
```

Upgrade the persistent integration database afterward:

```powershell
docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_test api alembic -c alembic-business.ini upgrade head
```

Expected: all tests pass and no metadata operations remain.

- [ ] **Step 7: Commit the organization domain schema**

```powershell
git add -- apps/api/src/hris/core/concurrency.py apps/api/src/hris/modules/platform/governance_models.py apps/api/src/hris/modules/workforce/organization_models.py apps/api/src/hris/modules/workforce/organization_policy.py apps/api/src/hris/modules/workforce/organization_schemas.py apps/api/src/hris/modules/workforce/models.py apps/api/src/hris/shared/db/business_models.py apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py apps/api/tests/test_organization_policy.py apps/api/tests/test_metadata.py
git commit -m "feat: add effective-dated organization domain"
```

### Task 5: Current Organization Tree and Effective-Dated Detail APIs

**Files:**
- Create: `apps/api/src/hris/modules/workforce/organization_service.py`
- Create: `apps/api/src/hris/modules/workforce/organization_api.py`
- Create: `apps/api/tests/integration/test_organization_api.py`
- Modify: `apps/api/src/hris/api/business_router.py`

**Interfaces:**
- Consumes: `Organization`, `OrganizationVersion`, `OrganizationEvent`, `VersionCommand`, `assert_no_cycle`.
- Produces: `OrganizationService.create_type`, `list_types`, `update_type`, `create`, `schedule_version`, `cancel_event`, `apply_due_events`, `get_current_tree`, `get_as_of`; routes under `/api/v1/organization-types` and `/api/v1/organizations`.

- [ ] **Step 1: Write API tests for the current tree and future detail version**

Create configurable Group/BG/BU/Department types and synthetic Group → BG → BU records, schedule BU to move under another BG tomorrow, and assert:

```python
assert current_tree.parent_of("BU001") == "BG001"
assert future_detail.parent_organization_code == "BG002"
```

Assert organization-type codes are stable, duplicate codes return `409 ORGANIZATION_TYPE_CODE_CONFLICT`, and an in-use type can be deactivated only for future creation—not physically deleted. The tree endpoint must not accept a future `effective_at`; future structure appears only in the organization detail event/version response. Also assert cycle attempts return `409 ORGANIZATION_CYCLE` and stale versions return `409 VERSION_CONFLICT`.

- [ ] **Step 2: Implement the service under per-organization advisory locks**

Implement these exact asynchronous methods on `OrganizationService`:

- `create_type(payload: OrganizationTypeCreate) -> OrganizationTypeView`
- `list_types(active_only: bool) -> list[OrganizationTypeView]`
- `update_type(type_id: UUID, payload: OrganizationTypeUpdate) -> OrganizationTypeView`
- `create(payload: OrganizationCreate, command: VersionCommand) -> OrganizationView`
- `schedule_version(organization_id: UUID, payload: OrganizationVersionCreate, command: VersionCommand) -> OrganizationEventView`
- `cancel_event(event_id: UUID, command: VersionCommand) -> OrganizationEventView`
- `apply_due_events(business_date: date) -> int`
- `get_current_tree() -> list[OrganizationTreeNode]`
- `get_as_of(organization_id: UUID, effective_at: date) -> OrganizationView`

`create` obtains a six-digit organization code from `NumberingService.reserve("ORG_NUMBER")`; clients cannot choose codes during normal creation. A separate import command can preserve historical codes in P1-D.

Use `pg_advisory_xact_lock` derived from the organization UUID before reading the expected version and writing the next version.

- [ ] **Step 3: Expose explicit action routes**

```text
POST   /api/v1/organization-types
GET    /api/v1/organization-types
PATCH  /api/v1/organization-types/{id}
POST   /api/v1/organizations
GET    /api/v1/organizations/tree
GET    /api/v1/organizations/{id}?effective_at=YYYY-MM-DD
POST   /api/v1/organizations/{id}/versions
POST   /api/v1/organization-events/{id}/cancel
POST   /api/v1/organization-events/apply-due
```

Permissions: `ORGANIZATION_VIEW`, `ORGANIZATION_ADMIN`, `ORGANIZATION_EVENT_APPLY`.

- [ ] **Step 4: Run integration tests**

Run: `docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e TEST_DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_test api pytest -q tests/integration/test_organization_api.py`

Expected: current tree, future detail, historical detail, cycle, idempotency, permission, and version-conflict cases pass.

- [ ] **Step 5: Commit organization operations**

```powershell
git add -- apps/api/src/hris/modules/workforce/organization_service.py apps/api/src/hris/modules/workforce/organization_api.py apps/api/src/hris/api/business_router.py apps/api/tests/integration/test_organization_api.py
git commit -m "feat: add effective-dated organization operations"
```

### Task 6: Legal Entities, Leaders, and BP Service Scopes

**Files:**
- Modify: `apps/api/src/hris/modules/workforce/organization_schemas.py`
- Modify: `apps/api/src/hris/modules/workforce/organization_service.py`
- Modify: `apps/api/src/hris/modules/workforce/organization_api.py`
- Create: `apps/api/tests/integration/test_organization_relations_api.py`

**Interfaces:**
- Consumes: legal entities, organization versions, persons, leader and BP models.
- Produces: versioned legal-entity links, up to three leaders, one BP type per person per period, multiple BP service scopes.

- [ ] **Step 1: Write failing relation tests**

Cover:

- one BU linked to two legal entities;
- one legal entity linked to two organizations;
- the fourth overlapping organization leader rejected with `LEADER_LIMIT_EXCEEDED`;
- the same person serving ten organizations under HRBP accepted;
- overlapping EBP membership for that HRBP rejected with `BP_TYPE_OVERLAP`;
- multiple dotted service scopes do not alter the primary organization.

- [ ] **Step 2: Add request contracts**

```python
class OrganizationLegalEntitySet(BaseModel):
    legal_entity_ids: list[UUID] = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None
    command: VersionCommand


class OrganizationLeaderSet(BaseModel):
    person_ids: list[UUID] = Field(min_length=1, max_length=3)
    effective_from: date
    effective_to: date | None = None
    command: VersionCommand


class BpMembershipCreate(BaseModel):
    person_id: UUID
    bp_type: Literal["HRBP", "EBP", "TBP", "FBP"]
    organization_ids: list[UUID] = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None
    command: VersionCommand
```

- [ ] **Step 3: Implement atomic replace-by-version operations**

Each operation locks its aggregate, closes the prior version at `new_from - 1 day`, inserts the new relation set, audits before/after IDs, and writes one outbox event.

- [ ] **Step 4: Expose relation routes**

```text
PUT /api/v1/organizations/{id}/legal-entities
PUT /api/v1/organizations/{id}/leaders
POST /api/v1/bp-memberships
PUT /api/v1/bp-memberships/{id}/service-scopes
GET /api/v1/organizations/{id}/relations?effective_at=YYYY-MM-DD
```

- [ ] **Step 5: Run relation integration tests and commit**

Run: `docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e TEST_DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_test api pytest -q tests/integration/test_organization_relations_api.py`

```powershell
git add -- apps/api/src/hris/modules/workforce/organization_schemas.py apps/api/src/hris/modules/workforce/organization_service.py apps/api/src/hris/modules/workforce/organization_api.py apps/api/tests/integration/test_organization_relations_api.py
git commit -m "feat: add organization legal leader and BP relations"
```

### Task 7: Cost Allocation and Revenue Targets

**Files:**
- Modify: `apps/api/src/hris/modules/workforce/organization_schemas.py`
- Modify: `apps/api/src/hris/modules/workforce/organization_service.py`
- Modify: `apps/api/src/hris/modules/workforce/organization_api.py`
- Create: `apps/api/tests/integration/test_financial_dimensions_api.py`

**Interfaces:**
- Consumes: `CostCenter`, `OrganizationCostAllocation`, `RevenueTarget`, `RevenueTargetMonth`.
- Produces: versioned cost allocation sets and currency-specific annual/monthly target views.

- [ ] **Step 1: Write failing cost-allocation tests**

Assert 60/40 succeeds, 60/39.9999 fails, a future 70/30 version leaves the current view unchanged, and the as-of view changes on the effective date.

- [ ] **Step 2: Write failing revenue tests**

Assert exactly 12 unique months are required, their sum equals the annual amount, and parent aggregation keeps CNY and USD totals separate.

- [ ] **Step 3: Implement aggregate commands**

```python
class CostAllocationSet(BaseModel):
    effective_from: date
    effective_to: date | None = None
    lines: list[CostAllocationLine] = Field(min_length=1)
    command: VersionCommand


class RevenueTargetSet(BaseModel):
    year: int = Field(ge=2000, le=2200)
    currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    annual_amount: Decimal = Field(ge=0, decimal_places=4)
    months: list[RevenueTargetMonthInput] = Field(min_length=12, max_length=12)
    command: VersionCommand
```

Service methods: `set_cost_allocation`, `set_revenue_target`, `get_cost_allocation_as_of`, `get_revenue_targets`, `aggregate_revenue_tree`.

- [ ] **Step 4: Expose financial-dimension routes**

```text
POST /api/v1/cost-centers
GET  /api/v1/cost-centers
PUT  /api/v1/organizations/{id}/cost-allocation
GET  /api/v1/organizations/{id}/cost-allocation?effective_at=YYYY-MM-DD
PUT  /api/v1/organizations/{id}/revenue-targets/{year}/{currency}
GET  /api/v1/organizations/{id}/revenue-targets?year=YYYY&include_descendants=true
```

- [ ] **Step 5: Run tests and commit**

Run: `docker compose -f deploy/compose.yaml run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e TEST_DATABASE_URL=postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr_phase1a_test api pytest -q tests/test_organization_policy.py tests/integration/test_financial_dimensions_api.py`

```powershell
git add -- apps/api/src/hris/modules/workforce/organization_schemas.py apps/api/src/hris/modules/workforce/organization_service.py apps/api/src/hris/modules/workforce/organization_api.py apps/api/tests/integration/test_financial_dimensions_api.py
git commit -m "feat: add cost allocation and revenue targets"
```

### Task 8: Replace the Construction Dashboard with Phase 1A Workspaces

**Files:**
- Create all frontend files listed under “Frontend files to create”.
- Modify: `apps/web/src/business/BusinessApp.tsx`
- Modify: `apps/web/src/business/client.ts`
- Modify: `apps/web/src/business/business.css`

**Interfaces:**
- Consumes: Phase 1A `/api/v1` endpoints and current login token storage.
- Produces: navigable configuration and organization administration workspaces.

- [ ] **Step 1: Write failing shell and navigation tests**

```tsx
it("opens the organization workspace from the administrator menu", async () => {
  render(<BusinessApp />)
  await userEvent.click(screen.getByText("组织中心"))
  expect(await screen.findByRole("heading", { name: "组织中心" })).toBeInTheDocument()
})
```

Mock only the HTTP boundary; use synthetic organization codes and names.

- [ ] **Step 2: Extract `AppShell` and typed navigation**

```ts
export type WorkspaceKey =
  | "dashboard"
  | "configuration"
  | "organization"
  | "people"
  | "headcount"
  | "recruitment"
  | "governance"
```

The selected workspace is mirrored in `window.location.hash` so browser refresh and back/forward preserve location without adding a router dependency.

- [ ] **Step 3: Implement `DictionaryWorkspace`**

Provide dictionary search, item tree, create/edit drawer, deactivate confirmation, loading state, empty state, permission-denied state, and version-conflict refresh.

- [ ] **Step 4: Implement organization tree and details**

`OrganizationWorkspace` contains a left current-effective tree and right detail tabs. The effective-date control affects only the selected organization detail. Future planned versions appear in a separate “未来变更” tab and never redraw the entire tree.

The tree supports keyboard navigation, every form control has a visible label, validation errors are announced, and color is never the only status indicator.

- [ ] **Step 5: Implement relation and financial tabs**

Use editable Ant Design tables for legal entities, leaders, BP scopes, cost allocation, and 12 revenue months. Disable submit until allocation equals exactly 100% or revenue months equal the annual total.

- [ ] **Step 6: Run frontend tests and production build**

Run:

```powershell
docker compose -f deploy/compose.yaml run --rm web npm run test:run
docker compose -f deploy/compose.yaml run --rm web npm run build
```

Expected: all tests pass and both `index.html` and `business.html` build.

- [ ] **Step 7: Commit Phase 1A frontend**

```powershell
git add -- apps/web/src/business/BusinessApp.tsx apps/web/src/business/client.ts apps/web/src/business/business.css apps/web/src/business/AppShell.tsx apps/web/src/business/navigation.ts apps/web/src/business/components apps/web/src/business/features/configuration apps/web/src/business/features/organization
git commit -m "feat: add configuration and organization workspaces"
```

### Task 9: Phase 1A End-to-End Gate and Delivery Evidence

**Files:**
- Create: `apps/api/tests/integration/test_phase_1a_journey.py`
- Create: `docs/delivery/P1-A.md`
- Modify: `docs/implementation/phase-1-3-plan.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: all Phase 1A backend and frontend deliverables.
- Produces: repeatable organization initialization, future move, 60/40→70/30 cost allocation, and revenue aggregation evidence.

- [ ] **Step 1: Write the Phase 1A journey**

The test must:

1. create organization types Group/BG/BU/Department;
2. create Group → BG1 → BU and BG2;
3. associate BU with two legal entities;
4. set three leaders and reject a fourth;
5. create one HRBP membership serving BG1 and BU;
6. set current cost allocation to 60/40;
7. schedule 70/30 for tomorrow;
8. schedule BU to move from BG1 to BG2 tomorrow;
9. verify the current tree remains unchanged while tomorrow's organization detail shows the planned parent and allocation;
10. set 12 monthly CNY targets and verify parent aggregation;
11. verify every write has an audit record and stable Trace ID.

- [ ] **Step 2: Run the full backend gate**

Run: `docker run --rm -v "${PWD}/apps/api:/work" -w /work -e PYTHONPATH=/work/src corehr-api sh -c "python -m compileall -q src && pytest -q"`

Expected: all backend tests pass.

- [ ] **Step 3: Run migration parity and frontend gate**

Run Alembic upgrade/downgrade/re-upgrade/check on an isolated database, then `npm run test:run` and `npm run build` in the web container.

- [ ] **Step 4: Perform browser verification**

Verify login, dictionary maintenance, organization-type maintenance, current tree, future version in organization detail, relation tabs, cost validation, revenue validation, permission denial, keyboard navigation, and logout. Save screenshots only under `artifacts/p1-a/`; screenshots must contain synthetic data.

- [ ] **Step 5: Write delivery evidence**

`docs/delivery/P1-A.md` records commit IDs, migrations, test counts, journey results, screenshots, known limitations, and the exact entry criteria for P1-B. It must not claim Phase 1 complete.

- [ ] **Step 6: Commit the Phase 1A gate**

After all evidence is recorded, remove only the isolated test database:

```powershell
docker compose -f deploy/compose.yaml exec -T db dropdb -U corehr corehr_phase1a_test
```

```powershell
git add -- apps/api/tests/integration/test_phase_1a_journey.py docs/delivery/P1-A.md docs/implementation/phase-1-3-plan.md README.md
git commit -m "test: verify phase 1A organization journey"
```

## Plan Completion Check

Before starting P1-B, verify all statements are true:

- [ ] `e7b3d9a4c2f1` and `f1a000000001` are committed and reversible.
- [ ] `alembic check` reports no new operations.
- [ ] Dictionary APIs reject unknown or unstable codes.
- [ ] The tree shows only current effective structure; historical and future versions are correct in organization detail.
- [ ] Organization cycles and stale versions return stable conflict errors.
- [ ] BU↔legal entity is many-to-many.
- [ ] Leader count is capped at three without rank.
- [ ] One person cannot hold overlapping BP types but can serve multiple organizations.
- [ ] Cost allocation requires exactly 100% and versions by effective date.
- [ ] Revenue targets contain 12 normalized months and aggregate by currency.
- [ ] PC pages can perform every Phase 1A operation without Swagger.
- [ ] Restricted roles cannot write and receive `403 PERMISSION_DENIED`.
- [ ] Tests, logs, screenshots, and artifacts contain synthetic data only.
