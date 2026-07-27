package com.smartaudit.backend.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.smartaudit.backend.security.AuthContext;
import com.smartaudit.backend.security.AuthPrincipal;
import com.smartaudit.backend.security.CallbackSignatureVerifier;
import com.smartaudit.backend.security.PdfUploadValidator;
import com.smartaudit.backend.security.SimpleRateLimiter;
import com.smartaudit.backend.service.AuditTaskService;
import com.smartaudit.backend.service.SseService;
import com.smartaudit.backend.dto.AuditTaskDetailRespDTO;
import com.smartaudit.backend.entity.AuditTask;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;

class AuditTaskControllerAuthorizationTest {

    private final AuditTaskService auditTaskService = mock(AuditTaskService.class);
    private final AuditTaskController controller = new AuditTaskController(
            auditTaskService,
            mock(SseService.class),
            mock(SimpleRateLimiter.class),
            mock(CallbackSignatureVerifier.class),
            new ObjectMapper(),
            mock(PdfUploadValidator.class));

    @AfterEach
    void clearContext() {
        AuthContext.clear();
    }

    @Test
    void employeeCannotDeleteOrTriggerAudit() {
        AuthContext.set(new AuthPrincipal(7L, "employee", "EMPLOYEE"));
        assertThrows(SecurityException.class, () -> controller.delete(1L));
        assertThrows(SecurityException.class, () -> controller.triggerAiAudit(1L, null));
    }

    @Test
    void unauthenticatedUserCannotReadDetailsOrPdf() {
        assertThrows(SecurityException.class, () -> controller.getById(1L));
        assertThrows(SecurityException.class, () -> controller.previewPdf(1L));
        assertThrows(SecurityException.class, () -> controller.subscribeTaskSse(1L, null));
    }

    @Test
    void employeeCannotReadAnotherUsersTask() {
        AuthContext.set(new AuthPrincipal(7L, "employee", "EMPLOYEE"));
        AuditTaskDetailRespDTO detail = new AuditTaskDetailRespDTO();
        detail.setInitiatorUserId(8L);
        when(auditTaskService.getTaskDetail(1L)).thenReturn(detail);
        assertThrows(SecurityException.class, () -> controller.getById(1L));

        AuditTask task = new AuditTask();
        task.setInitiatorUserId(8L);
        task.setFilePath("managed.pdf");
        when(auditTaskService.getById(1L)).thenReturn(task);
        assertThrows(SecurityException.class, () -> controller.previewPdf(1L));
    }

    @Test
    void adminCanUseDetailTriggerDeleteAndSseEndpoints() {
        AuthContext.set(new AuthPrincipal(1L, "admin", "ADMIN"));
        AuditTaskDetailRespDTO detail = new AuditTaskDetailRespDTO();
        detail.setInitiatorUserId(8L);
        AuditTask task = new AuditTask();
        task.setId(1L);
        task.setInitiatorUserId(8L);
        when(auditTaskService.getTaskDetail(1L)).thenReturn(detail);
        when(auditTaskService.getById(1L)).thenReturn(task);
        when(auditTaskService.triggerAiAudit(1L)).thenReturn(true);
        when(auditTaskService.deleteTaskCascade(1L)).thenReturn(true);
        SimpleRateLimiter limiter = (SimpleRateLimiter) org.springframework.test.util.ReflectionTestUtils
                .getField(controller, "rateLimiter");
        when(limiter.tryAcquire(anyString(), anyInt())).thenReturn(true);
        SseService sseService = (SseService) org.springframework.test.util.ReflectionTestUtils
                .getField(controller, "sseService");
        when(sseService.createSseEmitter(1L)).thenReturn(new SseEmitter());
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRemoteAddr("127.0.0.1");

        controller.getById(1L);
        controller.triggerAiAudit(1L, request);
        controller.subscribeTaskSse(1L, request);
        controller.delete(1L);
    }
}
