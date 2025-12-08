import argparse
import json
import random
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

def request(base_url: str, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    url = base_url.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {url} failed ({exc.code}): {body}") from exc

def ensure_active_sprint(base_url: str) -> Dict[str, Any]:
    active = request(base_url, "GET", "/api/sprints/active")
    if active:
        return active
    # Create new if not exists (though usually there is one)
    # For simplicity, assume manual creation or existing one
    raise RuntimeError("No active sprint found. Please start the app properly first.")

def create_story(base_url: str, sprint_id: int, title: str) -> Dict[str, Any]:
    payload = {
        "title": title,
        "description": "Performance test story",
        "story_points": 13,
        "priority": 3,
        "sprint_id": sprint_id,
        "status": "ACTIVE",
    }
    return request(base_url, "POST", "/api/stories", payload)

def create_task(base_url: str, story_id: int, title: str, status: str) -> None:
    payload = {
        "title": title,
        "story_id": story_id,
        "story_points": random.randint(1, 5),
        "status": status,
        "assignee": f"user_{random.randint(1, 5)}",
        "remaining_days": random.randint(1, 10) if status != "DONE" else 0
    }
    request(base_url, "POST", "/api/tasks", payload)

def main():
    parser = argparse.ArgumentParser(description="Seed 500 tasks for performance testing")
    parser.add_argument("--base", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--count", type=int, default=500, help="Number of tasks to create")
    args = parser.parse_args()

    print(f"Connecting to {args.base}...")
    sprint = ensure_active_sprint(args.base)
    print(f"Using Sprint: {sprint['name']} (ID: {sprint['id']})")

    # Create a dedicated story for these tasks
    story = create_story(args.base, sprint["id"], "Performance Test Story (500 Tasks)")
    print(f"Created Story: {story['title']} (ID: {story['id']})")

    print(f"Generating {args.count} tasks...")
    statuses = ["TODO", "IN_PROGRESS", "CODE_REVIEW", "DONE"]
    
    for i in range(args.count):
        status = random.choice(statuses)
        create_task(args.base, story["id"], f"Perf Task {i+1:03d}", status)
        if (i + 1) % 50 == 0:
            print(f"  ... created {i + 1} tasks")

    print("Done! You can now test the frontend performance.")

if __name__ == "__main__":
    main()
