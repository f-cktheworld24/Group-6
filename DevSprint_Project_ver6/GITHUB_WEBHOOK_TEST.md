# GitHub Webhook 集成功能测试指南

## 前置条件

1. 确保后端服务正在运行（默认地址：`http://127.0.0.1:8000`）
2. 确保数据库中已有任务数据（可以通过前端创建任务，或使用 demo 数据）

## 测试方法

### 方法一：使用 Python 测试脚本（推荐）

#### 安装依赖

```bash
pip install requests
```

#### 测试 Push 事件（提交事件）

```bash
# 测试提交事件，关联任务 #1
python test_github_webhook.py --event-type push --task-id 1

# 自定义仓库名称和提交 SHA
python test_github_webhook.py --event-type push --task-id 1 --repo-name "your-org/your-repo" --commit-sha "abc123def456"
```

**说明：** 
- Push 事件会解析提交消息中的 `ref #任务ID` 模式
- 提交消息会自动生成为：`feat: implement feature ref #1`
- 如果任务存在，会将提交关联到该任务

#### 测试 Pull Request 事件

```bash
# 测试 PR 事件，关联任务 #2
python test_github_webhook.py --event-type pull_request --task-id 2

# 测试已合并的 PR
python test_github_webhook.py --event-type pull_request --task-id 2 --pr-state closed --pr-merged

# 自定义 PR URL
python test_github_webhook.py --event-type pull_request --task-id 2 --pr-url "https://github.com/your-org/your-repo/pull/123"
```

**说明：**
- PR 事件会解析 PR 标题和正文中的 `ref #任务ID` 模式
- PR 标题会自动生成为：`Fix issue ref #2`
- 如果任务存在，会将 PR 关联到该任务，并将任务状态更新为 `CODE_REVIEW`

#### 测试 Status 事件（CI 状态）

```bash
# 测试 CI 成功状态
python test_github_webhook.py --event-type status --commit-sha "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3" --ci-status success

# 测试 CI 失败状态（会标记任务为 blocked）
python test_github_webhook.py --event-type status --commit-sha "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3" --ci-status failure
```

**说明：**
- Status 事件通过 commit SHA 查找已关联的任务
- 如果 CI 状态为 `failure`、`failed` 或 `error`，会将任务标记为 `blocked`

#### 测试 Check Suite 事件

```bash
# 测试检查套件完成事件
python test_github_webhook.py --event-type check_suite --commit-sha "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3" --ci-status success
```

### 方法二：使用 curl 命令

#### 测试 Push 事件

```bash
curl -X POST http://127.0.0.1:8000/api/github/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d '{
    "ref": "refs/heads/main",
    "repository": {
      "full_name": "octocat/Hello-World",
      "name": "Hello-World"
    },
    "commits": [
      {
        "id": "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3",
        "message": "feat: implement feature ref #1",
        "url": "https://github.com/octocat/Hello-World/commit/7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3",
        "author": {
          "name": "Test User",
          "email": "test@example.com"
        }
      }
    ]
  }'
```

#### 测试 Pull Request 事件

```bash
curl -X POST http://127.0.0.1:8000/api/github/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -d '{
    "action": "opened",
    "repository": {
      "full_name": "octocat/Hello-World",
      "name": "Hello-World"
    },
    "pull_request": {
      "number": 1,
      "title": "Fix issue ref #2",
      "body": "This PR fixes the issue mentioned in ref #2",
      "html_url": "https://github.com/octocat/Hello-World/pull/1",
      "state": "open",
      "merged": false,
      "head": {
        "sha": "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3"
      }
    }
  }'
```

### 方法三：使用 PowerShell（Windows）

如果之前创建了 `simulate_github_webhook.ps1` 脚本，可以使用：

```powershell
# Push 事件
.\simulate_github_webhook.ps1 -EventType push -TaskId 1

# Pull Request 事件
.\simulate_github_webhook.ps1 -EventType pull_request -TaskId 2

# Status 事件
.\simulate_github_webhook.ps1 -EventType status -CommitSha "abc123" -CIStatus failure
```

## 测试流程建议

### 完整测试流程

1. **准备测试数据**
   - 在前端创建几个任务（例如任务 #1, #2, #3）
   - 记录这些任务的 ID

2. **测试 Push 事件**
   ```bash
   python test_github_webhook.py --event-type push --task-id 1
   ```
   - 检查前端看板，任务 #1 应该显示 GitHub 链接（Commit）
   - 检查任务详情，应该能看到 commit hash 和仓库名称

3. **测试 Pull Request 事件**
   ```bash
   python test_github_webhook.py --event-type pull_request --task-id 2
   ```
   - 检查前端看板，任务 #2 应该：
     - 状态自动变为 `CODE_REVIEW`
     - 显示 GitHub 链接（PR）
     - 如果有配置评审者，应该创建评审任务分配

4. **测试 CI 状态更新**
   ```bash
   # 先发送一个 push 事件关联任务
   python test_github_webhook.py --event-type push --task-id 3 --commit-sha "test123"
   
   # 然后发送 status 事件
   python test_github_webhook.py --event-type status --commit-sha "test123" --ci-status failure
   ```
   - 检查任务 #3，应该：
     - 显示 CI 状态为 `failure`
     - 任务被标记为 `blocked`

## 验证结果

### 在前端验证

1. **查看任务卡片**
   - 任务卡片底部应该显示 GitHub 链接（PR 或 Commit）
   - 点击链接应该能跳转到 GitHub

2. **查看任务详情**
   - 任务应该包含 `github_links` 数据
   - 如果发送了 PR 事件，任务状态应该变为 `CODE_REVIEW`

3. **查看评审队列**
   - 如果发送了 PR 事件，任务应该出现在评审队列中

### 通过 API 验证

```bash
# 获取任务详情
curl http://127.0.0.1:8000/api/tasks/1

# 检查返回的 JSON 中应该包含 github_links 字段
```

## 常见问题

### 1. 任务没有关联成功

**可能原因：**
- 任务 ID 不存在
- 提交消息/PR 标题中没有正确格式的 `ref #任务ID`

**解决方法：**
- 确认任务 ID 存在
- 确保消息中包含 `ref #任务ID`（不区分大小写）

### 2. PR 事件后任务状态没有变为 CODE_REVIEW

**可能原因：**
- 任务不存在
- PR 标题/正文中没有 `ref #任务ID`

**解决方法：**
- 检查任务是否存在
- 确认 PR 标题或正文中包含 `ref #任务ID`

### 3. CI 状态更新没有生效

**可能原因：**
- Commit SHA 没有关联到任何任务
- 需要先发送 push 事件关联任务和 commit SHA

**解决方法：**
- 先发送 push 事件，确保 commit SHA 关联到任务
- 然后再发送 status 事件

## 调试技巧

1. **查看后端日志**
   - 后端应该会输出处理 webhook 的日志信息
   - 检查是否有错误信息

2. **使用 --verbose 模式**
   - 测试脚本会输出详细的请求和响应信息

3. **检查数据库**
   - 直接查询 `github_links` 表，确认数据是否正确插入

## 示例：完整测试场景

```bash
# 1. 创建任务（通过前端或 API）
# 假设创建了任务 #1, #2, #3

# 2. 测试提交关联
python test_github_webhook.py --event-type push --task-id 1 --commit-sha "commit001"

# 3. 测试 PR 创建和关联
python test_github_webhook.py --event-type pull_request --task-id 2

# 4. 测试 CI 状态更新（使用步骤2的 commit SHA）
python test_github_webhook.py --event-type status --commit-sha "commit001" --ci-status success

# 5. 测试 CI 失败场景
python test_github_webhook.py --event-type status --commit-sha "commit001" --ci-status failure
```

