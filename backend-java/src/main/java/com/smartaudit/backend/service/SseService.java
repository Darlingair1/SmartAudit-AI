package com.smartaudit.backend.service;

import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

public interface SseService {

    SseEmitter createSseEmitter(Long taskId);

    void sendMessage(Long taskId, String message);

    void complete(Long taskId);
}

