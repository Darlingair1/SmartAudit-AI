package com.smartaudit.backend.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertThrows;

class StartupSecurityValidatorTest {

    @Test
    void productionRejectsDisabledStrictAuthentication() {
        MockEnvironment environment = new MockEnvironment();
        environment.setActiveProfiles("prod");
        StartupSecurityValidator validator = new StartupSecurityValidator(environment);
        ReflectionTestUtils.setField(validator, "strictAuthEnabled", false);
        ReflectionTestUtils.setField(validator, "failOnDefaultSecrets", true);
        assertThrows(IllegalStateException.class, () -> validator.run(null));
    }

    @Test
    void rejectsShortSecrets() {
        MockEnvironment environment = new MockEnvironment();
        StartupSecurityValidator validator = new StartupSecurityValidator(environment);
        ReflectionTestUtils.setField(validator, "strictAuthEnabled", true);
        ReflectionTestUtils.setField(validator, "failOnDefaultSecrets", true);
        ReflectionTestUtils.setField(validator, "dbUsername", "root");
        ReflectionTestUtils.setField(validator, "dbPassword", "database-password");
        ReflectionTestUtils.setField(validator, "callbackToken", "short");
        ReflectionTestUtils.setField(validator, "callbackSignatureEnabled", true);
        ReflectionTestUtils.setField(validator, "callbackSignatureSecret", "short");
        ReflectionTestUtils.setField(validator, "jwtSecret", "short");
        ReflectionTestUtils.setField(validator, "internalToken", "short");
        assertThrows(IllegalStateException.class, () -> validator.run(null));
    }
}
