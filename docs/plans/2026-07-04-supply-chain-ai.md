# Supply Chain AI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a first-party supply chain collaboration module inside `dtcall` that covers demand forecasting, outsource issue completeness, PR intelligent review, price review, and sample tracking without relying on third-party platforms.

**Architecture:** Add a dedicated Django app `apps.supply_chain` as the domain layer, reuse `production`, `inventory`, `contract`, `approval`, `message`, and `ai`, and implement each business flow as a stateful workflow backed by structured rules plus AI-assisted explanations. Start from model and service foundations, then add views/templates, then wire notifications, approvals, and dashboards.

**Tech Stack:** Django 5.2, Django ORM, Django templates + LayUI, existing `apps.ai` business result pipeline, existing `apps.message` notification service, SQLite/MySQL compatible migrations, Django test runner.

---

### Task 1: Scaffold the supply chain app

**Files:**
- Create: `apps/supply_chain/__init__.py`
- Create: `apps/supply_chain/apps.py`
- Create: `apps/supply_chain/models.py`
- Create: `apps/supply_chain/forms.py`
- Create: `apps/supply_chain/views.py`
- Create: `apps/supply_chain/urls.py`
- Create: `apps/supply_chain/tests.py`
- Modify: `dtcall/settings.py`
- Modify: `dtcall/urls.py`

**Step 1: Write the failing test**

Add a test asserting Django can import and route the new app namespace.

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainAppSmokeTests -v 2`
Expected: FAIL because app and routes do not exist.

**Step 3: Write minimal implementation**

Create the app package, register it in `INSTALLED_APPS`, add root route include, and add a smoke test view.

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainAppSmokeTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add dtcall/settings.py dtcall/urls.py apps/supply_chain
git commit -m "feat: scaffold supply chain app"
```

### Task 2: Add core domain models and migrations

**Files:**
- Modify: `apps/supply_chain/models.py`
- Create: `apps/supply_chain/migrations/__init__.py`
- Create: `apps/supply_chain/migrations/0001_initial.py`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add model tests covering:
- forecast plan creation
- outsource issue item shortage calculation fields
- PR review task default status
- sample request code uniqueness intent

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainModelTests -v 2`
Expected: FAIL because models and tables do not exist.

**Step 3: Write minimal implementation**

Implement initial models:
- `DemandForecastPlan`
- `DemandForecastSnapshot`
- `DemandForecastResult`
- `MaterialPreparationReview`
- `OutsourceIssueOrder`
- `OutsourceIssueItem`
- `PRReviewRule`
- `PRReviewTask`
- `PriceReviewOrder`
- `PriceReviewDocument`
- `PriceReviewComponent`
- `PriceReviewConclusion`
- `SampleRequest`
- `SampleReceipt`
- `SamplePickupRecord`
- `SupplyChainEventLog`

Use existing foreign keys to `Product`, `Supplier`, `ProductionPlan`, `InventoryItem`, and `AUTH_USER_MODEL`.

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainModelTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/models.py apps/supply_chain/tests.py apps/supply_chain/migrations
git commit -m "feat: add supply chain domain models"
```

### Task 3: Implement forecast services and tests

**Files:**
- Create: `apps/supply_chain/services/__init__.py`
- Create: `apps/supply_chain/services/forecast_service.py`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add tests for:
- forecast snapshot generation from stock / in-process / demand values
- recommended preparation quantity calculation
- forecast accuracy calculation from historical actuals

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.DemandForecastServiceTests -v 2`
Expected: FAIL because service functions do not exist.

**Step 3: Write minimal implementation**

Create a pure service layer with deterministic functions:
- aggregate demand inputs
- compute safety stock
- compute recommended preparation
- compute forecast accuracy

Do not call AI here.

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.DemandForecastServiceTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/services apps/supply_chain/tests.py
git commit -m "feat: add forecast calculation services"
```

### Task 4: Implement outsource completeness services

**Files:**
- Create: `apps/supply_chain/services/outsource_service.py`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add tests for:
- BOM to issue item expansion
- shortage quantity computation
- readiness detection when all items are complete

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.OutsourceIssueServiceTests -v 2`
Expected: FAIL because outsource service logic is missing.

**Step 3: Write minimal implementation**

Implement service functions to:
- build issue lines from `BOMItem`
- map to `InventoryItem` by code
- compute available, required, shortage
- mark order as ready or shortage

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.OutsourceIssueServiceTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/services/outsource_service.py apps/supply_chain/tests.py
git commit -m "feat: add outsource issue completeness service"
```

### Task 5: Implement PR review rules engine

**Files:**
- Create: `apps/supply_chain/services/pr_review_service.py`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add tests for:
- matching urgent PR
- matching abnormal tail-order PR
- manual review fallback when multiple abnormal rules hit

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.PRReviewServiceTests -v 2`
Expected: FAIL because the rules engine does not exist.

**Step 3: Write minimal implementation**

Implement a rules engine that accepts structured PR payloads and returns:
- matched rules
- abnormal flag
- recommended action
- approval mode
- evidence payload

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.PRReviewServiceTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/services/pr_review_service.py apps/supply_chain/tests.py
git commit -m "feat: add pr review rules engine"
```

### Task 6: Implement price review parsing and comparison services

**Files:**
- Create: `apps/supply_chain/services/price_review_service.py`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add tests for:
- parsing structured spec payload into components
- historical price deviation detection
- abnormal component highlighting

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.PriceReviewServiceTests -v 2`
Expected: FAIL because service functions do not exist.

**Step 3: Write minimal implementation**

Implement service functions to:
- accept parsed spec data
- normalize cost components
- compare against `PurchasePriceHistory`
- return structured review conclusions

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.PriceReviewServiceTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/services/price_review_service.py apps/supply_chain/tests.py
git commit -m "feat: add price review services"
```

### Task 7: Implement sample tracking services

**Files:**
- Create: `apps/supply_chain/services/sample_service.py`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add tests for:
- request code generation
- receipt status transition
- overdue pickup detection

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.SampleWorkflowServiceTests -v 2`
Expected: FAIL because sample workflow service is missing.

**Step 3: Write minimal implementation**

Implement service helpers for:
- generating sample request codes
- recording receipt
- creating pickup reminders
- marking overdue pickup

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.SampleWorkflowServiceTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/services/sample_service.py apps/supply_chain/tests.py
git commit -m "feat: add sample workflow services"
```

### Task 8: Add forms and CRUD views

**Files:**
- Modify: `apps/supply_chain/forms.py`
- Modify: `apps/supply_chain/views.py`
- Modify: `apps/supply_chain/urls.py`
- Create: `templates/supply_chain/dashboard.html`
- Create: `templates/supply_chain/forecast_list.html`
- Create: `templates/supply_chain/forecast_form.html`
- Create: `templates/supply_chain/outsource_list.html`
- Create: `templates/supply_chain/outsource_form.html`
- Create: `templates/supply_chain/pr_review_list.html`
- Create: `templates/supply_chain/price_review_list.html`
- Create: `templates/supply_chain/sample_list.html`
- Create: `templates/supply_chain/sample_form.html`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add integration tests for page access and create flows for forecast plans, outsource issue orders, and sample requests.

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainViewTests -v 2`
Expected: FAIL because forms, routes, or templates are missing.

**Step 3: Write minimal implementation**

Create Django forms and function-based views that follow existing template patterns.

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainViewTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/forms.py apps/supply_chain/views.py apps/supply_chain/urls.py templates/supply_chain apps/supply_chain/tests.py
git commit -m "feat: add supply chain crud pages"
```

### Task 9: Wire notifications and event logging

**Files:**
- Create: `apps/supply_chain/services/event_service.py`
- Modify: `apps/supply_chain/views.py`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add tests verifying that:
- shortage creates an event
- sample receipt creates a reminder message
- PR abnormal review creates a message task

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainNotificationTests -v 2`
Expected: FAIL because logging and notification hooks are not wired.

**Step 3: Write minimal implementation**

Add a service that writes `SupplyChainEventLog` and uses `MessageService` to send notifications.

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainNotificationTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/services/event_service.py apps/supply_chain/views.py apps/supply_chain/tests.py
git commit -m "feat: add supply chain event logging and notifications"
```

### Task 10: Add AI endpoints for structured assistant results

**Files:**
- Create: `apps/supply_chain/ai_views.py`
- Modify: `apps/supply_chain/urls.py`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add tests for:
- forecast AI summary endpoint
- price review AI explanation endpoint
- PR review AI explanation endpoint

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainAITests -v 2`
Expected: FAIL because AI endpoints do not exist.

**Step 3: Write minimal implementation**

Use existing `build_business_ai_result` patterns to wrap deterministic payloads and AI analyzer calls where available.

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainAITests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/ai_views.py apps/supply_chain/urls.py apps/supply_chain/tests.py
git commit -m "feat: add supply chain ai endpoints"
```

### Task 11: Dashboard and reporting

**Files:**
- Modify: `apps/supply_chain/views.py`
- Create: `templates/supply_chain/dashboard.html`
- Modify: `apps/supply_chain/tests.py`

**Step 1: Write the failing test**

Add tests for dashboard metrics:
- forecast count
- shortage orders
- abnormal PR tasks
- pending pickups

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainDashboardTests -v 2`
Expected: FAIL because dashboard aggregation is incomplete.

**Step 3: Write minimal implementation**

Build a dashboard view with queryset aggregations and summary cards.

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainDashboardTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/supply_chain/views.py templates/supply_chain/dashboard.html apps/supply_chain/tests.py
git commit -m "feat: add supply chain dashboard"
```

### Task 12: Final verification and docs sync

**Files:**
- Modify: `documents/03_PRD_产品需求文档.md`
- Modify: `documents/04_业务模块与数据模型说明.md`
- Modify: `documents/06_AI功能分析与落地规划.md`

**Step 1: Write the failing test**

No new behavior test. Add any missing regression tests discovered during integration.

**Step 2: Run focused test suites**

Run: `python manage.py test apps.supply_chain.tests -v 2`
Expected: PASS

**Step 3: Run broader regression**

Run: `python manage.py test apps.production.tests apps.inventory.tests apps.ai.tests -v 2`
Expected: PASS or known unrelated failures documented.

**Step 4: Sync docs**

Document the new module, its models, and AI capabilities in the project docs.

**Step 5: Commit**

```bash
git add documents/03_PRD_产品需求文档.md documents/04_业务模块与数据模型说明.md documents/06_AI功能分析与落地规划.md
git commit -m "docs: document supply chain ai module"
```
