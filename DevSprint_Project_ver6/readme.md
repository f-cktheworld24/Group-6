## DevSprint 项目说明（DevSprint_Project）

---

## 技术栈
- 后端: Python, FastAPI, SQLAlchemy, APScheduler
- 前端: React（Create React App），Recharts
- 接口文档: Swagger UI `http://localhost:8000/docs`
- 数据库: SQLite（一键启动脚本默认），也支持 MySQL

---

## 项目结构
- `backend/` 后端 FastAPI 服务（`main.py` 提供 API、模型与定时任务）
- `frontend/` 前端 React 应用（看板、燃尽图、仪表盘等页面）
- `start.ps1` Windows 一键启动脚本（同时拉起后端与前端）
- `devsprint.db` SQLite 数据库文件（使用脚本默认生成）
- `2.sql` 示例 SQL 文件（如需导入自定义数据）

---

## 一键启动（Windows）
1) 在项目根目录执行：
   - `powershell -ExecutionPolicy Bypass -File .\start.ps1`
2) 功能说明：
   - 自动安装后端依赖并设置 `DATABASE_URL=sqlite:///./devsprint.db`
   - 启动后端 `uvicorn backend.main:app --reload`（地址 `http://127.0.0.1:8000`）
   - 自动下载或使用便携版 Node v20，安装前端依赖并启动前端（地址 `http://localhost:3000`）

提示：如果系统未安装 `py` 启动器，脚本会回退到 `python`；如仍报错，请确保已安装 Python 并可在终端直接运行 `python`。

---

## 手动启动后端
1) 准备 Python 3.10+，在根目录：
   - `python -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
   - `python -m pip install -r backend\requirements.txt`
   - `python -m pip install uvicorn`
2) 使用 SQLite（推荐快速体验）：
   - PowerShell：`$env:DATABASE_URL = "sqlite:///./devsprint.db"`
   - CMD：`set DATABASE_URL=sqlite:///./devsprint.db`
3) 运行：
   - `python -m uvicorn backend.main:app --reload`
4) 关闭示例数据灌入（可选）：
   - PowerShell：`$env:DEVSPRINT_SEED_DEMO = "0"`
   - CMD：`set DEVSPRINT_SEED_DEMO=0`

使用 MySQL：如未设置 `DATABASE_URL`，后端默认连接 `mysql+pymysql://root:password@localhost:3306/devsprint_db`；可按需修改为你的 MySQL 连接串。

---

## 启动前端
方式 A（系统 Node）：
- 在 `frontend` 目录执行：
  - `npm install --no-fund --no-audit`
  - PowerShell：`$env:REACT_APP_API_BASE = "http://127.0.0.1:8000"`
  - CMD：`set REACT_APP_API_BASE=http://127.0.0.1:8000`
  - `npm start`

方式 B（便携 Node）：
- 使用根目录下 `.node_portable\node-v20.16.0-win-x64\npm.cmd` 执行上述命令（`npm` 改为便携路径）。

---

## 初始化示例数据
默认数据库为空时，前端看板是空板。可用以下方式快速填充 Sprint / Story / Task，体验燃尽图、剩余天数、技术债务、评审队列等：

- **一键生成（自动或手动）**
  - 自动：后端启动且任务表为空时，会自动灌入 Demo 数据。若不想自动生成，启动前设置 `DEVSPRINT_SEED_DEMO=0`。
  - 手动：执行 `python backend/seed_demo_data.py --base http://localhost:8000`；需要重置示例时追加 `--force`。
  - Demo 链接默认指向 GitHub 示例仓库 `octocat/Hello-World`，可用 `DEVSPRINT_DEMO_REPO` / `DEVSPRINT_DEMO_PR_URL` / `DEVSPRINT_DEMO_COMMIT` 自定义。

- **手动调用 API 示例**
  - 创建 Sprint  
    `curl -X POST http://localhost:8000/api/sprints -H "Content-Type: application/json" -d "{\"name\":\"Demo Sprint\",\"goal\":\"完成前端看板演示\",\"start_date\":\"2024-11-25\",\"end_date\":\"2024-12-02\",\"status\":\"ACTIVE\"}"`
  - 创建 Story（替换 `sprint_id`）  
    `curl -X POST http://localhost:8000/api/stories -H "Content-Type: application/json" -d "{\"title\":\"看板体验提升\",\"description\":\"- 支持 Markdown\\n- 优化列排序\",\"story_points\":5,\"priority\":2,\"sprint_id\":1}"`
  - 创建 Task  
    `curl -X POST http://localhost:8000/api/tasks -H "Content-Type: application/json" -d "{\"title\":\"实现列内拖拽\",\"story_id\":1,\"story_points\":3,\"status\":\"IN_PROGRESS\",\"assignee\":\"alice\"}"`

- **模拟 GitHub Webhook**
  
  ##### 测试提交事件（关联任务 #1）
  
  `python test_github_webhook.py --event-type push --task-id 1`
  
  ##### 测试 PR 事件（关联任务 #2）
  
  `python test_github_webhook.py --event-type pull_request --task-id 2`
  
  ##### 测试 CI 状态更新
  
  `python test_github_webhook.py --event-type status --commit-sha "abc123" --ci-status failure`

---

## 后端 API 概览
- `GET /api/dashboard` 仪表盘汇总（燃尽、评审队列、技术债务、倒计时、WIP、评审 SLA）
- `GET /api/sprints` / `POST /api/sprints` / `PATCH /api/sprints/{id}` / `GET /api/sprints/active`
- `GET /api/stories/{id}` / `POST /api/stories` / `PATCH /api/stories/{id}`
- `GET /api/tasks` / `POST /api/tasks` / `PATCH /api/tasks/{id}` / `DELETE /api/tasks/{id}`
- `GET /api/burndown/{sprint_id}` / `GET /api/cfd/{sprint_id}` / `GET /api/velocity`
- `POST /api/github/webhook` 解析 `Ref #<task_id>` 进行 commit/PR 关联
- `POST /api/simulate/advance_days` / `POST /api/simulate/set_remaining_days`
- `POST /api/admin/clear_board` 清空当前活跃 Sprint 的故事、任务与快照（保留 Sprint 本身）
 - `GET /api/tasks/{id}/assignments` 返回任务的分配列表（`DEV/REVIEW`、剩余天数、状态与决策）
 - `POST /api/tasks/{id}/assignments` 批量创建分配（体含 `users[]`、`role`、`remaining_days`）
 - `POST /api/review/{task_id}/decision` 审查决策（`approved` 或不通过并指定 `tech_debt_days`）

## 模拟进度与剩余天数
- 燃尽图支持“模拟天数”按钮：可模拟 +1/+3 天或输入自定义天数，自动推进任务状态（TODO → IN_PROGRESS → CODE_REVIEW → DONE），并生成对应日期的燃尽快照。
- 可点击“设置剩余天数”直接指定当前 Sprint 的剩余天数（非负整数），系统会调整模拟日期偏移，倒计时和燃尽图随之更新。
- 如果所有任务都已完成，模拟时会自动生成一条技术债务任务，确保燃尽与看板有可见变化。

## 开发者特性与扩展
- WIP 限制：通过环境变量设置各列上限，仪表盘显示超限提示（`DEVSPRINT_WIP_IN_PROGRESS`、`DEVSPRINT_WIP_CODE_REVIEW` 等）。
- Velocity 报告：`GET /api/velocity` 返回各 Sprint 完成点数与平均速度，前端折线图展示。
- CFD（累积流图）：每日记录各状态任务数，`GET /api/cfd/{sprint_id}` 返回堆叠面积图所需数据。
- 评审队列与 SLA：PR 进入队列自动指派 Reviewer（`DEVSPRINT_REVIEWERS`），按 `DEVSPRINT_REVIEW_SLA_DAYS` 计算等待与超期。
- GitHub 状态增强：记录 `pr_state`、`pr_merged`、`ci_status`，CI 失败自动标记任务阻塞。
- 过滤/视图：看板支持 Assignee、优先级、技术债务过滤与视图切换（仅活跃故事/仅评审队列）。
- 看板分页：每个状态列支持分页，默认每页 5 条；提供首页/上一页/下一页/末页按钮与每页数量选择（5/10/20/50）。当筛选条件变化或创建/删除任务后，分页自动重置为第一页；当某列为空时隐藏分页条；窄屏下分页控件自动换行。
- 多人 PR 审查与分配：PR 创建时为 `DEVSPRINT_REVIEWERS` 中所有成员自动创建 `REVIEW` 分配，分配带倒计时；模拟 +1 天时各分配的 `remaining_days` 同步减 1。
- 审查决策：在前端 `Code Review` 列提供“通过/不通过”按钮；不通过时需填写技术债完成天数，任务转为技术债并重新进入开发分配。
- 进行中排序：`IN_PROGRESS` 列按“技术债优先 → 故事优先级升序 → ID”排序，确保优先解决技术债务。
 - 交互优化：所有输入改为模态框交互（替代浏览器 `prompt`），包括编辑用户故事描述、模拟自定义天数与设置剩余天数，以及审查不通过时填写技术债完成天数。

---

## 使用指引（前端交互）
- 编辑用户故事描述：在任务卡点击“编辑描述”，弹出模态框修改 Markdown 文本并“保存”。
- 模拟天数：在燃尽图卡片点击“自定义天数”，输入正整数并“开始模拟”；看板与燃尽图将随即更新。
- 设置剩余天数：点击“设置剩余天数”，输入非负整数并“设置”；倒计时和燃尽图会更新到指定天数。
- 审查决策：在 `Code Review` 列，点击“通过”直接完成审查；点击“不通过”弹出模态输入技术债完成天数并提交，任务转为技术债。

---

## 清空看板
- 说明：清空当前活跃 Sprint 下的所有故事与任务，并删除对应的燃尽与累积流快照；保留 Sprint 本身以便继续规划。
- 前端：在看板页头部点击“清空看板”，确认后执行。
- 接口：
  - `curl -X POST http://127.0.0.1:8000/api/admin/clear_board`
  - 响应示例：`{"deleted_stories":1,"deleted_tasks":1,"sprint_id":1}`
- 注意：操作不可恢复，请谨慎使用；如需全量重置包含所有 Sprint 的数据，可另行扩展管理端接口。

## 环境变量速查
- `DATABASE_URL`：数据库连接（默认 SQLite）
- `DEVSPRINT_SEED_DEMO`：是否自动灌入示例数据（默认 1）
- `DEVSPRINT_WIP_TODO` / `DEVSPRINT_WIP_IN_PROGRESS` / `DEVSPRINT_WIP_CODE_REVIEW` / `DEVSPRINT_WIP_DONE`
- `DEVSPRINT_REVIEWERS`：逗号分隔评审人分配列表
- `DEVSPRINT_REVIEW_SLA_DAYS`：评审 SLA 天数
- `DEVSPRINT_DEMO_REPO` / `DEVSPRINT_DEMO_PR_URL` / `DEVSPRINT_DEMO_COMMIT`

---

## 非功能需求（NFR）与测试
- 性能
  - 在 500 条任务场景下，分页切换的 75% 分位渲染耗时 < 120ms；首次看板渲染 75% 分位 < 250ms。
  - 单列同时挂载的卡片不超过当前页大小，避免超长列表导致的布局抖动与滚动卡顿。
  - **性能测试脚本**: `python backend/seed_perf_data.py` 可自动生成 500 条测试任务。
- 可访问性（A11y）
  - 分页按钮具备键盘可达性与语义（`button` + `aria-label`/`aria-disabled`），禁用态明确；颜色对比符合 WCAG AA。
- 响应式与可用性
  - 分页条在窄屏自动换行；点击区域不小于 40×40 像素；文案与界面语言一致。
- 可靠性与鲁棒性
  - 当数据为空或网络异常时界面不抛错；页码自动夹取到有效范围；筛选切换后自动回到第一页。
- 可维护性
  - 不引入额外依赖；分页逻辑集中于前端组件，遵循现有状态管理与代码风格。
- 国际化准备
  - 分页相关文案集中管理，便于后续引入 i18n 映射。

> 注：当前分页为前端实现，并不改变后端接口行为；如任务总量显著增长，可按需扩展 `GET /api/tasks` 的服务端分页（`status/page/size`），前端在阈值下自动切换。

## 常见问题
- 端口占用：后端默认 `8000`，前端默认 `3000`；如需修改，请按各自启动命令调整。
- MySQL 使用：将 `DATABASE_URL` 改为 `mysql+pymysql://<user>:<pass>@<host>:3306/devsprint_db` 即可。
- 数据库初始化：如果无法自动生成 SQLite 文件，或者需要在 MySQL 中从零创建表结构，请运行项目根目录下的 `2.sql` 文件。
- 前端连接失败：确保 `REACT_APP_API_BASE` 指向后端地址（默认 `http://127.0.0.1:8000`）。
- `py` 命令不可用：请直接使用 `python`，或安装 Python Launcher（Windows）。
