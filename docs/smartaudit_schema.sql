-- =========================================================
-- SmartAudit-AI 核心库表（MySQL 8 / InnoDB / utf8mb4）
-- 说明：ID 由应用层雪花算法生成，不使用自增。
-- =========================================================

CREATE TABLE `sys_user` (
  `id` BIGINT NOT NULL COMMENT '主键ID（雪花算法）',
  `username` VARCHAR(64) NOT NULL COMMENT '登录账号',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希（建议BCrypt/Argon2）',
  `real_name` VARCHAR(64) NOT NULL COMMENT '真实姓名',
  `mobile` VARCHAR(20) DEFAULT NULL COMMENT '手机号',
  `email` VARCHAR(128) DEFAULT NULL COMMENT '邮箱',
  `role_code` VARCHAR(64) NOT NULL DEFAULT 'EMPLOYEE' COMMENT '角色编码（RBAC）',
  `status` TINYINT NOT NULL DEFAULT 1 COMMENT '账号状态：1启用，0禁用',
  `last_login_time` DATETIME(3) DEFAULT NULL COMMENT '最后登录时间',
  `create_time` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `update_time` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  `is_deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标识：0否，1是',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sys_user_username` (`username`),
  UNIQUE KEY `uk_sys_user_mobile` (`mobile`),
  KEY `idx_sys_user_role_status` (`role_code`, `status`),
  KEY `idx_sys_user_is_deleted` (`is_deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='系统用户表';


CREATE TABLE `audit_task` (
  `id` BIGINT NOT NULL COMMENT '主键ID（雪花算法）',
  `task_no` VARCHAR(50) NOT NULL COMMENT '任务编号（业务唯一）',
  `task_name` VARCHAR(200) NOT NULL COMMENT '任务名称',
  `file_name` VARCHAR(255) NOT NULL COMMENT '原始文件名',
  `file_storage_type` VARCHAR(20) NOT NULL DEFAULT 'OSS' COMMENT '文件存储类型：LOCAL/OSS',
  `file_path` VARCHAR(1024) NOT NULL COMMENT '文件存储路径',
  `file_sha256` CHAR(64) DEFAULT NULL COMMENT '文件内容SHA256',
  `file_size` BIGINT DEFAULT NULL COMMENT '文件大小（字节）',
  `status` VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '任务状态：PENDING/PROCESSING/COMPLETED/FAILED',
  `progress` TINYINT NOT NULL DEFAULT 0 COMMENT '审查进度（0-100）',
  `initiator_user_id` BIGINT NOT NULL COMMENT '发起人用户ID',
  `python_job_id` VARCHAR(64) DEFAULT NULL COMMENT 'Python侧任务ID',
  `ai_model` VARCHAR(100) DEFAULT NULL COMMENT '本次审查模型标识',
  `risk_total` INT NOT NULL DEFAULT 0 COMMENT '风险总数',
  `high_risk_count` INT NOT NULL DEFAULT 0 COMMENT '高风险数量',
  `medium_risk_count` INT NOT NULL DEFAULT 0 COMMENT '中风险数量',
  `low_risk_count` INT NOT NULL DEFAULT 0 COMMENT '低风险数量',
  `error_code` VARCHAR(64) DEFAULT NULL COMMENT '失败错误码',
  `error_message` VARCHAR(1000) DEFAULT NULL COMMENT '失败错误信息',
  `start_time` DATETIME(3) DEFAULT NULL COMMENT 'AI审查开始时间',
  `complete_time` DATETIME(3) DEFAULT NULL COMMENT 'AI审查完成时间',
  `ext_json` JSON DEFAULT NULL COMMENT '扩展字段（规则快照、参数等）',
  `create_time` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `update_time` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  `is_deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标识：0否，1是',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_audit_task_task_no` (`task_no`),
  KEY `idx_audit_task_initiator_status` (`initiator_user_id`, `status`),
  KEY `idx_audit_task_status_ctime` (`status`, `create_time`),
  KEY `idx_audit_task_python_job_id` (`python_job_id`),
  KEY `idx_audit_task_is_deleted` (`is_deleted`),
  CONSTRAINT `fk_audit_task_initiator` FOREIGN KEY (`initiator_user_id`) REFERENCES `sys_user` (`id`),
  CONSTRAINT `chk_audit_task_progress` CHECK (`progress` BETWEEN 0 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='合同审查任务主表';


CREATE TABLE `audit_risk_item` (
  `id` BIGINT NOT NULL COMMENT '主键ID（雪花算法）',
  `task_id` BIGINT NOT NULL COMMENT '关联审查任务ID',
  `seq_no` INT NOT NULL DEFAULT 1 COMMENT '风险序号（同任务内排序）',
  `risk_type` VARCHAR(64) NOT NULL COMMENT '风险类型（如违约责任、付款周期等）',
  `risk_level` VARCHAR(16) NOT NULL COMMENT '风险等级：HIGH/MEDIUM/LOW',
  `risk_score` DECIMAL(5,2) DEFAULT NULL COMMENT '风险评分（0-100）',
  `clause_title` VARCHAR(255) DEFAULT NULL COMMENT '条款标题',
  `clause_position` VARCHAR(128) DEFAULT NULL COMMENT '条款定位（页码/段落）',
  `contract_excerpt` TEXT NOT NULL COMMENT '合同原文片段',
  `risk_desc` VARCHAR(2000) DEFAULT NULL COMMENT '风险说明',
  `suggestion` TEXT NOT NULL COMMENT '修改建议',
  `legal_basis` VARCHAR(500) DEFAULT NULL COMMENT '法条或制度依据',
  `evidence` TEXT DEFAULT NULL COMMENT '模型检索证据或推理摘要',
  `review_status` TINYINT NOT NULL DEFAULT 0 COMMENT '人工复核状态：0待复核，1已确认，2已驳回',
  `create_time` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `update_time` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  `is_deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标识：0否，1是',
  PRIMARY KEY (`id`),
  KEY `idx_audit_risk_item_task_id` (`task_id`),
  KEY `idx_audit_risk_item_level` (`risk_level`),
  KEY `idx_audit_risk_item_type` (`risk_type`),
  KEY `idx_audit_risk_item_task_deleted` (`task_id`, `is_deleted`),
  CONSTRAINT `fk_risk_item_task` FOREIGN KEY (`task_id`) REFERENCES `audit_task` (`id`),
  CONSTRAINT `chk_risk_level` CHECK (`risk_level` IN ('HIGH', 'MEDIUM', 'LOW'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='审查风险明细表';


CREATE TABLE `audit_callback_log` (
  `id` BIGINT NOT NULL COMMENT '主键ID（雪花算法）',
  `task_id` BIGINT NOT NULL COMMENT '关联审查任务ID',
  `callback_id` VARCHAR(64) NOT NULL COMMENT '回调唯一ID（幂等键）',
  `python_job_id` VARCHAR(64) DEFAULT NULL COMMENT 'Python任务ID',
  `callback_status` TINYINT NOT NULL DEFAULT 1 COMMENT '回调处理结果：1成功，0失败',
  `http_status` INT DEFAULT NULL COMMENT 'Java响应状态码',
  `payload_json` JSON NOT NULL COMMENT '回调原始报文',
  `fail_reason` VARCHAR(1000) DEFAULT NULL COMMENT '失败原因',
  `create_time` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `update_time` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  `is_deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标识：0否，1是',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_callback_id` (`callback_id`),
  KEY `idx_callback_task_id` (`task_id`),
  KEY `idx_callback_create_time` (`create_time`),
  CONSTRAINT `fk_callback_task` FOREIGN KEY (`task_id`) REFERENCES `audit_task` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI回调日志表（用于幂等和审计）';

