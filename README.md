# paritycheck · 数据迁移双跑对账与差异归因台

> 面向「Oracle 19c → MySQL 8.0 核心表迁移验收」的双跑对账底稿：按主键稳定哈希分桶 + 行级规范化
> checksum 做全量核对，只对不一致桶抽样下钻，并把差异按类型归因成可审批的修复单。

短名：`paritycheck`；前端 `18226` / 后端 `19226` / MySQL `17726`。

## 真实场景（模拟客户）

**明川银行 · 数据中台迁移组（11 人）**：12 张核心表从 Oracle 19c 迁往 MySQL 8.0 新库，双跑 30 天做验收。

- 现有工作流：迁移组用 DataX 双写 + Excel 记进度，验收时抽 SQL 手工比对。
- 三个痛点：
  1. 全量对比跑不动（数十亿行），只敢抽 1000 行；抽样又证明不了整体一致；
  2. 不一致时定位不到是哪个字段哪一行，靠人肉 SQL 下钻；
  3. 差异原因（类型截断/编码/时区/精度）没人记录，验收报告写不出结论。
- 上下游：上游 = 迁移工具双写后的源库/目标库快照（demo 用同库 `src_*` / `tgt_*` 两套表模拟双跑）；
  本系统替代「抽样 SQL + Excel 记录」；下游 = 迁移验收报告、DBA 修数单、上线评审会。
- 一天的工作剧本：09:40 迁移组打开前一日批次底稿 → 看到 128 桶里 5 个不一致桶、跳过率 96.1% →
  下钻定位 `order_item.qty` 类型截断 12 行与 `customer.phone` 编码差异 8 行 → 生成修复单 →
  负责人审批通过 → 审计导出 CSV 附到验收报告。

角色权限：

| 角色（enum） | 账号 | 主要页面 | 权限 |
|---|---|---|---|
| `admin` 迁移负责人 | admin@paritycheck.demo | 全部 | 全部写 + 审批修复单 |
| `analyst` 数据开发 | analyst@paritycheck.demo | 映射/批次/差异 | 读写，不能审批（审批接口 403） |
| `viewer` 审计 | viewer@paritycheck.demo | 批次/报告 | 只读，可导出 CSV（写操作 403） |

密码统一 `Demo@2026`。

## 主要功能

- 5 个迁移表对维护（源表/目标表/主键/字段归一化规则/负责人）。
- 批次发起：表对多选、策略、桶数 `N∈{64,128,256}`、抽样率、时间窗，实时预估扫描量。
- Celery worker 真跑分桶对账，桶级 count/checksum 落库；128 桶热力矩阵 + 进度条。
- 差异下钻：按差异类型/桶/表对/字段筛选，展示源值→目标值、相似度、归因与建议。
- 修复单：草稿 → 提交 → 审批（仅 admin），差异范围由后端按 (表, 字段, 分类) 汇总。
- 验收导出：差异明细 CSV、归因汇总 CSV（UTF-8 BOM，HTTP 下载）。
- 横切：JWT + 3 角色鉴权、`audit_logs` 审计日志、Redis 每分钟限流 + 每角色每日配额、统一错误码。

## 快速启动

```bash
cd batch-20261110b/projects/gb-553
cp .env.example .env
docker compose up -d --build
# 首次启动 backend 会自动 seed（SEED_DEMO=true），也可手动重跑（幂等）
docker compose exec -T backend python -m scripts.seed_demo
```

- 前端：http://localhost:18226
- 后端健康检查：http://localhost:19226/api/health
- MySQL：`127.0.0.1:17726`，库 `paritycheck`，用户 `paritycheck` / `paritycheck_pw_2026`

真实 seed 输出（两次运行逐字一致）：

```
SEED_SUMMARY pairs=5 src_rows=12000 tgt_rows=11968 batches=4 diffs=40 tickets=3 users=3
```

## 本地开发

- 后端：`cd backend && pip install -r requirements.txt && alembic upgrade head && uvicorn src.main:app --reload --port 8000`
- worker：`PYTHONPATH=/app:/app/backend celery -A worker_src.config.celery_app worker -B -l info`
- 前端：`cd frontend && npm install && npm run dev`（Vite 代理 `/api` → `localhost:19226`）

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + React Router + Zustand（纯手写 CSS，无 UI 框架） |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.0 + PyMySQL + Alembic |
| 异步 | Celery 5 + Redis（broker/backend + 心跳） |
| 数据库 | MySQL 8.0（`utf8mb4_0900_ai_ci`，双跑 `src_*`/`tgt_*` 演示表） |
| 网关 | Nginx 1.27（托管构建产物 + `/api/` 反代 + SPA 回落） |

## 目录

```
gb-553/
├── docker-compose.yml        # 5 服务：frontend/backend/worker/db/redis（全部 healthcheck）
├── backend/
│   ├── Dockerfile · requirements.txt · alembic.ini · entrypoint.sh
│   ├── scripts/seed_demo.py  # 幂等 seed（输出一行 SEED_SUMMARY）
│   └── src/{config,constants,models,schemas,services,controllers,routes,middlewares,utils,migrations}
├── worker/
│   ├── Dockerfile · healthcheck.sh
│   └── src/{config,tasks}    # 复用 backend 的 recon_engine（同一份算法实现）
└── frontend/
    ├── Dockerfile · nginx.conf · package.json
    └── src/{api,stores,types,components/{common,layout},hooks,pages,router,utils,constants,styles}
```

## 两个核心算法（Python 真算、落库、前端只展示）

### A. 分桶对账 `backend/src/services/recon_engine.py`

- 输入：表对集合、时间窗、桶数 `N∈{64,128,256}`、抽样率、策略。
- 步骤：
  1. 主键稳定哈希：`bucket = int(md5(pk)[:8], 16) mod N`（多表对共用同一桶空间）；
  2. 行级 `h = md5('|'.join(列值规范化))`，桶级 `checksum = Σ int(h[:8], 16) mod 2^32`（与行序无关、可复现）；
  3. 桶内 `count` 与 `checksum` 都相等 → `match` 并跳过抽样；
  4. 不一致桶：缺失/多出行按主键行集比对全量暴露；字段级值差异按 `int(md5(pk + '#sample')[:8], 16) % 100 < 抽样率` 确定性抽样后交给 diff_engine；
  5. 输出桶矩阵 + 跳过率（`match 桶数 / 总桶数`）+ 全量扫描成本估算（`桶数 × 单桶平均耗时`，实测后回填）。
- 失败态：源表主键含 NULL → 批次 `failed`，`reason=null_primary_key`；空桶（0/0）记 `empty` 不计不一致；
  主键重复由 diff_engine 标 `duplicate_key`。

### B. 差异定位与归因 `backend/src/services/diff_engine.py`

- 按主键配对 → 行级字段 diff（缺失/多余/值不同）。
- 相似度：数值 `|a-b|/max(|a|,1)` 的相对误差反向；字符串 `1 - lev/max(len)`；时间归一化后比较。
- 分类：`missing` / `extra` / `type_truncated`（目标值比源值短且为前缀）/ `precision_loss`（相对误差 < 1e-6 但不等）/
  `encoding`（仅全半角、空格、不可见字符差异）/ `value_shift` / `duplicate_key`（失败态，不参与相似度）。
- 归因聚合：按 `(表, 字段, 分类)` 计数排序，输出「最可能原因 + 修复建议」。

## 共享枚举与出现位置

| 枚举组 | 后端定义 | 前端定义 | 其他出现位置 |
|---|---|---|---|
| `Role` | `backend/src/constants/enums.py` + `constants/roles.py` 能力矩阵 | `frontend/src/constants/enums.ts` | `models/user.py`、`middlewares/rbac.py`、Login 页角色提示 |
| `BatchStatus` | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` | `recon_engine.py` 状态机、`BatchDetail` 状态印章、seed 批次 |
| `BucketStatus` | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` | `recon_engine.py` 桶判定、`BucketMatrix` 图例 |
| `DiffType` | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` | `diff_engine.py` 分类与归因、`Diffs` 页筛选 chip |
| `TicketStatus` | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` | `ticket_service.py` 状态机、`Tickets` 页台账 |

## 环境变量

见 `.env.example`（`.env` 已进 `.gitignore`）：`COMPOSE_PROJECT_NAME`、`FRONTEND_PORT/BACKEND_PORT/DB_PORT`、
`DB_NAME/DB_USER/DB_PASSWORD/DB_ROOT_PASSWORD`、`JWT_SECRET`、`REDIS_URL`、`SEED_DEMO`、`DEMO_PASSWORD`。

## 演示数据（seed）

`pairs=5`（orders/order_item/customer/payment/refund）、源表 12,000 行、目标表 11,968 行；
4 个批次：completed（128 桶 / 5% 抽样，真实跑出 5 个不一致桶、40 行差异 = 12 类型截断 + 8 编码 + 20 缺失）、
running（payment，桶 64，已算前 16 桶）、failed（refund，`null_primary_key`）、pending（orders，桶 256）；
3 张修复单（draft / submitted / approved）；3 个演示账号。

## License

Demo only · 明川银行数据中台迁移组内部验收用例（虚构客户与数据）。
