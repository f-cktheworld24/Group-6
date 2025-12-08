#!/usr/bin/env python3
"""
GitHub Webhook 集成功能测试脚本

使用方法:
    python test_github_webhook.py --event-type push --task-id 1
    python test_github_webhook.py --event-type pull_request --task-id 2
    python test_github_webhook.py --event-type status --commit-sha abc123 --ci-status failure
"""

import argparse
import json
import requests
from typing import Optional


def test_push_event(webhook_url: str, task_id: int, repo_name: str = "octocat/Hello-World", commit_sha: str = "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3"):
    """测试 push 事件（提交事件）"""
    payload = {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": repo_name,
            "name": repo_name.split("/")[1]
        },
        "commits": [
            {
                "id": commit_sha,
                "message": f"feat: implement feature ref #{task_id}",
                "url": f"https://github.com/{repo_name}/commit/{commit_sha}",
                "author": {
                    "name": "Test User",
                    "email": "test@example.com"
                }
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "test-delivery-id"
    }
    
    print(f"📤 发送 Push 事件 - 关联任务 #{task_id}")
    print(f"   提交消息: {payload['commits'][0]['message']}")
    return send_webhook(webhook_url, payload, headers)


def test_pull_request_event(webhook_url: str, task_id: int, repo_name: str = "octocat/Hello-World", pr_url: Optional[str] = None, pr_state: str = "open", pr_merged: bool = False):
    """测试 pull_request 事件"""
    if not pr_url:
        pr_url = f"https://github.com/{repo_name}/pull/1"
    
    payload = {
        "action": "opened",
        "repository": {
            "full_name": repo_name,
            "name": repo_name.split("/")[1]
        },
        "pull_request": {
            "number": 1,
            "title": f"Fix issue ref #{task_id}",
            "body": f"This PR fixes the issue mentioned in ref #{task_id}",
            "html_url": pr_url,
            "state": pr_state,
            "merged": pr_merged,
            "head": {
                "sha": "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3"
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "test-delivery-id"
    }
    
    print(f"📤 发送 Pull Request 事件 - 关联任务 #{task_id}")
    print(f"   PR 标题: {payload['pull_request']['title']}")
    print(f"   PR 状态: {pr_state}, 已合并: {pr_merged}")
    return send_webhook(webhook_url, payload, headers)


def test_status_event(webhook_url: str, commit_sha: str, ci_status: str = "success", repo_name: str = "octocat/Hello-World"):
    """测试 status 事件（CI 状态更新）"""
    payload = {
        "repository": {
            "full_name": repo_name,
            "name": repo_name.split("/")[1]
        },
        "sha": commit_sha,
        "state": ci_status,
        "context": "continuous-integration/travis-ci/pr",
        "description": f"Build {ci_status}",
        "target_url": f"https://travis-ci.org/{repo_name}/builds/123456"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "status",
        "X-GitHub-Delivery": "test-delivery-id"
    }
    
    print(f"📤 发送 Status 事件 - Commit SHA: {commit_sha}")
    print(f"   CI 状态: {ci_status}")
    return send_webhook(webhook_url, payload, headers)


def test_check_suite_event(webhook_url: str, commit_sha: str, conclusion: str = "success", repo_name: str = "octocat/Hello-World"):
    """测试 check_suite 事件"""
    payload = {
        "action": "completed",
        "repository": {
            "full_name": repo_name,
            "name": repo_name.split("/")[1]
        },
        "check_suite": {
            "head_sha": commit_sha,
            "conclusion": conclusion,
            "status": "completed"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "check_suite",
        "X-GitHub-Delivery": "test-delivery-id"
    }
    
    print(f"📤 发送 Check Suite 事件 - Commit SHA: {commit_sha}")
    print(f"   结论: {conclusion}")
    return send_webhook(webhook_url, payload, headers)


def send_webhook(webhook_url: str, payload: dict, headers: dict):
    """发送 webhook 请求"""
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"\n📥 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 请求成功!")
            print(f"   关联的任务ID: {result.get('linked_tasks', [])}")
            return True
        else:
            print(f"❌ 请求失败!")
            print(f"   错误信息: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="测试 GitHub Webhook 集成功能")
    parser.add_argument(
        "--webhook-url",
        default="http://127.0.0.1:8000/api/github/webhook",
        help="Webhook URL (默认: http://127.0.0.1:8000/api/github/webhook)"
    )
    parser.add_argument(
        "--event-type",
        choices=["push", "pull_request", "status", "check_suite"],
        required=True,
        help="事件类型"
    )
    parser.add_argument(
        "--task-id",
        type=int,
        help="任务ID（用于 push 和 pull_request 事件）"
    )
    parser.add_argument(
        "--repo-name",
        default="octocat/Hello-World",
        help="仓库名称 (默认: octocat/Hello-World)"
    )
    parser.add_argument(
        "--commit-sha",
        default="7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3",
        help="提交 SHA (默认: 7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3)"
    )
    parser.add_argument(
        "--commit-message",
        help="提交消息（可选，默认会自动生成包含任务ID的消息）"
    )
    parser.add_argument(
        "--pr-url",
        help="PR URL（可选，默认会自动生成）"
    )
    parser.add_argument(
        "--pr-state",
        choices=["open", "closed"],
        default="open",
        help="PR 状态 (默认: open)"
    )
    parser.add_argument(
        "--pr-merged",
        action="store_true",
        help="PR 是否已合并"
    )
    parser.add_argument(
        "--ci-status",
        choices=["success", "failure", "pending", "error"],
        default="success",
        help="CI 状态 (默认: success)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("GitHub Webhook 集成功能测试")
    print("=" * 60)
    print(f"Webhook URL: {args.webhook_url}")
    print(f"事件类型: {args.event_type}")
    print("-" * 60)
    
    success = False
    
    if args.event_type == "push":
        if not args.task_id:
            print("❌ 错误: push 事件需要指定 --task-id")
            return
        success = test_push_event(
            args.webhook_url,
            args.task_id,
            args.repo_name,
            args.commit_sha
        )
    
    elif args.event_type == "pull_request":
        if not args.task_id:
            print("❌ 错误: pull_request 事件需要指定 --task-id")
            return
        success = test_pull_request_event(
            args.webhook_url,
            args.task_id,
            args.repo_name,
            args.pr_url,
            args.pr_state,
            args.pr_merged
        )
    
    elif args.event_type == "status":
        success = test_status_event(
            args.webhook_url,
            args.commit_sha,
            args.ci_status,
            args.repo_name
        )
    
    elif args.event_type == "check_suite":
        success = test_check_suite_event(
            args.webhook_url,
            args.commit_sha,
            args.ci_status,
            args.repo_name
        )
    
    print("-" * 60)
    if success:
        print("✅ 测试完成!")
    else:
        print("❌ 测试失败!")
    print("=" * 60)


if __name__ == "__main__":
    main()

