package com.smartaudit.backend.security;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class CallbackSignatureVerifierTest {

    @Test
    void shouldVerifySignatureAndBlockReplay() {
        CallbackSignatureVerifier verifier = new CallbackSignatureVerifier();
        ReflectionTestUtils.setField(verifier, "enabled", true);
        ReflectionTestUtils.setField(verifier, "secret", "local-sign-secret-123456");
        ReflectionTestUtils.setField(verifier, "allowedSkewSeconds", 300L);
        ReflectionTestUtils.setField(verifier, "nonceTtlSeconds", 600L);

        String body = "{\"taskId\":\"1\",\"status\":\"COMPLETED\"}";
        String timestamp = String.valueOf(System.currentTimeMillis() / 1000);
        String nonce = "nonce-1";
        String signature = verifier.sign(timestamp, nonce, body);

        boolean first = verifier.verify(body, timestamp, nonce, signature);
        boolean replay = verifier.verify(body, timestamp, nonce, signature);

        Assertions.assertTrue(first);
        Assertions.assertFalse(replay);
    }

    @Test
    void invalidSignatureMustNotConsumeNonce() {
        CallbackSignatureVerifier verifier = new CallbackSignatureVerifier();
        ReflectionTestUtils.setField(verifier, "enabled", true);
        ReflectionTestUtils.setField(verifier, "secret", "local-sign-secret-1234567890123456");
        ReflectionTestUtils.setField(verifier, "allowedSkewSeconds", 300L);
        ReflectionTestUtils.setField(verifier, "nonceTtlSeconds", 600L);

        String body = "{\"taskId\":\"1\"}";
        String timestamp = String.valueOf(System.currentTimeMillis() / 1000);
        String nonce = "nonce-not-poisoned";

        Assertions.assertFalse(verifier.verify(body, timestamp, nonce, "invalid"));
        Assertions.assertTrue(verifier.verify(body, timestamp, nonce, verifier.sign(timestamp, nonce, body)));
    }
}
