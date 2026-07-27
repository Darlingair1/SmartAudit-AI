package com.smartaudit.backend.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.smartaudit.backend.dto.AuditCallbackReqDTO;
import com.smartaudit.backend.dto.AuditTaskDetailRespDTO;
import com.smartaudit.backend.entity.AuditTask;

public interface AuditTaskService extends IService<AuditTask> {

    AuditTaskDetailRespDTO getTaskDetail(Long taskId);

    boolean triggerAiAudit(Long taskId);

    boolean handleAiCallback(AuditCallbackReqDTO dto);

    boolean deleteTaskCascade(Long taskId);
}
