-- 1. 创建数据库（如已存在可跳过）
CREATE DATABASE IF NOT EXISTS devsprint_db
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE devsprint_db;

-- 2. Sprint 主表
CREATE TABLE IF NOT EXISTS sprints (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  goal        VARCHAR(500),
  start_date  DATE NOT NULL,
  end_date    DATE NOT NULL,
  status      ENUM('ACTIVE','CLOSED') DEFAULT 'ACTIVE',
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT chk_sprint_dates CHECK (end_date >= start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. User Story
CREATE TABLE IF NOT EXISTS user_stories (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  sprint_id    INT NULL,
  title        VARCHAR(255) NOT NULL,
  description  TEXT,
  story_points INT NOT NULL,
  priority     INT DEFAULT 3,
  is_tech_debt TINYINT(1) DEFAULT 0,
  status       ENUM('PLANNED','ACTIVE','DONE') DEFAULT 'PLANNED',
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_story_sprint
    FOREIGN KEY (sprint_id) REFERENCES sprints(id)
    ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Task（子任务）
CREATE TABLE IF NOT EXISTS tasks (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  story_id      INT NOT NULL,
  title         VARCHAR(255) NOT NULL,
  status        VARCHAR(20) DEFAULT 'TODO', -- 兼容 ENUM('TODO','IN_PROGRESS','CODE_REVIEW','DONE')
  story_points  INT NOT NULL,
  is_tech_debt  TINYINT(1) DEFAULT 0,
  assignee      VARCHAR(255),
  reviewer      VARCHAR(255),
  review_started_at DATETIME,
  is_blocked    TINYINT(1) DEFAULT 0,
  tech_debt_estimate_days INT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_task_story
    FOREIGN KEY (story_id) REFERENCES user_stories(id)
    ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. GitHub 关联
CREATE TABLE IF NOT EXISTS github_links (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  task_id     INT NOT NULL,
  commit_hash VARCHAR(100),
  pr_url      VARCHAR(500),
  repo_name   VARCHAR(255),
  pr_state    VARCHAR(50),
  pr_merged   TINYINT(1) DEFAULT 0,
  ci_status   VARCHAR(50),
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_link_task
    FOREIGN KEY (task_id) REFERENCES tasks(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  INDEX idx_commit_hash (commit_hash),
  INDEX idx_pr_url (pr_url(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. 任务分配（多人评审/开发）
CREATE TABLE IF NOT EXISTS task_assignments (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  task_id        INT NOT NULL,
  user           VARCHAR(255),
  role           VARCHAR(20) NOT NULL, -- 'DEV' or 'REVIEW'
  remaining_days INT DEFAULT 0,
  started_at     DATETIME,
  status         VARCHAR(20) DEFAULT 'ACTIVE',
  decision       VARCHAR(20), -- 'APPROVED', 'REJECTED'
  created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_assignment_task
    FOREIGN KEY (task_id) REFERENCES tasks(id)
    ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. 燃尽快照
CREATE TABLE IF NOT EXISTS burndown_snapshots (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  sprint_id        INT NOT NULL,
  snapshot_date    DATE NOT NULL,
  remaining_points INT NOT NULL DEFAULT 0,
  created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_snapshot_sprint
    FOREIGN KEY (sprint_id) REFERENCES sprints(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  UNIQUE KEY uniq_snapshot_day (sprint_id, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. 累积流快照 (CFD)
CREATE TABLE IF NOT EXISTS flow_snapshots (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  sprint_id         INT NOT NULL,
  snapshot_date     DATE NOT NULL,
  todo_count        INT DEFAULT 0,
  in_progress_count INT DEFAULT 0,
  code_review_count INT DEFAULT 0,
  done_count        INT DEFAULT 0,
  created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_flow_sprint
    FOREIGN KEY (sprint_id) REFERENCES sprints(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  UNIQUE KEY uniq_flow_day (sprint_id, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
