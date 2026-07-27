package com.smartaudit.backend.service;

import com.smartaudit.backend.entity.AuditTask;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class RetentionCleanupJob {

    private final AuditTaskService auditTaskService;

    @Value("${smartaudit.retention.enabled:true}")
    private boolean enabled;

    @Value("${smartaudit.retention.days:90}")
    private int retentionDays;

    @Scheduled(cron = "${smartaudit.retention.cron:0 30 2 * * *}")
    public void cleanupExpiredTasks() {
        if (!enabled) {
            return;
        }
        int days = Math.max(1, retentionDays);
        LocalDateTime cutoff = LocalDateTime.now().minusDays(days);
        List<AuditTask> expired = auditTaskService.lambdaQuery()
                .lt(AuditTask::getCreateTime, cutoff)
                .in(AuditTask::getStatus, "COMPLETED", "FAILED")
                .list();
        for (AuditTask task : expired) {
            try {
                auditTaskService.deleteTaskCascade(task.getId());
            } catch (Exception ex) {
                log.error("Retention cleanup failed, taskId={}", task.getId(), ex);
            }
        }
        if (!expired.isEmpty()) {
            log.info("Retention cleanup processed {} expired tasks", expired.size());
        }
    }
}
