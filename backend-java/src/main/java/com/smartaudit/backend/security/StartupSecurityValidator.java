package com.smartaudit.backend.security;

import cn.hutool.core.util.StrUtil;
import lombok.extern.slf4j.Slf4j;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

@Slf4j
@Component
@RequiredArgsConstructor
public class StartupSecurityValidator implements ApplicationRunner {

    private static final int MIN_SECRET_LENGTH = 32;

    private static final Set<String> WEAK_VALUES = Set.of(
            "changeme",
            "change-me",
            "your_callback_token",
            "your-secret",
            "default",
            "demo",
            "123456",
            "password"
    );

    @Value("${smartaudit.security.fail-on-default-secrets:true}")
    private boolean failOnDefaultSecrets;

    @Value("${smartaudit.security.strict-auth-enabled:false}")
    private boolean strictAuthEnabled;

    @Value("${smartaudit.security.jwt-secret:}")
    private String jwtSecret;

    @Value("${smartaudit.ai.callback-token:}")
    private String callbackToken;

    @Value("${smartaudit.ai.python-internal-token:}")
    private String internalToken;

    @Value("${smartaudit.ai.callback-signature.enabled:true}")
    private boolean callbackSignatureEnabled;

    @Value("${smartaudit.ai.callback-signature.secret:}")
    private String callbackSignatureSecret;

    @Value("${spring.datasource.username:}")
    private String dbUsername;

    @Value("${spring.datasource.password:}")
    private String dbPassword;

    private final Environment environment;

    @Override
    public void run(ApplicationArguments args) {
        boolean production = List.of(environment.getActiveProfiles()).stream()
                .anyMatch(profile -> "prod".equalsIgnoreCase(profile) || "production".equalsIgnoreCase(profile));
        if (production && !strictAuthEnabled) {
            throw new IllegalStateException("security preflight check failed: strict authentication is required in production");
        }
        if (production && !failOnDefaultSecrets) {
            throw new IllegalStateException("security preflight check failed: secret validation cannot be disabled in production");
        }
        if (!failOnDefaultSecrets) {
            log.warn("Security startup checks are disabled by smartaudit.security.fail-on-default-secrets=false");
            return;
        }
        List<String> errors = new ArrayList<>();

        if (StrUtil.isBlank(dbUsername) || StrUtil.isBlank(dbPassword)) {
            errors.add("database credentials must not be blank");
        }
        if (isWeakSecret(callbackToken)) {
            errors.add("smartaudit.ai.callback-token is blank or weak");
        }
        if (callbackSignatureEnabled && isWeakSecret(callbackSignatureSecret)) {
            errors.add("smartaudit.ai.callback-signature.secret is blank or weak");
        }
        if (strictAuthEnabled) {
            if (isWeakSecret(jwtSecret)) {
                errors.add("smartaudit.security.jwt-secret is blank or weak");
            }
            if (isWeakSecret(internalToken)) {
                errors.add("smartaudit.ai.python-internal-token is blank or weak");
            }
        }

        if (!errors.isEmpty()) {
            throw new IllegalStateException("security preflight check failed: " + String.join("; ", errors));
        }
    }

    private boolean isWeakSecret(String raw) {
        if (StrUtil.isBlank(raw)) {
            return true;
        }
        String normalized = raw.trim().toLowerCase();
        return normalized.length() < MIN_SECRET_LENGTH || WEAK_VALUES.contains(normalized)
                || normalized.startsWith("<required_") || normalized.startsWith("<same_as_");
    }
}
