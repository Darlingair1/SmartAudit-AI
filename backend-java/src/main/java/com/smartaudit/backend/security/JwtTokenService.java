package com.smartaudit.backend.security;

import cn.hutool.core.util.StrUtil;
import cn.hutool.core.convert.Convert;
import cn.hutool.jwt.JWT;
import cn.hutool.jwt.JWTUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

@Component
public class JwtTokenService {

    @Value("${smartaudit.security.jwt-secret:}")
    private String jwtSecret;

    @Value("${smartaudit.security.jwt-expire-seconds:7200}")
    private long jwtExpireSeconds;

    public String createToken(AuthPrincipal principal) {
        if (principal == null || principal.getUserId() == null || StrUtil.isBlank(principal.getUsername())) {
            throw new IllegalArgumentException("invalid principal");
        }
        if (StrUtil.isBlank(jwtSecret)) {
            throw new IllegalStateException("smartaudit.security.jwt-secret is not configured");
        }

        long now = Instant.now().getEpochSecond();
        long exp = now + Math.max(300, jwtExpireSeconds);
        Map<String, Object> payload = new HashMap<>();
        payload.put("uid", principal.getUserId());
        payload.put("uname", principal.getUsername());
        payload.put("role", StrUtil.blankToDefault(principal.getRoleCode(), "EMPLOYEE"));
        payload.put("iat", now);
        payload.put("exp", exp);
        return JWTUtil.createToken(payload, jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    public AuthPrincipal parseAndVerify(String token) {
        if (StrUtil.isBlank(token) || StrUtil.isBlank(jwtSecret)) {
            return null;
        }
        try {
            boolean ok = JWTUtil.verify(token, jwtSecret.getBytes(StandardCharsets.UTF_8));
            if (!ok) {
                return null;
            }
            JWT jwt = JWTUtil.parseToken(token);
            Long exp = Convert.toLong(jwt.getPayload("exp"));
            if (exp == null || exp <= Instant.now().getEpochSecond()) {
                return null;
            }
            Long uid = Convert.toLong(jwt.getPayload("uid"));
            String username = Convert.toStr(jwt.getPayload("uname"));
            String role = Convert.toStr(jwt.getPayload("role"));
            if (uid == null || StrUtil.isBlank(username)) {
                return null;
            }
            return new AuthPrincipal(uid, username, StrUtil.blankToDefault(role, "EMPLOYEE"));
        } catch (Exception ex) {
            return null;
        }
    }
}
