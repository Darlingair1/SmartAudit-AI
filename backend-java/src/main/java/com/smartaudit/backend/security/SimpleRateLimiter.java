package com.smartaudit.backend.security;

import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Component
public class SimpleRateLimiter {

    private final ConcurrentHashMap<String, WindowCounter> counterMap = new ConcurrentHashMap<>();

    public boolean tryAcquire(String key, int limitPerMinute) {
        if (limitPerMinute <= 0) {
            return true;
        }
        long minuteBucket = Instant.now().getEpochSecond() / 60;
        WindowCounter current = counterMap.compute(key, (k, existing) -> {
            if (existing == null || existing.windowMinute != minuteBucket) {
                return new WindowCounter(minuteBucket, new AtomicInteger(1));
            }
            existing.count.incrementAndGet();
            return existing;
        });
        return current.count.get() <= limitPerMinute;
    }

    private static final class WindowCounter {
        private final long windowMinute;
        private final AtomicInteger count;

        private WindowCounter(long windowMinute, AtomicInteger count) {
            this.windowMinute = windowMinute;
            this.count = count;
        }
    }
}
