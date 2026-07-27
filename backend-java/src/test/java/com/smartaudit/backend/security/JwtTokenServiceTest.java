package com.smartaudit.backend.security;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class JwtTokenServiceTest {

    @Test
    void shouldCreateAndParseToken() {
        JwtTokenService tokenService = new JwtTokenService();
        ReflectionTestUtils.setField(tokenService, "jwtSecret", "jwt-secret-for-unit-test-123456");
        ReflectionTestUtils.setField(tokenService, "jwtExpireSeconds", 3600L);

        AuthPrincipal principal = new AuthPrincipal(1L, "admin", "ADMIN");
        String token = tokenService.createToken(principal);
        AuthPrincipal parsed = tokenService.parseAndVerify(token);

        Assertions.assertNotNull(parsed);
        Assertions.assertEquals(1L, parsed.getUserId());
        Assertions.assertEquals("admin", parsed.getUsername());
        Assertions.assertEquals("ADMIN", parsed.getRoleCode());
    }

    @Test
    void shouldRejectInvalidToken() {
        JwtTokenService tokenService = new JwtTokenService();
        ReflectionTestUtils.setField(tokenService, "jwtSecret", "jwt-secret-for-unit-test-123456");
        ReflectionTestUtils.setField(tokenService, "jwtExpireSeconds", 3600L);
        Assertions.assertNull(tokenService.parseAndVerify("invalid-token"));
    }
}
