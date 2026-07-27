package com.smartaudit.backend.controller;

import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.smartaudit.backend.common.Result;
import com.smartaudit.backend.dto.AuditCallbackReqDTO;
import com.smartaudit.backend.dto.AuditTaskDetailRespDTO;
import com.smartaudit.backend.entity.AuditTask;
import com.smartaudit.backend.security.CallbackSignatureVerifier;
import com.smartaudit.backend.security.AuthContext;
import com.smartaudit.backend.security.AuthPrincipal;
import com.smartaudit.backend.security.RoleGuard;
import com.smartaudit.backend.security.PdfUploadValidator;
import com.smartaudit.backend.security.SimpleRateLimiter;
import com.smartaudit.backend.service.AuditTaskService;
import com.smartaudit.backend.service.SseService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Tag(name = "AuditTask")
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class AuditTaskController {

    private final AuditTaskService auditTaskService;
    private final SseService sseService;
    private final SimpleRateLimiter rateLimiter;
    private final CallbackSignatureVerifier callbackSignatureVerifier;
    private final ObjectMapper objectMapper;
    private final PdfUploadValidator pdfUploadValidator;

    @Value("${smartaudit.storage.local-base-dir:${user.dir}/storage/pdfs}")
    private String localBaseDir;

    @Value("${smartaudit.ai.callback-token:}")
    private String callbackTokenExpected;

    @Value("${smartaudit.ai.default-model:deepseek-v4-flash}")
    private String defaultAiModel;

    @Value("${smartaudit.security.strict-auth-enabled:false}")
    private boolean strictAuthEnabled;

    @Value("${smartaudit.ai.request-limit.trigger-per-minute:30}")
    private int triggerLimitPerMinute;

    @Value("${smartaudit.ai.request-limit.callback-per-minute:180}")
    private int callbackLimitPerMinute;

    @Value("${smartaudit.ai.request-limit.sse-subscribe-per-minute:120}")
    private int sseSubscribeLimitPerMinute;

    @Operation(summary = "Create audit task")
    @PostMapping(value = "/audit/tasks", consumes = MediaType.APPLICATION_JSON_VALUE)
    public Result<AuditTask> create(@RequestBody AuditTask auditTask) {
        RoleGuard.requireAny("ADMIN", "LEGAL");
        if (StrUtil.isBlank(auditTask.getStatus())) {
            auditTask.setStatus("PENDING");
        }
        if (auditTask.getProgress() == null) {
            auditTask.setProgress(0);
        }
        if (StrUtil.isBlank(auditTask.getFileStorageType())) {
            auditTask.setFileStorageType("LOCAL");
        }
        if (StrUtil.isNotBlank(auditTask.getFilePath())) {
            Path managed = resolveManagedStoragePath(auditTask.getFilePath());
            if (managed == null) {
                throw new IllegalArgumentException("filePath must be a local file under managed storage directory");
            }
            auditTask.setFilePath(managed.toString());
        }
        if (auditTask.getInitiatorUserId() == null && AuthContext.get() != null) {
            auditTask.setInitiatorUserId(AuthContext.get().getUserId());
        }
        auditTask.setAiModel(defaultAiModel);
        boolean saved = auditTaskService.save(auditTask);
        if (!saved) {
            return Result.fail(500, "create task failed");
        }
        return Result.success(auditTask);
    }

    @Operation(summary = "Create audit task with pdf upload")
    @PostMapping(value = "/audit/tasks", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Result<AuditTask> createWithUpload(
            @RequestParam("taskName") String taskName,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "taskNo", required = false) String taskNo,
            @RequestParam(value = "initiatorUserId", required = false) Long initiatorUserId) {
        RoleGuard.requireAny("ADMIN", "LEGAL");
        String originalName = pdfUploadValidator.validate(file);
        if (StrUtil.isBlank(taskName)) {
            throw new IllegalArgumentException("taskName cannot be blank");
        }

        String finalTaskNo = StrUtil.isBlank(taskNo) ? "WEB-" + System.currentTimeMillis() : taskNo.trim();
        StoredPdf storedPdf = savePdfToLocal(file);

        AuditTask auditTask = new AuditTask();
        auditTask.setTaskNo(finalTaskNo);
        auditTask.setTaskName(taskName.trim());
        auditTask.setFileName(originalName);
        auditTask.setFileStorageType("LOCAL");
        auditTask.setFilePath(storedPdf.path());
        auditTask.setFileSize(file.getSize());
        auditTask.setFileSha256(storedPdf.sha256());
        auditTask.setStatus("PENDING");
        auditTask.setProgress(0);
        Long resolvedInitiator = initiatorUserId;
        if (resolvedInitiator == null && AuthContext.get() != null) {
            resolvedInitiator = AuthContext.get().getUserId();
        }
        auditTask.setInitiatorUserId(resolvedInitiator != null ? resolvedInitiator : 1L);
        auditTask.setAiModel(defaultAiModel);

        boolean saved = auditTaskService.save(auditTask);
        if (!saved) {
            try {
                Files.deleteIfExists(Paths.get(storedPdf.path()));
            } catch (IOException ignored) {
                // no-op
            }
            return Result.fail(500, "create task failed");
        }
        return Result.success(auditTask);
    }

    @Operation(summary = "Get task by id")
    @GetMapping("/audit/tasks/{id}")
    public Result<AuditTaskDetailRespDTO> getById(@PathVariable Long id) {
        RoleGuard.requireAny("ADMIN", "LEGAL", "EMPLOYEE");
        AuditTaskDetailRespDTO detail = auditTaskService.getTaskDetail(id);
        if (detail == null) {
            return Result.fail(404, "task not found");
        }
        requireTaskReadAccess(detail.getInitiatorUserId());
        return Result.success(detail);
    }

    @Operation(summary = "Preview task pdf file")
    @GetMapping("/audit/tasks/{id}/file")
    public ResponseEntity<Resource> previewPdf(@PathVariable Long id) throws IOException {
        RoleGuard.requireAny("ADMIN", "LEGAL", "EMPLOYEE");
        AuditTask task = auditTaskService.getById(id);
        if (task == null || StrUtil.isBlank(task.getFilePath())) {
            return ResponseEntity.notFound().build();
        }
        requireTaskReadAccess(task.getInitiatorUserId());

        Path path = resolveManagedStoragePath(task.getFilePath());
        if (path == null) {
            return ResponseEntity.badRequest().build();
        }
        if (!Files.exists(path) || !Files.isRegularFile(path)) {
            return ResponseEntity.notFound().build();
        }

        Resource resource = new UrlResource(path.toUri());
        String filename = StrUtil.blankToDefault(task.getFileName(), path.getFileName().toString());
        ContentDisposition disposition = ContentDisposition.inline()
                .filename(filename, StandardCharsets.UTF_8)
                .build();
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_PDF)
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString())
                .body(resource);
    }

    @Operation(summary = "Get task page list")
    @GetMapping("/audit/tasks")
    public Result<IPage<AuditTask>> page(
            @RequestParam(defaultValue = "1") Long pageNum,
            @RequestParam(defaultValue = "10") Long pageSize,
            @RequestParam(required = false) String taskNo,
            @RequestParam(required = false) String taskName,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Long initiatorUserId) {
        RoleGuard.requireAny("ADMIN", "LEGAL", "EMPLOYEE");
        LambdaQueryWrapper<AuditTask> queryWrapper = Wrappers.lambdaQuery();
        if (StrUtil.isNotBlank(taskNo)) {
            queryWrapper.eq(AuditTask::getTaskNo, taskNo);
        }
        if (StrUtil.isNotBlank(taskName)) {
            queryWrapper.like(AuditTask::getTaskName, taskName);
        }
        if (StrUtil.isNotBlank(status)) {
            queryWrapper.eq(AuditTask::getStatus, status);
        }
        if (initiatorUserId != null) {
            queryWrapper.eq(AuditTask::getInitiatorUserId, initiatorUserId);
        }
        AuthPrincipal principal = AuthContext.get();
        if (principal != null && "EMPLOYEE".equalsIgnoreCase(principal.getRoleCode())) {
            queryWrapper.eq(AuditTask::getInitiatorUserId, principal.getUserId());
        }
        queryWrapper.orderByDesc(AuditTask::getCreateTime);
        IPage<AuditTask> page = auditTaskService.page(new Page<>(pageNum, pageSize), queryWrapper);
        return Result.success(page);
    }

    @Operation(summary = "Update task")
    @PutMapping("/audit/tasks/{id}")
    public Result<Boolean> update(@PathVariable Long id, @RequestBody AuditTask auditTask) {
        RoleGuard.requireAny("ADMIN", "LEGAL");
        if (auditTaskService.getById(id) == null) {
            return Result.fail(404, "task not found");
        }
        auditTask.setId(id);
        boolean updated = auditTaskService.updateById(auditTask);
        if (!updated) {
            return Result.fail(500, "update task failed");
        }
        return Result.success(Boolean.TRUE);
    }

    @Operation(summary = "Delete task (logical)")
    @DeleteMapping("/audit/tasks/{id}")
    public Result<Boolean> delete(@PathVariable Long id) {
        RoleGuard.requireAny("ADMIN", "LEGAL");
        if (auditTaskService.getById(id) == null) {
            return Result.fail(404, "task not found");
        }
        boolean deleted = auditTaskService.deleteTaskCascade(id);
        if (!deleted) {
            return Result.fail(500, "delete task failed");
        }
        return Result.success(Boolean.TRUE);
    }

    @Operation(summary = "Trigger AI audit")
    @PostMapping("/audit/tasks/{id}/trigger")
    public Result<Boolean> triggerAiAudit(@PathVariable Long id, HttpServletRequest request) {
        RoleGuard.requireAny("ADMIN", "LEGAL");
        String rateLimitKey = "trigger:" + clientIp(request);
        if (!rateLimiter.tryAcquire(rateLimitKey, triggerLimitPerMinute)) {
            return Result.fail(429, "trigger rate limit exceeded");
        }
        boolean accepted = auditTaskService.triggerAiAudit(id);
        if (!accepted) {
            return Result.fail(500, "trigger ai audit failed");
        }
        return Result.success(Boolean.TRUE);
    }

    @Operation(summary = "Subscribe task SSE events")
    @GetMapping(value = "/audit/tasks/{id}/sse", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter subscribeTaskSse(@PathVariable Long id, HttpServletRequest request) {
        RoleGuard.requireAny("ADMIN", "LEGAL", "EMPLOYEE");
        AuditTask task = auditTaskService.getById(id);
        if (task == null) {
            throw new IllegalArgumentException("task not found");
        }
        requireTaskReadAccess(task.getInitiatorUserId());
        String rateLimitKey = "sse:" + clientIp(request);
        if (!rateLimiter.tryAcquire(rateLimitKey, sseSubscribeLimitPerMinute)) {
            throw new IllegalArgumentException("sse subscribe rate limit exceeded");
        }
        return sseService.createSseEmitter(id);
    }

    @Operation(summary = "AI callback endpoint")
    @PostMapping("/internal/audit/tasks/callback")
    public Result<Map<String, Object>> handleAiCallback(
            @RequestHeader(value = "X-Callback-Token", required = false) String callbackToken,
            @RequestHeader(value = "X-Callback-Timestamp", required = false) String callbackTimestamp,
            @RequestHeader(value = "X-Callback-Nonce", required = false) String callbackNonce,
            @RequestHeader(value = "X-Callback-Signature", required = false) String callbackSignature,
            @RequestBody String rawBody,
            HttpServletRequest request) {
        String rateLimitKey = "callback:" + clientIp(request);
        if (!rateLimiter.tryAcquire(rateLimitKey, callbackLimitPerMinute)) {
            return Result.fail(429, "callback rate limit exceeded");
        }
        if (strictAuthEnabled && StrUtil.isBlank(callbackTokenExpected)) {
            return Result.fail(500, "callback token not configured");
        }
        if (StrUtil.isNotBlank(callbackTokenExpected)
                && !MessageDigest.isEqual(
                        callbackTokenExpected.getBytes(StandardCharsets.UTF_8),
                        StrUtil.nullToEmpty(StrUtil.trim(callbackToken)).getBytes(StandardCharsets.UTF_8))) {
            return Result.fail(401, "unauthorized callback");
        }
        if (!callbackSignatureVerifier.verify(rawBody, callbackTimestamp, callbackNonce, callbackSignature)) {
            return Result.fail(401, "invalid callback signature");
        }

        AuditCallbackReqDTO dto;
        try {
            dto = objectMapper.readValue(rawBody, AuditCallbackReqDTO.class);
        } catch (IOException ex) {
            throw new IllegalArgumentException("invalid callback body");
        }
        boolean handled = auditTaskService.handleAiCallback(dto);
        if (!handled) {
            return Result.fail(500, "callback handle failed");
        }

        Map<String, Object> data = new HashMap<>();
        data.put("ack", true);
        data.put("taskId", dto.getTaskId());
        data.put("updatedStatus", dto.getStatus());
        return Result.success(data);
    }

    private StoredPdf savePdfToLocal(MultipartFile file) {
        try {
            Path baseDir = resolveStorageBasePath();
            String dayFolder = LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
            Path dir = baseDir.resolve(dayFolder);
            Files.createDirectories(dir);

            String newFileName = UUID.randomUUID().toString().replace("-", "") + ".pdf";
            Path target = dir.resolve(newFileName);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream in = new java.security.DigestInputStream(file.getInputStream(), digest)) {
                Files.copy(in, target, StandardCopyOption.REPLACE_EXISTING);
            }
            return new StoredPdf(target.toAbsolutePath().toString(), java.util.HexFormat.of().formatHex(digest.digest()));
        } catch (IOException | NoSuchAlgorithmException ex) {
            throw new RuntimeException("save pdf file failed", ex);
        }
    }

    private record StoredPdf(String path, String sha256) {
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

    private String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (StrUtil.isNotBlank(forwarded)) {
            return forwarded.split(",")[0].trim();
        }
        return StrUtil.blankToDefault(request.getRemoteAddr(), "unknown");
    }

    private void requireTaskReadAccess(Long initiatorUserId) {
        AuthPrincipal principal = AuthContext.get();
        if (principal == null) {
            throw new SecurityException("unauthorized");
        }
        if ("EMPLOYEE".equalsIgnoreCase(principal.getRoleCode())
                && !java.util.Objects.equals(principal.getUserId(), initiatorUserId)) {
            throw new SecurityException("forbidden");
        }
    }
}
