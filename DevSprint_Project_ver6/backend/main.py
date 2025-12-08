import logging
import os
import re
from datetime import date, timedelta, datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker, joinedload

logging.basicConfig(level=logging.INFO)

# 1. 数据库配置
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:123456@localhost:3306/devsprint_db",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 模拟天数偏移（用于前端“模拟天数”按钮，单位：天）
SIMULATION_OFFSET_DAYS = 0


def get_today() -> date:
    return date.today() + timedelta(days=SIMULATION_OFFSET_DAYS)


class SprintStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    CODE_REVIEW = "CODE_REVIEW"
    DONE = "DONE"


class UserStoryStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    DONE = "DONE"


# 2. 定义数据库模型
class SprintModel(Base):
    __tablename__ = "sprints"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    goal = Column(String(500), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), default=SprintStatus.ACTIVE.value)

    stories = relationship(
        "UserStoryModel",
        back_populates="sprint",
        cascade="all, delete-orphan",
    )
    snapshots = relationship(
        "BurndownSnapshotModel",
        back_populates="sprint",
        cascade="all, delete-orphan",
    )


class UserStoryModel(Base):
    __tablename__ = "user_stories"

    id = Column(Integer, primary_key=True, index=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id", ondelete="SET NULL"))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    story_points = Column(Integer, nullable=False)
    priority = Column(Integer, default=3)
    is_tech_debt = Column(Boolean, default=False)
    status = Column(String(20), default=UserStoryStatus.PLANNED.value)

    sprint = relationship("SprintModel", back_populates="stories")
    tasks = relationship(
        "TaskModel",
        back_populates="story",
        cascade="all, delete-orphan",
    )


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("user_stories.id", ondelete="CASCADE"))
    title = Column(String(255), nullable=False)
    status = Column(String(20), default=TaskStatus.TODO.value)
    story_points = Column(Integer, nullable=False)
    is_tech_debt = Column(Boolean, default=False)
    assignee = Column(String(255), nullable=True)
    reviewer = Column(String(255), nullable=True)
    review_started_at = Column(DateTime, nullable=True)
    is_blocked = Column(Boolean, default=False)
    tech_debt_estimate_days = Column(Integer, nullable=True)

    story = relationship("UserStoryModel", back_populates="tasks")
    github_links = relationship(
        "GitHubLinkModel",
        back_populates="task",
        cascade="all, delete-orphan",
    )
    assignments = relationship(
        "TaskAssignmentModel",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class GitHubLinkModel(Base):
    __tablename__ = "github_links"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"))
    commit_hash = Column(String(100), nullable=True)
    pr_url = Column(String(500), nullable=True)
    repo_name = Column(String(255), nullable=True)
    pr_state = Column(String(50), nullable=True)
    pr_merged = Column(Boolean, default=False)
    ci_status = Column(String(50), nullable=True)

    task = relationship("TaskModel", back_populates="github_links")


class TaskAssignmentModel(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"))
    user = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False)
    remaining_days = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="ACTIVE")
    decision = Column(String(20), nullable=True)

    task = relationship("TaskModel", back_populates="assignments")

class BurndownSnapshotModel(Base):
    __tablename__ = "burndown_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id", ondelete="CASCADE"))
    snapshot_date = Column(Date, default=date.today)
    remaining_points = Column(Integer, default=0)

    sprint = relationship("SprintModel", back_populates="snapshots")


class FlowSnapshotModel(Base):
    __tablename__ = "flow_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id", ondelete="CASCADE"))
    snapshot_date = Column(Date, default=date.today)
    todo_count = Column(Integer, default=0)
    in_progress_count = Column(Integer, default=0)
    code_review_count = Column(Integer, default=0)
    done_count = Column(Integer, default=0)


Base.metadata.create_all(bind=engine)


# 3. Pydantic 模型
class GitHubLinkResponse(BaseModel):
    id: int
    commit_hash: Optional[str]
    pr_url: Optional[str]
    repo_name: Optional[str]
    pr_state: Optional[str]
    pr_merged: Optional[bool]
    ci_status: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class TaskAssignmentResponse(BaseModel):
    id: int
    user: Optional[str]
    role: str
    remaining_days: int
    started_at: Optional[datetime]
    status: str
    decision: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class AssignmentBatchCreate(BaseModel):
    users: List[str]
    role: Optional[str] = "DEV"
    remaining_days: int = Field(..., ge=0)

class ReviewDecision(BaseModel):
    approved: bool
    tech_debt_days: Optional[int] = Field(None, ge=0)

class TaskBase(BaseModel):
    title: str
    story_id: int
    story_points: int = Field(..., ge=1)
    status: TaskStatus = TaskStatus.TODO
    is_tech_debt: bool = False
    assignee: Optional[str] = None
    reviewer: Optional[str] = None


class TaskCreate(TaskBase):
    remaining_days: Optional[int] = Field(None, ge=0)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[TaskStatus] = None
    story_points: Optional[int] = Field(None, ge=1)
    is_tech_debt: Optional[bool] = None
    assignee: Optional[str] = None
    reviewer: Optional[str] = None
    is_blocked: Optional[bool] = None
    remaining_days: Optional[int] = Field(None, ge=0)


class TaskResponse(TaskBase):
    id: int
    github_links: List[GitHubLinkResponse] = Field(default_factory=list)
    review_started_at: Optional[datetime] = None
    is_blocked: bool = False
    assignments: List["TaskAssignmentResponse"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class UserStoryBase(BaseModel):
    title: str
    description: Optional[str] = None
    story_points: int = Field(..., ge=1)
    priority: int = Field(ge=1, le=5, default=3)
    is_tech_debt: bool = False
    sprint_id: Optional[int] = None
    status: UserStoryStatus = UserStoryStatus.PLANNED


class UserStoryCreate(UserStoryBase):
    pass


class UserStoryUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    story_points: Optional[int] = Field(None, ge=1)
    priority: Optional[int] = Field(None, ge=1, le=5)
    is_tech_debt: Optional[bool] = None
    sprint_id: Optional[int] = None
    status: Optional[UserStoryStatus] = None


class UserStoryResponse(UserStoryBase):
    id: int
    tasks: List[TaskResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SprintBase(BaseModel):
    name: str
    goal: Optional[str] = None
    start_date: date
    end_date: date
    status: SprintStatus = SprintStatus.ACTIVE


class SprintCreate(SprintBase):
    pass


class SprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[SprintStatus] = None


class SprintResponse(SprintBase):
    id: int
    stories: List[UserStoryResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BurndownPoint(BaseModel):
    day: str
    ideal: float
    actual: Optional[float] = None


class FlowPoint(BaseModel):
    day: str
    todo: int
    in_progress: int
    code_review: int
    done: int

    model_config = ConfigDict(from_attributes=True)


class VelocityPoint(BaseModel):
    sprint_id: int
    sprint_name: str
    start_date: date
    end_date: date
    total_points: int
    completed_points: int


class VelocityResponse(BaseModel):
    points: List[VelocityPoint] = Field(default_factory=list)
    average_velocity: float = 0.0
class WipStatus(BaseModel):
    status: TaskStatus
    count: int
    limit: Optional[int] = None
    breached: bool

    model_config = ConfigDict(from_attributes=True)


class ReviewMetric(BaseModel):
    task_id: int
    waiting_days: int
    sla_days: int
    breached: bool

    model_config = ConfigDict(from_attributes=True)


class DashboardResponse(BaseModel):
    sprint: Optional[SprintResponse] = None
    burndown: List[BurndownPoint] = Field(default_factory=list)
    review_queue: List[TaskResponse] = Field(default_factory=list)
    tech_debt_points: int = 0
    sprint_countdown_days: Optional[int] = None
    wip: List[WipStatus] = Field(default_factory=list)
    review_metrics: List[ReviewMetric] = Field(default_factory=list)
    current_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


# 4. FastAPI 初始化
app = FastAPI(title="DevSprint API", description="Agile Task Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calculate_remaining_points(db: Session, sprint_id: int) -> int:
    remaining = (
        db.query(func.coalesce(func.sum(UserStoryModel.story_points), 0))
        .filter(
            UserStoryModel.sprint_id == sprint_id,
            UserStoryModel.status != UserStoryStatus.DONE.value,
        )
        .scalar()
    )
    return remaining or 0


def build_burndown_payload(
    db: Session, sprint: SprintModel
) -> List[BurndownPoint]:
    if not sprint.start_date or not sprint.end_date:
        return []

    total_days = (sprint.end_date - sprint.start_date).days + 1
    total_days = max(total_days, 1)
    total_points = sum(story.story_points for story in sprint.stories)
    total_points = max(total_points, 0)

    snapshots = (
        db.query(BurndownSnapshotModel)
        .filter(BurndownSnapshotModel.sprint_id == sprint.id)
        .order_by(BurndownSnapshotModel.snapshot_date)
        .all()
    )
    snapshot_map: Dict[date, int] = {
        snap.snapshot_date: snap.remaining_points for snap in snapshots
    }

    current_day = sprint.start_date
    last_actual = total_points
    burndown_points: List[BurndownPoint] = []
    today = get_today()

    for index in range(total_days):
        ideal_remaining = total_points - (
            index * total_points / max(total_days - 1, 1)
        )
        if current_day in snapshot_map:
            last_actual = snapshot_map[current_day]
        
        # 只显示到今天（含）的实际数据
        actual_value = max(last_actual, 0) if current_day <= today else None

        burndown_points.append(
            BurndownPoint(
                day=f"Day {index + 1}",
                ideal=max(ideal_remaining, 0),
                actual=actual_value,
            )
        )
        current_day = current_day + timedelta(days=1)

    if burndown_points and not snapshots and sprint.start_date <= today:
        # 如果尚未生成快照且在Sprint范围内，则使用实时剩余点数填充
        # 注意：这可能会覆盖掉上面的 None，如果是未来的话不应该覆盖，但在 start_date <= today 条件下是安全的
        idx = (today - sprint.start_date).days
        if 0 <= idx < len(burndown_points):
             burndown_points[idx].actual = calculate_remaining_points(db, sprint.id)

    return burndown_points


def sync_story_status(db: Session, story: UserStoryModel) -> None:
    if not story.tasks:
        return
    if all(task.status == TaskStatus.DONE.value for task in story.tasks):
        story.status = UserStoryStatus.DONE.value
    elif any(task.status in (TaskStatus.IN_PROGRESS.value, TaskStatus.CODE_REVIEW.value) for task in story.tasks):
        story.status = UserStoryStatus.ACTIVE.value
    else:
        story.status = UserStoryStatus.PLANNED.value


def link_commit_to_task(
    db: Session, task: TaskModel, commit_hash: str, repo_name: Optional[str]
):
    link = GitHubLinkModel(
        task_id=task.id,
        commit_hash=commit_hash,
        repo_name=repo_name,
    )
    db.add(link)


def link_pr_to_task(
    db: Session, task: TaskModel, pr_url: str, repo_name: Optional[str]
):
    link = GitHubLinkModel(
        task_id=task.id,
        pr_url=pr_url,
        repo_name=repo_name,
    )
    task.status = TaskStatus.CODE_REVIEW.value
    reviewers = [r.strip() for r in (os.getenv("DEVSPRINT_REVIEWERS", "").split(",")) if r.strip()]
    if reviewers:
        task.review_started_at = datetime.utcnow()
        sla = _env_int("DEVSPRINT_REVIEW_SLA_DAYS", 2) or 2
        for r in reviewers:
            db.add(
                TaskAssignmentModel(
                    task_id=task.id,
                    user=r,
                    role="REVIEW",
                    remaining_days=max(0, sla),
                    started_at=datetime.utcnow(),
                    status="ACTIVE",
                )
            )
    db.add(link)


# 5. API - Sprint & Story
@app.post("/api/sprints", response_model=SprintResponse)
def create_sprint(payload: SprintCreate, db: Session = Depends(get_db)):
    sprint = SprintModel(**payload.dict())
    if sprint.end_date < sprint.start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint


@app.get("/api/sprints", response_model=List[SprintResponse])
def list_sprints(db: Session = Depends(get_db)):
    return db.query(SprintModel).all()


@app.get("/api/sprints/active", response_model=Optional[SprintResponse])
def get_active_sprint(db: Session = Depends(get_db)):
    return (
        db.query(SprintModel)
        .filter(SprintModel.status == SprintStatus.ACTIVE.value)
        .order_by(SprintModel.start_date)
        .first()
    )


@app.patch("/api/sprints/{sprint_id}", response_model=SprintResponse)
def update_sprint(
    sprint_id: int, payload: SprintUpdate, db: Session = Depends(get_db)
):
    sprint = db.get(SprintModel, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(sprint, key, value)
    if sprint.end_date < sprint.start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    db.commit()
    db.refresh(sprint)
    return sprint


@app.post("/api/stories", response_model=UserStoryResponse)
def create_story(payload: UserStoryCreate, db: Session = Depends(get_db)):
    if payload.sprint_id:
        sprint = db.get(SprintModel, payload.sprint_id)
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")
    story = UserStoryModel(**payload.dict())
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


@app.patch("/api/stories/{story_id}", response_model=UserStoryResponse)
def update_story(
    story_id: int, payload: UserStoryUpdate, db: Session = Depends(get_db)
):
    story = db.get(UserStoryModel, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    update_data = payload.dict(exclude_unset=True)
    if "sprint_id" in update_data and update_data["sprint_id"]:
        sprint = db.get(SprintModel, update_data["sprint_id"])
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")
    for key, value in update_data.items():
        setattr(story, key, value)
    db.commit()
    db.refresh(story)
    return story


@app.get("/api/stories/{story_id}", response_model=UserStoryResponse)
def get_story(story_id: int, db: Session = Depends(get_db)):
    story = db.get(UserStoryModel, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


# 6. API - Task
@app.get("/api/tasks", response_model=List[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(TaskModel).all()


@app.post("/api/tasks", response_model=TaskResponse)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    story = db.get(UserStoryModel, payload.story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    task_data = payload.dict()
    remaining_days = task_data.pop("remaining_days", None)
    task = TaskModel(**task_data)
    db.add(task)
    db.flush()
    # 如果有assignee和remaining_days（包括0），创建TaskAssignment
    if task.assignee and remaining_days is not None:
        assignment = TaskAssignmentModel(
            task_id=task.id,
            user=task.assignee,
            role="DEV",
            remaining_days=max(0, remaining_days),
            started_at=datetime.utcnow(),
            status="ACTIVE",
        )
        db.add(assignment)
    db.commit()
    db.refresh(task)
    sync_story_status(db, story)
    db.commit()
    db.refresh(task)
    return task


@app.patch("/api/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = payload.dict(exclude_unset=True)
    remaining_days = update_data.pop("remaining_days", None)
    
    # 更新任务基本字段
    old_assignee = task.assignee
    for key, value in update_data.items():
        setattr(task, key, value)
    
    # 如果 assignee 发生了变化，关闭旧的 assignment
    if "assignee" in update_data and old_assignee != task.assignee:
        old_assignments = (
            db.query(TaskAssignmentModel)
            .filter(
                TaskAssignmentModel.task_id == task_id,
                TaskAssignmentModel.role == "DEV",
                TaskAssignmentModel.status == "ACTIVE"
            )
            .all()
        )
        for assign in old_assignments:
            if assign.user != task.assignee:
                assign.status = "DONE"
                assign.remaining_days = 0

    # 处理 remaining_days 更新或新 assignee 的 assignment 创建
    if remaining_days is not None or ("assignee" in update_data and task.assignee):
        # 获取或创建当前 assignee 的 DEV assignment
        if task.assignee:
            dev_assignment = (
                db.query(TaskAssignmentModel)
                .filter(
                    TaskAssignmentModel.task_id == task_id,
                    TaskAssignmentModel.role == "DEV",
                    TaskAssignmentModel.status == "ACTIVE",
                    TaskAssignmentModel.user == task.assignee
                )
                .first()
            )
            if dev_assignment:
                if remaining_days is not None:
                    dev_assignment.remaining_days = max(0, remaining_days)
            else:
                # 创建新的assignment
                # 如果没有提供 remaining_days，尝试使用旧值或默认值
                days_to_set = remaining_days if remaining_days is not None else 1
                db.add(
                    TaskAssignmentModel(
                        task_id=task_id,
                        user=task.assignee,
                        role="DEV",
                        remaining_days=max(0, days_to_set),
                        started_at=datetime.utcnow(),
                        status="ACTIVE",
                    )
                )
    
    db.commit()
    db.refresh(task)
    if task.story:
        sync_story_status(db, task.story)
        db.commit()
        db.refresh(task)
    return task


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    story = task.story
    db.delete(task)
    db.commit()
    if story:
        sync_story_status(db, story)
        db.commit()
    return None

@app.post("/api/admin/clear_board")
def clear_board(db: Session = Depends(get_db)):
    sprint = (
        db.query(SprintModel)
        .filter(SprintModel.status == SprintStatus.ACTIVE.value)
        .order_by(SprintModel.start_date)
        .first()
    )
    if not sprint:
        raise HTTPException(status_code=404, detail="No active sprint found")
    stories = (
        db.query(UserStoryModel)
        .filter(UserStoryModel.sprint_id == sprint.id)
        .all()
    )
    deleted_tasks = 0
    deleted_stories = 0
    for st in stories:
        deleted_tasks += len(st.tasks)
        db.delete(st)
        deleted_stories += 1
    
    # 额外清理：确保清理所有属于该 Sprint 的任务（即使由于某种原因未被级联删除）
    # 并清理可能存在的未关联 Story 但逻辑上属于该 Sprint 的孤儿任务（如果有 story_id 指向该 Sprint 的 Story）
    # 注意：上面的 db.delete(st) 应该已经处理了大部分，这里是双重保险
    
    # 清理快照
    db.query(BurndownSnapshotModel).filter(BurndownSnapshotModel.sprint_id == sprint.id).delete()
    db.query(FlowSnapshotModel).filter(FlowSnapshotModel.sprint_id == sprint.id).delete()
    db.commit()
    return {"deleted_stories": deleted_stories, "deleted_tasks": deleted_tasks, "sprint_id": sprint.id}

@app.get("/api/tasks/{task_id}/assignments", response_model=List[TaskAssignmentResponse])
def list_assignments(task_id: int, db: Session = Depends(get_db)):
    task = db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return db.query(TaskAssignmentModel).filter(TaskAssignmentModel.task_id == task_id).all()

@app.post("/api/tasks/{task_id}/assignments", response_model=List[TaskAssignmentResponse])
def create_assignments(task_id: int, payload: AssignmentBatchCreate, db: Session = Depends(get_db)):
    task = db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    created: List[TaskAssignmentModel] = []
    for u in payload.users:
        a = TaskAssignmentModel(
            task_id=task_id,
            user=u,
            role=payload.role or "DEV",
            remaining_days=max(0, payload.remaining_days),
            started_at=datetime.utcnow(),
            status="ACTIVE",
        )
        db.add(a)
        created.append(a)
    db.commit()
    return created

@app.post("/api/review/{task_id}/decision", response_model=TaskResponse)
def review_decision(task_id: int, payload: ReviewDecision, db: Session = Depends(get_db)):
    task = db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    reviews = db.query(TaskAssignmentModel).filter(TaskAssignmentModel.task_id == task_id, TaskAssignmentModel.role == "REVIEW", TaskAssignmentModel.status == "ACTIVE").all()
    if payload.approved:
        for a in reviews:
            a.decision = "APPROVED"
            a.status = "DONE"
        all_done = db.query(TaskAssignmentModel).filter(TaskAssignmentModel.task_id == task_id, TaskAssignmentModel.role == "REVIEW").all()
        if all(all_a.decision == "APPROVED" for all_a in all_done):
            task.status = TaskStatus.DONE.value
            if task.story:
                sync_story_status(db, task.story)
    else:
        for a in reviews:
            a.decision = "REJECTED"
            a.status = "DONE"
        task.is_tech_debt = True
        task.tech_debt_estimate_days = max(0, payload.tech_debt_days or 1)
        task.status = TaskStatus.IN_PROGRESS.value
        if task.assignee:
            # 检查是否已有该用户的DEV assignment
            existing_dev_assignment = (
                db.query(TaskAssignmentModel)
                .filter(
                    TaskAssignmentModel.task_id == task_id,
                    TaskAssignmentModel.user == task.assignee,
                    TaskAssignmentModel.role == "DEV"
                )
                .first()
            )
            if existing_dev_assignment:
                # 更新现有的assignment，重置为ACTIVE状态并设置新的剩余天数
                existing_dev_assignment.status = "ACTIVE"
                existing_dev_assignment.remaining_days = task.tech_debt_estimate_days or 1
                existing_dev_assignment.started_at = datetime.utcnow()
                existing_dev_assignment.decision = None
            else:
                # 如果没有，创建新的assignment
                db.add(TaskAssignmentModel(task_id=task_id, user=task.assignee, role="DEV", remaining_days=task.tech_debt_estimate_days or 1, started_at=datetime.utcnow(), status="ACTIVE"))
        if task.story:
            sync_story_status(db, task.story)
    db.commit()
    db.refresh(task)
    return task


# 7. API - GitHub 集成
commit_ref_pattern = re.compile(r"ref\s+#(\d+)", re.IGNORECASE)


@app.post("/api/github/webhook")
def github_webhook(payload: dict = Body(...), db: Session = Depends(get_db)):
    repo_name = payload.get("repository", {}).get("full_name")
    processed_tasks: List[int] = []

    for commit in payload.get("commits", []):
        message = commit.get("message", "")
        for match in commit_ref_pattern.findall(message):
            task = db.get(TaskModel, int(match))
            if task:
                link_commit_to_task(db, task, commit.get("id"), repo_name)
                processed_tasks.append(task.id)

    pull_request = payload.get("pull_request")
    if pull_request:
        text = f"{pull_request.get('title', '')}\n{pull_request.get('body', '')}"
        pr_url = pull_request.get("html_url")
        pr_state = pull_request.get("state")
        pr_merged = bool(pull_request.get("merged"))
        for match in commit_ref_pattern.findall(text):
            task = db.get(TaskModel, int(match))
            if task:
                link_pr_to_task(db, task, pr_url, repo_name)
                last_link = (
                    db.query(GitHubLinkModel)
                    .filter(GitHubLinkModel.task_id == task.id, GitHubLinkModel.pr_url == pr_url)
                    .order_by(GitHubLinkModel.id.desc())
                    .first()
                )
                if last_link:
                    last_link.pr_state = pr_state
                    last_link.pr_merged = pr_merged
                processed_tasks.append(task.id)

    status_payload = payload.get("status") or payload.get("check_suite")
    if status_payload:
        state = status_payload.get("state") or status_payload.get("conclusion")
        sha = status_payload.get("sha") or status_payload.get("head_sha")
        if sha and state:
            gh_links = (
                db.query(GitHubLinkModel)
                .filter(GitHubLinkModel.commit_hash == sha)
                .all()
            )
            for link in gh_links:
                link.ci_status = state
                task = db.get(TaskModel, link.task_id)
                if task and str(state).lower() in {"failure", "failed", "error"}:
                    task.is_blocked = True
    db.commit()

    return {"linked_tasks": processed_tasks}


# 8. API - 燃尽图与仪表盘
@app.get("/api/burndown/{sprint_id}", response_model=List[BurndownPoint])
def get_burndown(sprint_id: int, db: Session = Depends(get_db)):
    sprint = db.get(SprintModel, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return build_burndown_payload(db, sprint)


@app.get("/api/cfd/{sprint_id}", response_model=List[FlowPoint])
def get_cfd(sprint_id: int, db: Session = Depends(get_db)):
    sprint = db.get(SprintModel, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    snapshots = (
        db.query(FlowSnapshotModel)
        .filter(FlowSnapshotModel.sprint_id == sprint_id)
        .order_by(FlowSnapshotModel.snapshot_date)
        .all()
    )
    points: List[FlowPoint] = []
    for idx, snap in enumerate(snapshots):
        points.append(
            FlowPoint(
                day=f"Day {idx + 1}",
                todo=snap.todo_count,
                in_progress=snap.in_progress_count,
                code_review=snap.code_review_count,
                done=snap.done_count,
            )
        )
    return points


@app.get("/api/velocity", response_model=VelocityResponse)
def get_velocity(db: Session = Depends(get_db)):
    sprints = db.query(SprintModel).order_by(SprintModel.start_date).all()
    points: List[VelocityPoint] = []
    for sp in sprints:
        total_points = (
            db.query(func.coalesce(func.sum(TaskModel.story_points), 0))
            .join(UserStoryModel)
            .filter(UserStoryModel.sprint_id == sp.id)
            .scalar()
        ) or 0
        completed_points = (
            db.query(func.coalesce(func.sum(TaskModel.story_points), 0))
            .join(UserStoryModel)
            .filter(UserStoryModel.sprint_id == sp.id, TaskModel.status == TaskStatus.DONE.value)
            .scalar()
        ) or 0
        points.append(
            VelocityPoint(
                sprint_id=sp.id,
                sprint_name=sp.name,
                start_date=sp.start_date,
                end_date=sp.end_date,
                total_points=total_points,
                completed_points=completed_points,
            )
        )
    closed = [p.completed_points for p in points if any([True if sp.status == SprintStatus.CLOSED.value else False for sp in sprints if sp.id == p.sprint_id])]
    avg = float(sum(closed) / len(closed)) if closed else 0.0
    return VelocityResponse(points=points, average_velocity=avg)
@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    sprint = (
        db.query(SprintModel)
        .options(joinedload(SprintModel.stories))
        .filter(SprintModel.status == SprintStatus.ACTIVE.value)
        .order_by(SprintModel.start_date)
        .first()
    )
    burndown: List[BurndownPoint] = []
    tech_debt_points = 0
    countdown = None
    wip: List[WipStatus] = []
    if sprint:
        burndown = build_burndown_payload(db, sprint)
        tech_debt_points = (
            db.query(func.coalesce(func.sum(TaskModel.story_points), 0))
            .join(UserStoryModel)
            .filter(
                UserStoryModel.sprint_id == sprint.id,
                TaskModel.is_tech_debt == True,
                TaskModel.status != TaskStatus.DONE.value,
            )
            .scalar()
        ) or 0
        countdown = (sprint.end_date - get_today()).days

    review_queue = []
    if sprint:
        review_queue = (
            db.query(TaskModel)
            .join(UserStoryModel)
            .filter(
                TaskModel.status == TaskStatus.CODE_REVIEW.value,
                UserStoryModel.sprint_id == sprint.id
            )
            .all()
        )
    
    wip_counts: Dict[str, int] = {}
    if sprint:
        for s in TaskStatus:
            wip_counts[s.value] = (
                db.query(func.count(TaskModel.id))
                .join(UserStoryModel)
                .filter(
                    TaskModel.status == s.value,
                    UserStoryModel.sprint_id == sprint.id
                )
                .scalar()
            ) or 0
    else:
        # 如果没有活跃 Sprint，WIP 计数应为 0
        for s in TaskStatus:
            wip_counts[s.value] = 0

    limits_map: Dict[str, Optional[int]] = {
        TaskStatus.TODO.value: _env_int("DEVSPRINT_WIP_TODO", None),
        TaskStatus.IN_PROGRESS.value: _env_int("DEVSPRINT_WIP_IN_PROGRESS", 3),
        TaskStatus.CODE_REVIEW.value: _env_int("DEVSPRINT_WIP_CODE_REVIEW", 2),
        TaskStatus.DONE.value: _env_int("DEVSPRINT_WIP_DONE", None),
    }
    for key in [
        TaskStatus.TODO.value,
        TaskStatus.IN_PROGRESS.value,
        TaskStatus.CODE_REVIEW.value,
        TaskStatus.DONE.value,
    ]:
        count = wip_counts.get(key, 0)
        limit = limits_map.get(key)
        breached = limit is not None and count > limit
        wip.append(
            WipStatus(status=TaskStatus(key), count=count, limit=limit, breached=breached)
        )

    sla_days = _env_int("DEVSPRINT_REVIEW_SLA_DAYS", 2) or 2
    review_metrics: List[ReviewMetric] = []
    today = get_today()
    for t in review_queue:
        if t.review_started_at:
            waiting_days = max(0, (today - t.review_started_at.date()).days)
            breached = waiting_days > sla_days
            review_metrics.append(
                ReviewMetric(task_id=t.id, waiting_days=waiting_days, sla_days=sla_days, breached=breached)
            )

    return DashboardResponse(
        sprint=sprint,
        burndown=burndown,
        review_queue=review_queue,
        tech_debt_points=tech_debt_points,
        sprint_countdown_days=countdown,
        wip=wip,
        review_metrics=review_metrics,
        current_date=get_today(),
    )


# 9. 轮询任务：GitHub 同步 & 燃尽记录
def capture_burndown_snapshots(for_date: Optional[date] = None):
    db = SessionLocal()
    try:
        target_date = for_date or get_today()
        active_sprints = (
            db.query(SprintModel)
            .filter(SprintModel.status == SprintStatus.ACTIVE.value)
            .all()
        )
        for sprint in active_sprints:
            remaining = calculate_remaining_points(db, sprint.id)
            snapshot = (
                db.query(BurndownSnapshotModel)
                .filter(
                    BurndownSnapshotModel.sprint_id == sprint.id,
                    BurndownSnapshotModel.snapshot_date == target_date,
                )
                .first()
            )
            if snapshot:
                snapshot.remaining_points = remaining
            else:
                db.add(
                    BurndownSnapshotModel(
                        sprint_id=sprint.id,
                        snapshot_date=target_date,
                        remaining_points=remaining,
                    )
                )
            todo_count = (
                db.query(func.count(TaskModel.id))
                .join(UserStoryModel)
                .filter(
                    TaskModel.status == TaskStatus.TODO.value,
                    UserStoryModel.sprint_id == sprint.id,
                )
                .scalar()
            ) or 0
            in_progress_count = (
                db.query(func.count(TaskModel.id))
                .join(UserStoryModel)
                .filter(
                    TaskModel.status == TaskStatus.IN_PROGRESS.value,
                    UserStoryModel.sprint_id == sprint.id,
                )
                .scalar()
            ) or 0
            code_review_count = (
                db.query(func.count(TaskModel.id))
                .join(UserStoryModel)
                .filter(
                    TaskModel.status == TaskStatus.CODE_REVIEW.value,
                    UserStoryModel.sprint_id == sprint.id,
                )
                .scalar()
            ) or 0
            done_count = (
                db.query(func.count(TaskModel.id))
                .join(UserStoryModel)
                .filter(
                    TaskModel.status == TaskStatus.DONE.value,
                    UserStoryModel.sprint_id == sprint.id,
                )
                .scalar()
            ) or 0
            flow = (
                db.query(FlowSnapshotModel)
                .filter(
                    FlowSnapshotModel.sprint_id == sprint.id,
                    FlowSnapshotModel.snapshot_date == target_date,
                )
                .first()
            )
            if flow:
                flow.todo_count = todo_count
                flow.in_progress_count = in_progress_count
                flow.code_review_count = code_review_count
                flow.done_count = done_count
            else:
                db.add(
                    FlowSnapshotModel(
                        sprint_id=sprint.id,
                        snapshot_date=target_date,
                        todo_count=todo_count,
                        in_progress_count=in_progress_count,
                        code_review_count=code_review_count,
                        done_count=done_count,
                    )
                )
        db.commit()
    except Exception as exc:
        logging.exception("Failed to capture burndown snapshots: %s", exc)
        db.rollback()
    finally:
        db.close()


def poll_github_updates():
    # 这里可以扩展调用 GitHub API，同步最新 commit/PR
    logging.info("GitHub polling executed - integrate with GitHub API here.")


def simulate_progress(db: Session) -> None:
    sprint = (
        db.query(SprintModel)
        .filter(SprintModel.status == SprintStatus.ACTIVE.value)
        .order_by(SprintModel.start_date)
        .first()
    )
    if not sprint:
        return

    def pick_task(status: TaskStatus):
        return (
            db.query(TaskModel)
            .join(UserStoryModel)
            .filter(
                TaskModel.status == status.value,
                UserStoryModel.sprint_id == sprint.id,
            )
            .order_by(TaskModel.is_tech_debt.desc(), TaskModel.id)
            .first()
        )

    def ensure_tech_debt_story() -> UserStoryModel:
        td_story = (
            db.query(UserStoryModel)
            .filter(
                UserStoryModel.sprint_id == sprint.id,
                UserStoryModel.is_tech_debt == True,
            )
            .order_by(UserStoryModel.priority, UserStoryModel.id)
            .first()
        )
        if td_story:
            return td_story
        td_story = UserStoryModel(
            sprint_id=sprint.id,
            title="技术债务集中处理",
            description="- 自动生成的技术债务故事\n- 清理告警与代码异味",
            story_points=5,
            priority=1,
            is_tech_debt=True,
        )
        db.add(td_story)
        db.flush()
        return td_story

    def ensure_tech_debt_task():
        td_story = ensure_tech_debt_story()
        task = TaskModel(
            story_id=td_story.id,
            title="处理技术债务项",
            status=TaskStatus.TODO.value,
            story_points=2,
            is_tech_debt=True,
            assignee=None,
        )
        db.add(task)
        db.flush()
        return task

    active_tasks = (
        db.query(TaskModel)
        .join(UserStoryModel)
        .filter(UserStoryModel.sprint_id == sprint.id, TaskModel.status != TaskStatus.DONE.value)
        .all()
    )
    for t in active_tasks:
        # 对于TODO和IN_PROGRESS状态的任务，更新所有DEV assignment的剩余天数
        if t.status in (TaskStatus.TODO.value, TaskStatus.IN_PROGRESS.value):
            all_dev_assigns = db.query(TaskAssignmentModel).filter(
                TaskAssignmentModel.task_id == t.id,
                TaskAssignmentModel.role == "DEV"
            ).all()
            
            # 如果没有DEV assignment但有assignee，尝试创建或查找一个
            if not all_dev_assigns and t.assignee:
                # 检查是否有任何DEV assignment（包括非ACTIVE状态的）
                existing_assignment = db.query(TaskAssignmentModel).filter(
                    TaskAssignmentModel.task_id == t.id,
                    TaskAssignmentModel.role == "DEV",
                    TaskAssignmentModel.user == t.assignee
                ).first()
                
                if existing_assignment:
                    # 如果存在非ACTIVE的assignment，将其激活
                    existing_assignment.status = "ACTIVE"
                    if existing_assignment.remaining_days is None:
                        # 如果没有剩余天数，设置一个默认值（基于技术债务估计或默认1天）
                        existing_assignment.remaining_days = t.tech_debt_estimate_days if t.tech_debt_estimate_days else 1
                    all_dev_assigns = [existing_assignment]
                else:
                    # 创建新的assignment，使用技术债务估计天数或默认1天
                    new_assignment = TaskAssignmentModel(
                        task_id=t.id,
                        user=t.assignee,
                        role="DEV",
                        remaining_days=t.tech_debt_estimate_days if t.tech_debt_estimate_days else 1,
                        started_at=datetime.utcnow(),
                        status="ACTIVE",
                    )
                    db.add(new_assignment)
                    db.flush()  # 刷新以获取ID并确保可以查询
                    all_dev_assigns = [new_assignment]
            
            # 更新所有DEV assignment的剩余天数（无论任务状态是TODO还是IN_PROGRESS）
            # 如果查询结果为空，但任务有assignee，刷新任务对象并重新查询
            if not all_dev_assigns and t.assignee:
                # 先刷新任务对象，确保获取最新的关联数据
                db.refresh(t)
                # 重新查询，这次查询所有状态的assignment（不仅限于ACTIVE）
                all_dev_assigns = db.query(TaskAssignmentModel).filter(
                    TaskAssignmentModel.task_id == t.id,
                    TaskAssignmentModel.role == "DEV"
                ).all()
                # 如果仍然找不到，但任务确实有assignee，可能是数据不一致，已在上面创建
            
            if all_dev_assigns:
                for a in all_dev_assigns:
                    # 更新所有有剩余天数的assignment（包括非技术债务任务）
                    if a.remaining_days is not None and a.remaining_days > 0:
                        a.remaining_days = max(0, a.remaining_days - 1)
                        if a.remaining_days == 0 and a.status == "ACTIVE":
                            a.status = "DONE"
                    # 如果剩余天数为None，但assignment存在，说明可能需要设置初始值
                    elif a.remaining_days is None:
                        # 如果没有剩余天数但有技术债务估计，使用它
                        if t.tech_debt_estimate_days:
                            a.remaining_days = max(0, t.tech_debt_estimate_days - 1)
                        # 否则保持None，不更新
        
        # 对于CODE_REVIEW状态的任务，更新所有REVIEW assignment的剩余天数（只要剩余天数>0）
        if t.status == TaskStatus.CODE_REVIEW.value:
            all_review_assigns = db.query(TaskAssignmentModel).filter(
                TaskAssignmentModel.task_id == t.id,
                TaskAssignmentModel.role == "REVIEW"
            ).all()
            for a in all_review_assigns:
                # 只更新剩余天数>0的assignment
                if a.remaining_days is not None and a.remaining_days > 0:
                    a.remaining_days = max(0, a.remaining_days - 1)
        
        # 检查剩余天数并自动移动状态
        if t.status == TaskStatus.TODO.value:
            # 查询所有DEV assignment
            dev_all = db.query(TaskAssignmentModel).filter(TaskAssignmentModel.task_id == t.id, TaskAssignmentModel.role == "DEV").all()
            # 如果有ACTIVE的DEV assignment，移动到IN_PROGRESS
            active_dev_assigns = [a for a in dev_all if a.status == "ACTIVE"]
            if active_dev_assigns:
                t.status = TaskStatus.IN_PROGRESS.value
                if t.story:
                    sync_story_status(db, t.story)
            # 或者如果有剩余天数<=0的DEV assignment，也移动到IN_PROGRESS
            elif dev_all and any((a.remaining_days is not None and a.remaining_days <= 0) or a.status == "DONE" for a in dev_all):
                t.status = TaskStatus.IN_PROGRESS.value
                if t.story:
                    sync_story_status(db, t.story)
        
        if t.status == TaskStatus.IN_PROGRESS.value:
            # 如果所有DEV assignment都完成了（剩余天数<=0或status==DONE），移动到CODE_REVIEW
            dev_all = db.query(TaskAssignmentModel).filter(TaskAssignmentModel.task_id == t.id, TaskAssignmentModel.role == "DEV").all()
            if dev_all and all((a.remaining_days is not None and a.remaining_days <= 0) or a.status == "DONE" for a in dev_all):
                t.status = TaskStatus.CODE_REVIEW.value
                t.review_started_at = datetime.utcnow()
                if t.story:
                    sync_story_status(db, t.story)
        
        if t.status == TaskStatus.CODE_REVIEW.value:
            # 如果所有REVIEW assignment都完成了，移动到DONE（只有当所有review都approved时）
            review_all = db.query(TaskAssignmentModel).filter(TaskAssignmentModel.task_id == t.id, TaskAssignmentModel.role == "REVIEW").all()
            if review_all and all((a.remaining_days is not None and a.remaining_days <= 0) or a.status == "DONE" for a in review_all):
                # 只有当所有review都approved时才移动到DONE
                if all(a.decision == "APPROVED" for a in review_all if a.decision):
                    t.status = TaskStatus.DONE.value
                    if t.story:
                        sync_story_status(db, t.story)
    if not active_tasks:
        new_td = ensure_tech_debt_task()
    db.commit()


scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "UTC"))
scheduler.add_job(capture_burndown_snapshots, "cron", hour=0, minute=0)
scheduler.add_job(poll_github_updates, "interval", minutes=10)


def _env_flag(name: str, default: str = "1") -> bool:
    value = os.getenv(name, default)
    return value is not None and value.lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: Optional[int] = None) -> Optional[int]:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default

def seed_demo_data(db: Session) -> None:
    if db.query(TaskModel).count() > 0:
        logging.info("Demo data seeding skipped: tasks already exist.")
        return

    demo_repo = os.getenv("DEVSPRINT_DEMO_REPO", "octocat/Hello-World")
    demo_pr_url = os.getenv(
        "DEVSPRINT_DEMO_PR_URL", "https://github.com/octocat/Hello-World/pull/1"
    )
    demo_commit_hash = os.getenv(
        "DEVSPRINT_DEMO_COMMIT", "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3"
    )

    today = get_today()
    sprint = SprintModel(
        name=f"Sprint {today.isoformat()}",
        goal="交付核心功能并完成技术债务收敛",
        start_date=today,
        end_date=today + timedelta(days=7),
        status=SprintStatus.ACTIVE.value,
    )
    db.add(sprint)
    db.flush()

    story_defs = [
        {
            "title": "登录与权限收敛",
            "description": "- 支持企业 SSO\n- 登录失败时记录审计日志\n- 梳理角色权限矩阵",
            "story_points": 8,
            "priority": 1,
            "tasks": [
                {
                    "title": "实现基础登录接口",
                    "story_points": 3,
                    "status": TaskStatus.IN_PROGRESS.value,
                    "assignee": "alice",
                },
                {
                    "title": "接入 OAuth2 SSO",
                    "story_points": 3,
                    "status": TaskStatus.TODO.value,
                    "assignee": "bob",
                },
                {
                    "title": "安全扫描遗留项修复",
                    "story_points": 2,
                    "status": TaskStatus.TODO.value,
                    "is_tech_debt": True,
                    "assignee": "alice",
                },
            ],
        },
        {
            "title": "团队看板体验提升",
            "description": "- Story 支持 Markdown 展示\n- 优化列内排序与快捷操作\n- 可见性分组与筛选",
            "story_points": 7,
            "priority": 2,
            "tasks": [
                {
                    "title": "支持 Story Markdown 渲染",
                    "story_points": 2,
                    "status": TaskStatus.DONE.value,
                    "assignee": "carol",
                },
                {
                    "title": "看板列内拖拽排序",
                    "story_points": 3,
                    "status": TaskStatus.TODO.value,
                    "assignee": "dave",
                },
                {
                    "title": "为技术债务卡片增加高亮",
                    "story_points": 2,
                    "status": TaskStatus.CODE_REVIEW.value,
                    "is_tech_debt": True,
                    "assignee": "carol",
                },
            ],
        },
        {
            "title": "持续交付与发布安全",
            "description": "- 部署前置健康检查\n- 增加缓存与并行策略\n- 回滚脚本自动化",
            "story_points": 9,
            "priority": 1,
            "tasks": [
                {
                    "title": "流水线缓存与并行优化",
                    "story_points": 4,
                    "status": TaskStatus.IN_PROGRESS.value,
                    "assignee": "erin",
                },
                {
                    "title": "部署前烟囱检查",
                    "story_points": 3,
                    "status": TaskStatus.CODE_REVIEW.value,
                    "assignee": "frank",
                },
                {
                    "title": "回滚脚本与演练手册",
                    "story_points": 2,
                    "status": TaskStatus.TODO.value,
                    "assignee": "erin",
                },
            ],
        },
        {
            "title": "监控告警闭环",
            "description": "- 建立关键 SLI/SLO\n- 引入告警抑制策略\n- 报警可观测性面板",
            "story_points": 6,
            "priority": 3,
            "tasks": [
                {
                    "title": "核心 API SLO 定义与仪表盘",
                    "story_points": 3,
                    "status": TaskStatus.DONE.value,
                    "assignee": "grace",
                },
                {
                    "title": "告警抑制与值班转派规则",
                    "story_points": 3,
                    "status": TaskStatus.TODO.value,
                    "assignee": "heidi",
                },
            ],
        },
    ]

    for story_def in story_defs:
        story = UserStoryModel(
            sprint_id=sprint.id,
            title=story_def["title"],
            description=story_def["description"],
            story_points=story_def["story_points"],
            priority=story_def.get("priority", 3),
            is_tech_debt=story_def.get("is_tech_debt", False),
        )
        db.add(story)
        db.flush()
        for task_def in story_def["tasks"]:
            task = TaskModel(
                story_id=story.id,
                title=task_def["title"],
                status=task_def["status"],
                story_points=task_def["story_points"],
                is_tech_debt=task_def.get("is_tech_debt", False),
                assignee=task_def.get("assignee"),
            )
            db.add(task)
            if task.status == TaskStatus.CODE_REVIEW.value:
                db.flush()
                db.add(
                    GitHubLinkModel(
                        task_id=task.id,
                        pr_url=demo_pr_url,
                        repo_name=demo_repo,
                        commit_hash=demo_commit_hash,
                    )
                )
        sync_story_status(db, story)

    db.commit()
    capture_burndown_snapshots()
    logging.info("Demo data seeded: sprint=%s, stories=%d", sprint.name, len(story_defs))
    # 生成今天的快照
    capture_burndown_snapshots(get_today())


@app.post("/api/simulate/advance_days")
def simulate_advance_days(days: int = Body(..., embed=True)) -> Dict[str, Union[int, str]]:
    if days <= 0:
        raise HTTPException(status_code=400, detail="Days must be positive")
    global SIMULATION_OFFSET_DAYS
    created = 0
    db = SessionLocal()
    try:
        for _ in range(days):
            SIMULATION_OFFSET_DAYS += 1
            simulate_date = get_today()
            simulate_progress(db)
            capture_burndown_snapshots(simulate_date)
            created += 1
    finally:
        db.close()
    return {
        "created_snapshots": created,
        "last_date": simulate_date.isoformat(),
        "current_day": get_today().isoformat(),
        "offset_days": SIMULATION_OFFSET_DAYS,
    }


@app.post("/api/simulate/set_remaining_days")
def simulate_set_remaining_days(
    remaining_days: int = Body(..., embed=True),
) -> Dict[str, Union[int, str]]:
    if remaining_days < 0:
        raise HTTPException(status_code=400, detail="Remaining days must be non-negative")

    global SIMULATION_OFFSET_DAYS
    db = SessionLocal()
    try:
        sprint = (
            db.query(SprintModel)
            .filter(SprintModel.status == SprintStatus.ACTIVE.value)
            .order_by(SprintModel.start_date)
            .first()
        )
        if not sprint:
            raise HTTPException(status_code=404, detail="No active sprint found")

        base_remaining = (sprint.end_date - date.today()).days
        SIMULATION_OFFSET_DAYS = base_remaining - remaining_days
        snapshot_date = get_today()
        capture_burndown_snapshots(snapshot_date)
        return {
            "current_day": snapshot_date.isoformat(),
            "offset_days": SIMULATION_OFFSET_DAYS,
            "remaining_days": remaining_days,
        }
    finally:
        db.close()


@app.post("/api/simulate/reset_time")
def simulate_reset_time() -> Dict[str, Union[int, str]]:
    global SIMULATION_OFFSET_DAYS
    SIMULATION_OFFSET_DAYS = 0
    return {
        "current_day": get_today().isoformat(),
        "offset_days": SIMULATION_OFFSET_DAYS,
    }
@app.on_event("startup")
def on_startup():
    if not scheduler.running:
        scheduler.start()
        logging.info("Background scheduler started.")
    try:
        with engine.connect() as conn:
            if engine.dialect.name == "sqlite":
                cols = conn.execute(text("PRAGMA table_info('tasks')")).fetchall()
                names = [row[1] for row in cols]
                if "tech_debt_estimate_days" not in names:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN tech_debt_estimate_days INTEGER"))
    except Exception as exc:
        logging.exception("Schema ensure failed: %s", exc)
    if _env_flag("DEVSPRINT_SEED_DEMO", "1"):
        db = SessionLocal()
        try:
            seed_demo_data(db)
        finally:
            db.close()


@app.on_event("shutdown")
def on_shutdown():
    if scheduler.running:
        scheduler.shutdown(wait=False)
class TaskAssignmentResponse(BaseModel):
    id: int
    user: Optional[str]
    role: str
    remaining_days: int
    started_at: Optional[datetime]
    status: str
    decision: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class AssignmentBatchCreate(BaseModel):
    users: List[str]
    role: Optional[str] = "DEV"
    remaining_days: int = Field(..., ge=0)

class ReviewDecision(BaseModel):
    approved: bool
    tech_debt_days: Optional[int] = Field(None, ge=0)
