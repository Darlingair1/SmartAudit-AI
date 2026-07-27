package com.smartaudit.backend.security;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;

class SimpleRateLimiterTest {

    @Test
    void shouldLimitWithinOneMinuteWindow() {
        SimpleRateLimiter limiter = new SimpleRateLimiter();
        String key = "trigger:127.0.0.1";
        Assertions.assertTrue(limiter.tryAcquire(key, 2));
        Assertions.assertTrue(limiter.tryAcquire(key, 2));
        Assertions.assertFalse(limiter.tryAcquire(key, 2));
    }
}
