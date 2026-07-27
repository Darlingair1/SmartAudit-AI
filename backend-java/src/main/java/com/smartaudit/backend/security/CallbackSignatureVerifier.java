package com.smartaudit.backend.security;

import cn.hutool.core.util.StrUtil;
import cn.hutool.crypto.digest.HMac;
import cn.hutool.crypto.digest.HmacAlgorithm;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class CallbackSignatureVerifier {

    @Value("${smartaudit.ai.callback-signature.enabled:true}")
    private boolean enabled;

    @Value("${smartaudit.ai.callback-signature.secret:}")
    private String secret;

    @Value("${smartaudit.ai.callback-signature.allowed-skew-seconds:300}")
    private long allowedSkewSeconds;

    @Value("${smartaudit.ai.callback-signature.nonce-ttl-seconds:600}")
    private long nonceTtlSeconds;

    private final ConcurrentHashMap<String, Long> nonceExpireAt = new ConcurrentHashMap<>();

    public boolean isEnabled() {
        return enabled;
    }

    public boolean verify(
            String rawBody,
            String timestampHeader,
            String nonce,
            String signature) {
        if (!enabled) {
            return true;
        }
        if (StrUtil.hasBlank(secret, timestampHeader, nonce, signature)) {
            return false;
        }
        long now = Instant.now().getEpochSecond();
        Long ts = parseTimestamp(timestampHeader);
        if (ts == null) {
            return false;
        }
        if (Math.abs(now - ts) > Math.max(30, allowedSkewSeconds)) {
            return false;
        }
        String expected = sign(timestampHeader, nonce, StrUtil.nullToEmpty(rawBody));
        if (!StrUtil.equals(expected, signature)) {
            return false;
        }
        return markNonce(nonce, now + Math.max(60, nonceTtlSeconds), now);
    }

    public String sign(String timestamp, String nonce, String body) {
        String canonical = timestamp + "\n" + nonce + "\n" + body;
        HMac hMac = new HMac(HmacAlgorithm.HmacSHA256, secret.getBytes(StandardCharsets.UTF_8));
        return hMac.digestHex(canonical);
    }

    private Long parseTimestamp(String raw) {
        try {
            return Long.parseLong(raw.trim());
        } catch (Exception ex) {
            return null;
        }
    }

    private boolean markNonce(String nonce, long expireAt, long nowEpochSecond) {
        cleanupExpired(nowEpochSecond);
        Long existing = nonceExpireAt.putIfAbsent(nonce, expireAt);
        if (existing == null) {
            return true;
        }
        if (existing <= nowEpochSecond) {
            nonceExpireAt.put(nonce, expireAt);
            return true;
        }
        return false;
    }

    private void cleanupExpired(long nowEpochSecond) {
        Iterator<Map.Entry<String, Long>> it = nonceExpireAt.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<String, Long> entry = it.next();
            if (entry.getValue() <= nowEpochSecond) {
                it.remove();
            }
        }
    }
}
