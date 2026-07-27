package com.smartaudit.backend.service.impl;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import com.smartaudit.backend.service.SseService;

import java.io.IOException;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Service
public class SseServiceImpl implements SseService {

    private static final long SSE_TIMEOUT_MS = 300_000L;
    private final ConcurrentHashMap<Long, SseEmitter> emitterMap = new ConcurrentHashMap<>();

    @Override
    public SseEmitter createSseEmitter(Long taskId) {
        if (taskId == null) {
            throw new IllegalArgumentException("taskId cannot be null");
        }
        SseEmitter oldEmitter = emitterMap.remove(taskId);
        if (oldEmitter != null) {
            oldEmitter.complete();
        }

        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        emitterMap.put(taskId, emitter);

        emitter.onCompletion(() -> emitterMap.remove(taskId));
        emitter.onTimeout(() -> {
            emitterMap.remove(taskId);
            emitter.complete();
        });
        emitter.onError((ex) -> emitterMap.remove(taskId));
        try {
            // Flush response headers immediately so browser fetch establishes the stream.
            emitter.send(SseEmitter.event().name("connected").data("CONNECTED"));
        } catch (IOException | IllegalStateException ex) {
            emitterMap.remove(taskId);
            emitter.completeWithError(ex);
            throw new IllegalStateException("failed to establish SSE stream", ex);
        }
        return emitter;
    }

    @Override
    public void sendMessage(Long taskId, String message) {
        SseEmitter emitter = emitterMap.get(taskId);
        if (emitter == null) {
            return;
        }
        try {
            emitter.send(SseEmitter.event().name("message").data(message));
        } catch (IOException | IllegalStateException ex) {
            log.warn("SSE send failed, taskId={}", taskId, ex);
            emitterMap.remove(taskId);
            emitter.completeWithError(ex);
        }
    }

    @Override
    public void complete(Long taskId) {
        SseEmitter emitter = emitterMap.remove(taskId);
        if (emitter != null) {
            emitter.complete();
        }
    }
}
