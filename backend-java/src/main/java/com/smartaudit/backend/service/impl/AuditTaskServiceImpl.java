package com.smartaudit.backend.service.impl;

import cn.hutool.core.util.StrUtil;
import cn.hutool.http.HttpResponse;
import cn.hutool.http.HttpUtil;
import cn.hutool.json.JSONUtil;
import org.springframework.beans.BeanUtils;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.smartaudit.backend.dto.AuditCallbackReqDTO;
import com.smartaudit.backend.dto.AuditTaskDetailRespDTO;
import com.smartaudit.backend.entity.AuditCallbackLog;
import com.smartaudit.backend.entity.AuditRiskItem;
import com.smartaudit.backend.entity.AuditTask;
import com.smartaudit.backend.mapper.AuditTaskMapper;
import com.smartaudit.backend.service.AuditCallbackLogService;
import com.smartaudit.backend.service.AuditRiskItemService;
import com.smartaudit.backend.service.SseService;
import com.smartaudit.backend.service.AuditTaskService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.interceptor.TransactionAspectSupport;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuditTaskServiceImpl extends ServiceImpl<AuditTaskMapper, AuditTask> implements AuditTaskService {

    // 本类是“任务聚合根”的核心业务层：任务状态、风险明细、回调日志在这里统一编排。
    private final AuditRiskItemService auditRiskItemService;
    private final AuditCallbackLogService auditCallbackLogService;
    private final SseService sseService;

    @Value("${smartaudit.ai.python-job-url:http://localhost:8000/internal/v1/ai/audit/jobs}")
    private String pythonJobUrl;

    @Value("${smartaudit.ai.callback-url:http://localhost:8080/api/v1/internal/audit/tasks/callback}")
    private String callbackUrl;

    @Value("${smartaudit.ai.callback-token:}")
    private String callbackToken;

    @Value("${smartaudit.ai.default-model:deepseek-v4-flash}")
    private String defaultAiModel;

    @Value("${smartaudit.ai.python-cleanup-url:http://localhost:8000/internal/v1/ai/audit/vector-index/cleanup}")
    private String pythonCleanupUrl;

    @Value("${smartaudit.ai.python-internal-token:}")
    private String pythonInternalToken;

    @Value("${smartaudit.storage.local-base-dir:${user.dir}/storage/pdfs}")
    private String localBaseDir;

    @Value("${smartaudit.security.strict-auth-enabled:false}")
    private boolean strictAuthEnabled;

    @Override
    public AuditTaskDetailRespDTO getTaskDetail(Long taskId) {
        if (taskId == null) {
            return null;
        }
        AuditTask task = getById(taskId);
        if (task == null) {
            return null;
        }

        AuditTaskDetailRespDTO detail = new AuditTaskDetailRespDTO();
        BeanUtils.copyProperties(task, detail);

        List<AuditRiskItem> riskItems = auditRiskItemService.lambdaQuery()
                .eq(AuditRiskItem::getTaskId, taskId)
                .orderByAsc(AuditRiskItem::getSeqNo)
                .orderByAsc(AuditRiskItem::getId)
                .list();
        if (riskItems != null && !riskItems.isEmpty()) {
            List<AuditTaskDetailRespDTO.RiskItemDTO> itemDTOList = riskItems.stream()
                    .map(AuditTaskDetailRespDTO::fromEntity)
                    .toList();
            detail.setRiskItems(itemDTOList);
        } else {
            detail.setRiskItems(new ArrayList<>());
        }
        return detail;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean triggerAiAudit(Long taskId) {
        // 1) 参数与状态前置校验：避免非法状态进入 AI 链路。
        if (taskId == null) {
            throw new IllegalArgumentException("taskId cannot be null");
        }
        AuditTask task = getById(taskId);
        if (task == null) {
            throw new IllegalArgumentException("task not found");
        }
        if (StrUtil.isBlank(task.getFilePath())) {
            throw new IllegalArgumentException("task filePath cannot be blank");
        }
        if ("PROCESSING".equalsIgnoreCase(task.getStatus())) {
            return true;
        }
        if ("COMPLETED".equalsIgnoreCase(task.getStatus())) {
            throw new IllegalArgumentException("task already completed");
        }
        if (StrUtil.isBlank(callbackToken)) {
            throw new IllegalStateException("smartaudit.ai.callback-token must be configured");
        }
        if (strictAuthEnabled && StrUtil.isBlank(pythonInternalToken)) {
            throw new IllegalStateException("smartaudit.ai.python-internal-token must be configured in strict mode");
        }
        Path managedFilePath = resolveManagedStoragePath(task.getFilePath());
        if (managedFilePath == null) {
            throw new IllegalArgumentException("task filePath must be a local file under managed storage directory");
        }
        if (!Files.exists(managedFilePath) || !Files.isRegularFile(managedFilePath)) {
            throw new IllegalArgumentException("task file not found under managed storage directory");
        }

        // 2) 组装发往 Python 的请求体（异步受理模式）。
        Map<String, Object> reqBody = new HashMap<>();
        reqBody.put("taskId", String.valueOf(task.getId()));
        reqBody.put("taskNo", task.getTaskNo());
        reqBody.put("filePath", managedFilePath.toString());
        reqBody.put("fileName", task.getFileName());
        reqBody.put("callbackUrl", callbackUrl);
        reqBody.put("callbackToken", callbackToken);
        String modelName = defaultAiModel;
        reqBody.put("modelName", modelName);
        reqBody.put("ruleSetCodes", List.of());
        String traceId = "trace-" + UUID.randomUUID();
        reqBody.put("traceId", traceId);

        // 3) 同步调用 Python 仅拿“ACCEPTED”，不是等 AI 真正审完。
        var request = HttpUtil.createPost(pythonJobUrl)
                .header("Content-Type", "application/json")
                .header("X-Trace-Id", traceId)
                .body(JSONUtil.toJsonStr(reqBody))
                .timeout(15000);
        if (StrUtil.isNotBlank(pythonInternalToken)) {
            request.header("X-Internal-Token", pythonInternalToken);
        }
        HttpResponse response = request.execute();

        if (!response.isOk()) {
            throw new RuntimeException("python service http error: " + response.getStatus());
        }

        String body = response.body();
        if (StrUtil.isBlank(body)) {
            throw new RuntimeException("python service response body is empty");
        }

        Boolean accepted = JSONUtil.parseObj(body).getBool("accepted", false);
        String status = JSONUtil.parseObj(body).getStr("status");
        String pythonJobId = JSONUtil.parseObj(body).getStr("pythonJobId");
        if (!Boolean.TRUE.equals(accepted) || !"ACCEPTED".equalsIgnoreCase(status)) {
            throw new RuntimeException("python service rejected task: " + body);
        }

        // 4) Python 接受后，本地任务切到 PROCESSING。
        AuditTask toUpdate = new AuditTask();
        toUpdate.setId(taskId);
        toUpdate.setStatus("PROCESSING");
        toUpdate.setProgress(10);
        toUpdate.setPythonJobId(pythonJobId);
        toUpdate.setAiModel(modelName);
        toUpdate.setStartTime(LocalDateTime.now());
        toUpdate.setErrorCode(null);
        toUpdate.setErrorMessage(null);
        return updateById(toUpdate);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean handleAiCallback(AuditCallbackReqDTO dto) {
        // 幂等主键：同一个 callbackId 只能成功处理一次。
        if (dto == null || StrUtil.isBlank(dto.getCallbackId())) {
            throw new IllegalArgumentException("callbackId cannot be blank");
        }

        AuditCallbackLog existed = auditCallbackLogService.findByCallbackId(dto.getCallbackId());
        if (existed != null && Integer.valueOf(1).equals(existed.getCallbackStatus())) {
            return true;
        }

        AuditCallbackLog callbackLog = buildBaseCallbackLog(dto);
        try {
            Long taskId = parseTaskId(dto.getTaskId());
            AuditTask task = getById(taskId);
            if (task == null) {
                throw new IllegalArgumentException("task not found for callback");
            }

            String callbackStatus = StrUtil.emptyToDefault(dto.getStatus(), "FAILED").toUpperCase();
            String notifyStatus;
            AuditTask toUpdate = new AuditTask();
            toUpdate.setId(taskId);
            toUpdate.setPythonJobId(StrUtil.emptyToDefault(dto.getPythonJobId(), task.getPythonJobId()));
            toUpdate.setProgress(100);
            toUpdate.setCompleteTime(LocalDateTime.now());

            if ("COMPLETED".equals(callbackStatus)) {
                // 成功分支：先算统计，再更新 task，再重建该任务风险明细。
                List<AuditRiskItem> entities = convertRiskItems(taskId, dto.getRiskItems());
                RiskCounter counter = countRiskLevels(entities);

                AuditCallbackReqDTO.SummaryDTO summary = dto.getSummary();
                Integer riskTotal = summary != null && summary.getRiskTotal() != null
                        ? summary.getRiskTotal()
                        : entities.size();
                Integer highCount = summary != null && summary.getHighRiskCount() != null
                        ? summary.getHighRiskCount()
                        : counter.highCount;
                Integer mediumCount = summary != null && summary.getMediumRiskCount() != null
                        ? summary.getMediumRiskCount()
                        : counter.mediumCount;
                Integer lowCount = summary != null && summary.getLowRiskCount() != null
                        ? summary.getLowRiskCount()
                        : counter.lowCount;

                toUpdate.setStatus("COMPLETED");
                toUpdate.setRiskTotal(defaultZero(riskTotal));
                toUpdate.setHighRiskCount(defaultZero(highCount));
                toUpdate.setMediumRiskCount(defaultZero(mediumCount));
                toUpdate.setLowRiskCount(defaultZero(lowCount));
                toUpdate.setErrorCode(null);
                toUpdate.setErrorMessage(null);
                notifyStatus = "COMPLETED";

                updateById(toUpdate);
                auditRiskItemService.remove(Wrappers.<AuditRiskItem>lambdaQuery()
                        .eq(AuditRiskItem::getTaskId, taskId));
                if (!entities.isEmpty()) {
                    auditRiskItemService.saveBatch(entities, 200);
                }
            } else {
                // 失败分支：任务置 FAILED，并写 error_code / error_message 便于排障。
                AuditCallbackReqDTO.SummaryDTO summary = dto.getSummary();
                AuditCallbackReqDTO.ErrorDTO error = dto.getError();
                toUpdate.setStatus("FAILED");
                toUpdate.setRiskTotal(summary != null ? defaultZero(summary.getRiskTotal()) : 0);
                toUpdate.setHighRiskCount(summary != null ? defaultZero(summary.getHighRiskCount()) : 0);
                toUpdate.setMediumRiskCount(summary != null ? defaultZero(summary.getMediumRiskCount()) : 0);
                toUpdate.setLowRiskCount(summary != null ? defaultZero(summary.getLowRiskCount()) : 0);
                toUpdate.setErrorCode(error != null && StrUtil.isNotBlank(error.getCode())
                        ? error.getCode()
                        : "AI_AUDIT_FAILED");
                toUpdate.setErrorMessage(error != null && StrUtil.isNotBlank(error.getMessage())
                        ? truncate(error.getMessage(), 900)
                        : "AI audit failed");
                notifyStatus = "FAILED";
                updateById(toUpdate);
            }

            callbackLog.setTaskId(taskId);
            callbackLog.setCallbackStatus(1);
            callbackLog.setHttpStatus(200);
            callbackLog.setFailReason(null);
            auditCallbackLogService.save(callbackLog);

            // 通过 SSE 主动通知前端刷新，完成“后端推送式”状态闭环。
            sseService.sendMessage(taskId, notifyStatus);
            sseService.complete(taskId);
            return true;
        } catch (Exception ex) {
            // 回调日志单独新事务落库，保证即使主事务回滚也能留痕。
            if (ex instanceof DuplicateKeyException) {
                AuditCallbackLog concurrent = auditCallbackLogService.findByCallbackId(dto.getCallbackId());
                if (concurrent != null && Integer.valueOf(1).equals(concurrent.getCallbackStatus())) {
                    return true;
                }
            }
            log.error("Handle ai callback failed, callbackId={}", dto.getCallbackId(), ex);
            TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
            callbackLog.setCallbackStatus(0);
            callbackLog.setHttpStatus(500);
            callbackLog.setFailReason(truncate(ex.getMessage(), 900));
            auditCallbackLogService.saveLogWithNewTransaction(callbackLog);
            return false;
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean deleteTaskCascade(Long taskId) {
        // 删除任务时顺带清理风险、回调日志和本地 PDF，避免历史垃圾数据堆积。
        if (taskId == null) {
            throw new IllegalArgumentException("taskId cannot be null");
        }
        AuditTask task = getById(taskId);
        if (task == null) {
            throw new IllegalArgumentException("task not found");
        }

        boolean deleted = removeById(taskId);
        if (!deleted) {
            return false;
        }

        auditRiskItemService.remove(Wrappers.<AuditRiskItem>lambdaQuery()
                .eq(AuditRiskItem::getTaskId, taskId));
        auditCallbackLogService.remove(Wrappers.<AuditCallbackLog>lambdaQuery()
                .eq(AuditCallbackLog::getTaskId, taskId));

        cleanupPythonVectorIndex(taskId);
        deleteLocalFileIfNeed(task.getFilePath());
        sseService.complete(taskId);
        return true;
    }

    private AuditCallbackLog buildBaseCallbackLog(AuditCallbackReqDTO dto) {
        AuditCallbackLog callbackLog = new AuditCallbackLog();
        callbackLog.setCallbackId(dto.getCallbackId());
        callbackLog.setPythonJobId(dto.getPythonJobId());
        Map<String, Object> safeMetadata = new HashMap<>();
        safeMetadata.put("callbackId", dto.getCallbackId());
        safeMetadata.put("taskId", dto.getTaskId());
        safeMetadata.put("pythonJobId", dto.getPythonJobId());
        safeMetadata.put("status", dto.getStatus());
        safeMetadata.put("riskItemCount", dto.getRiskItems() == null ? 0 : dto.getRiskItems().size());
        callbackLog.setPayloadJson(JSONUtil.toJsonStr(safeMetadata));
        callbackLog.setTaskId(StrUtil.isNumeric(dto.getTaskId()) ? Long.parseLong(dto.getTaskId()) : null);
        return callbackLog;
    }

    private Long parseTaskId(String taskId) {
        if (!StrUtil.isNumeric(taskId)) {
            throw new IllegalArgumentException("invalid taskId in callback");
        }
        return Long.parseLong(taskId);
    }

    private List<AuditRiskItem> convertRiskItems(Long taskId, List<AuditCallbackReqDTO.RiskItemDTO> riskItems) {
        List<AuditRiskItem> entities = new ArrayList<>();
        if (riskItems == null || riskItems.isEmpty()) {
            return entities;
        }
        int seq = 1;
        for (AuditCallbackReqDTO.RiskItemDTO item : riskItems) {
            AuditRiskItem entity = new AuditRiskItem();
            entity.setTaskId(taskId);
            entity.setSeqNo(item.getSeqNo() != null ? item.getSeqNo() : seq++);
            entity.setRiskType(StrUtil.emptyToDefault(item.getRiskType(), "UNKNOWN"));
            entity.setRiskLevel(normalizeRiskLevel(item.getRiskLevel()));
            entity.setRiskScore(item.getRiskScore());
            entity.setClauseTitle(item.getClauseTitle());
            entity.setClausePosition(item.getClausePosition());
            entity.setPageNo(item.getPageNo() != null && item.getPageNo() > 0 ? item.getPageNo() : 1);
            entity.setContractExcerpt(StrUtil.emptyToDefault(item.getContractExcerpt(), ""));
            entity.setRiskDesc(item.getRiskDesc());
            entity.setSuggestion(StrUtil.emptyToDefault(item.getSuggestion(), "Please review and revise this clause manually."));
            entity.setLegalBasis(item.getLegalBasis());
            entity.setEvidence(item.getEvidence());
            entity.setReviewStatus(0);
            entities.add(entity);
        }
        return entities;
    }

    private String normalizeRiskLevel(String riskLevel) {
        if (StrUtil.isBlank(riskLevel)) {
            return "LOW";
        }
        String upper = riskLevel.trim().toUpperCase();
        return switch (upper) {
            case "HIGH", "MEDIUM", "LOW" -> upper;
            default -> "LOW";
        };
    }

    private RiskCounter countRiskLevels(List<AuditRiskItem> entities) {
        RiskCounter counter = new RiskCounter();
        for (AuditRiskItem entity : entities) {
            if ("HIGH".equals(entity.getRiskLevel())) {
                counter.highCount++;
            } else if ("MEDIUM".equals(entity.getRiskLevel())) {
                counter.mediumCount++;
            } else {
                counter.lowCount++;
            }
        }
        return counter;
    }

    private Integer defaultZero(Integer value) {
        return value == null || value < 0 ? 0 : value;
    }

    private String truncate(String value, int maxLen) {
        if (StrUtil.isBlank(value)) {
            return value;
        }
        if (value.length() <= maxLen) {
            return value;
        }
        return value.substring(0, maxLen);
    }

    private void deleteLocalFileIfNeed(String filePath) {
        Path path = resolveManagedStoragePath(filePath);
        if (path == null) {
            if (StrUtil.isNotBlank(filePath)) {
                log.warn("Skip deleting unmanaged filePath: {}", filePath);
            }
            return;
        }
        try {
            Files.deleteIfExists(path);
        } catch (IOException ex) {
            throw new RuntimeException("delete local file failed: " + filePath, ex);
        }
    }

    private void cleanupPythonVectorIndex(Long taskId) {
        if (taskId == null || StrUtil.isBlank(pythonCleanupUrl)) {
            return;
        }
        try {
            Map<String, Object> payload = new HashMap<>();
            payload.put("taskId", String.valueOf(taskId));

            var req = HttpUtil.createPost(pythonCleanupUrl)
                    .header("Content-Type", "application/json")
                    .timeout(8000)
                    .body(JSONUtil.toJsonStr(payload));
            if (StrUtil.isNotBlank(pythonInternalToken)) {
                req.header("X-Internal-Token", pythonInternalToken);
            }

            HttpResponse response = req.execute();
            if (!response.isOk()) {
                log.warn("Python vector cleanup http failed, taskId={}, status={}", taskId, response.getStatus());
                return;
            }

            String body = response.body();
            if (StrUtil.isBlank(body)) {
                return;
            }
            Boolean cleaned = JSONUtil.parseObj(body).getBool("cleaned", false);
            if (!Boolean.TRUE.equals(cleaned)) {
                log.warn("Python vector cleanup returned not cleaned, taskId={}", taskId);
            }
        } catch (Exception ex) {
            // Best effort cleanup: do not block main delete transaction.
            log.warn("Python vector cleanup exception, taskId={}", taskId, ex);
        }
    }

    private String resolveStorageBaseDir() {
        String configured = StrUtil.trim(localBaseDir);
        if (StrUtil.isBlank(configured) || configured.contains("${")) {
            return Paths.get(System.getProperty("user.dir"), "storage", "pdfs").toString();
        }
        return configured;
    }

    private Path resolveStorageBasePath() {
        return Paths.get(resolveStorageBaseDir()).toAbsolutePath().normalize();
    }

    private Path resolveManagedStoragePath(String filePath) {
        if (StrUtil.isBlank(filePath)) {
            return null;
        }
        String lower = filePath.toLowerCase();
        if (lower.startsWith("http://")
                || lower.startsWith("https://")
                || lower.startsWith("oss://")
                || lower.startsWith("s3://")
                || lower.startsWith("file://")) {
            return null;
        }
        try {
            Path path = Paths.get(filePath).toAbsolutePath().normalize();
            Path basePath = resolveStorageBasePath();
            return path.startsWith(basePath) ? path : null;
        } catch (InvalidPathException ex) {
            return null;
        }
    }

    private static class RiskCounter {
        private int highCount;
        private int mediumCount;
        private int lowCount;
    }
}

