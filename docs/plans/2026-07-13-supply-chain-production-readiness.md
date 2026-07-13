# Supply Chain Production Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将供应链模块改造成只使用真实项目数据、支持审计与并发、AI 不阻塞核心页面且可完整回归的生产级业务模块。

**Architecture:** 保留现有 Django 应用和 Layui 页面，通过统一来源字段、业务序列、AI 分析记录和领域服务强化内核。所有写操作在服务层完成事务、行锁、状态校验和事件记录，视图只处理输入与反馈；页面 GET 只读取持久化 AI 结果。

**Tech Stack:** Django ORM、Django forms、项目 MessageService、项目 AIAnalysisTool、Layui、Django TestCase、Playwright。

---

### Task 1: 来源追溯与并发安全基础

**Files:**
- Modify: `apps/supply_chain/models.py`
- Create: `apps/supply_chain/migrations/0003_production_readiness_foundation.py`
- Create: `apps/supply_chain/services/sequence_service.py`
- Test: `apps/supply_chain/tests.py`

**Step 1: Write failing tests**

增加测试证明：业务序列连续生成不重复；核心单据可保存来源类型、来源主键、来源单号和来源快照；AI 分析记录按模块和对象保存最近有效结果。

**Step 2: Run tests to verify failure**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainFoundationTests --verbosity=2 --noinput`

Expected: FAIL，因为模型与序列服务尚不存在。

**Step 3: Implement minimal foundation**

新增 `SupplyChainSequence`、`SupplyChainAIInsight`，为预测、PR、核价和打样增加来源字段及必要索引/约束；实现事务内 `select_for_update` 的业务编号生成器。

**Step 4: Verify tests and migrations**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainFoundationTests --verbosity=2 --noinput`

Run: `python manage.py makemigrations --check --dry-run`

Expected: PASS；No changes detected。

**Step 5: Commit**

Commit message: `建立供应链来源追溯与并发安全基础`

### Task 2: 删除伪造初始化并接入真实上游单据

**Files:**
- Modify: `apps/supply_chain/services/bootstrap_service.py`
- Create: `apps/supply_chain/services/source_service.py`
- Modify: `apps/supply_chain/views.py`
- Modify: `apps/supply_chain/urls.py`
- Test: `apps/supply_chain/tests.py`

**Step 1: Write failing tests**

增加测试证明：同步不会生成样品到货/领样、不会伪造成本拆解或预测结果；预测来自生产计划；PR 来自 `MaterialRequest`；核价来自采购订单明细/价格历史；重复同步幂等。

**Step 2: Run tests to verify failure**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainSourceSyncTests --verbosity=2 --noinput`

Expected: FAIL，现有初始化仍会生成推测性业务事实。

**Step 3: Implement source synchronization**

将全局 bootstrap 改为只同步真实可操作来源。没有对应上游事实时保持空状态并返回缺失原因；打样必须人工创建；为来源记录保存快照和事件日志。

**Step 4: Verify tests**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainSourceSyncTests --verbosity=2 --noinput`

Expected: PASS。

**Step 5: Commit**

Commit message: `改造供应链真实来源同步流程`

### Task 3: 状态机、幂等与文件安全

**Files:**
- Create: `apps/supply_chain/services/workflow_service.py`
- Modify: `apps/supply_chain/forms.py`
- Modify: `apps/supply_chain/views.py`
- Modify: `apps/supply_chain/models.py`
- Create: `apps/supply_chain/migrations/0004_supply_chain_workflow_constraints.py`
- Test: `apps/supply_chain/tests.py`

**Step 1: Write failing tests**

覆盖预测评审、委外校验/发料、PR 评估/审批、核价分析、样品到货/领样/提醒的重复提交和非法跳转；覆盖附件类型、大小、空内容及存储失败。

**Step 2: Run tests to verify failure**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainWorkflowReliabilityTests --verbosity=2 --noinput`

Expected: FAIL，证明并发与输入边界尚未完整保护。

**Step 3: Implement locked workflows**

将关键操作迁入服务层，在原子事务内锁定单据并重查状态；使用数据库约束防重；通知通过 `transaction.on_commit`；附件增加格式/大小校验和失败清理。

**Step 4: Verify tests**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainWorkflowReliabilityTests --verbosity=2 --noinput`

Expected: PASS。

**Step 5: Commit**

Commit message: `强化供应链状态流转与文件安全`

### Task 4: AI 结果持久化与非阻塞页面

**Files:**
- Modify: `apps/supply_chain/services/ai_services.py`
- Create: `apps/supply_chain/services/ai_insight_service.py`
- Modify: `apps/supply_chain/ai_views.py`
- Modify: `apps/supply_chain/views.py`
- Modify: `apps/supply_chain/urls.py`
- Test: `apps/supply_chain/tests_ai.py`

**Step 1: Write failing tests**

验证页面 GET 不调用模型；AI 刷新成功保存结构化结果；模型失败保留上次有效结果并记录错误；并发请求不修改共享客户端；非法枚举和越界数值不会进入业务结论。

**Step 2: Run tests to verify failure**

Run: `python manage.py test apps.supply_chain.tests_ai.SupplyChainAIProductionTests --verbosity=2 --noinput`

Expected: FAIL，当前 GET 同步调用且没有持久化结果。

**Step 3: Implement persisted insights**

每次 AI 调用使用独立工具实例；新增按作用域刷新与读取服务；页面只读取结果；失败记录错误并回退到确定性业务规则或上次成功结果。

**Step 4: Verify tests**

Run: `python manage.py test apps.supply_chain.tests_ai.SupplyChainAIProductionTests apps.supply_chain.tests_ai --verbosity=1 --noinput`

Expected: PASS。

**Step 5: Commit**

Commit message: `完善供应链AI持久化与降级机制`

### Task 5: 页面统一与业务可理解性

**Files:**
- Modify: `templates/supply_chain/dashboard.html`
- Modify: `templates/supply_chain/inventory_analysis.html`
- Modify: `templates/supply_chain/forecast_list.html`
- Modify: `templates/supply_chain/outsource_list.html`
- Modify: `templates/supply_chain/pr_review_list.html`
- Modify: `templates/supply_chain/price_review_list.html`
- Modify: `templates/supply_chain/sample_list.html`
- Modify: `templates/supply_chain/price_review_form.html`
- Modify: `templates/supply_chain/sample_form.html`
- Modify: `templates/supply_chain/forecast_form.html`
- Test: `apps/supply_chain/tests.py`

**Step 1: Write failing response tests**

验证各页面包含真实来源、最近处理状态、下一步动作、明确空状态、AI 更新时间/失败状态和附件用途说明，且不再出现“初始化台账”入口。

**Step 2: Run tests to verify failure**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainPageClarityTests --verbosity=2 --noinput`

Expected: FAIL，当前模板仍以初始化数据为入口。

**Step 3: Implement consistent UI**

复用项目现有组件与 CSS 类，统一表格、标签、按钮、表单分组、来源信息、错误和空状态；不引入独立视觉体系。

**Step 4: Verify response tests**

Run: `python manage.py test apps.supply_chain.tests.SupplyChainPageClarityTests --verbosity=2 --noinput`

Expected: PASS。

**Step 5: Commit**

Commit message: `统一供应链页面与业务指引`

### Task 6: 全量验证与代码审查

**Files:**
- Modify only files required by findings

**Step 1: Run focused suites**

Run: `python manage.py test apps.supply_chain.tests_ai --verbosity=1 --noinput`

Run: `python manage.py test apps.supply_chain.tests --verbosity=1 --noinput`

Run: `python manage.py check`

Run: `python manage.py makemigrations --check --dry-run`

Expected: 全部 exit 0。

**Step 2: Run cross-module regression**

Run: `python manage.py test apps.inventory apps.production apps.supply_chain --verbosity=1 --noinput`

Expected: 新变更不破坏库存、生产与供应链联动；若发现既有失败，单独记录并确认与本次变更的关系。

**Step 3: Run browser acceptance**

启动新端口服务，使用 Playwright 真实登录并覆盖驾驶舱、库存分析、预测、委外、PR、核价、打样及统计/报表页面；执行主要合法动作与重复提交；检查控制台错误、页面错误、4xx/5xx、布局溢出和移动端视口。

**Step 4: Review diff**

逐项对照设计验收标准，检查重复代码、失效路由、旧初始化文案、无来源数据、未使用模型/字段和迁移冲突。

**Step 5: Commit fixes**

Commit message: `完成供应链生产化验收与收尾`
