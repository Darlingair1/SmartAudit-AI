package com.smartaudit.backend.security;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.util.ReflectionTestUtils;

class AuthInterceptorTest {

    @Test
    void shouldAllowDemoTokenWhenStrictModeDisabled() throws Exception {
        JwtTokenService tokenService = new JwtTokenService();
        AuthInterceptor interceptor = new AuthInterceptor(tokenService);
        ReflectionTestUtils.setField(interceptor, "strictAuthEnabled", false);

        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/audit/tasks");
        request.addHeader("Authorization", "Bearer demo-token");
        MockHttpServletResponse response = new MockHttpServletResponse();

        boolean allowed = interceptor.preHandle(request, response, new Object());
        Assertions.assertTrue(allowed);
        Assertions.assertNotNull(AuthContext.get());
        interceptor.afterCompletion(request, response, new Object(), null);
        Assertions.assertNull(AuthContext.get());
    }

    @Test
    void shouldRejectDemoTokenAndMissingTokenInStrictMode() {
        JwtTokenService tokenService = new JwtTokenService();
        AuthInterceptor interceptor = new AuthInterceptor(tokenService);
        ReflectionTestUtils.setField(interceptor, "strictAuthEnabled", true);

        MockHttpServletRequest demoRequest = new MockHttpServletRequest("GET", "/api/v1/audit/tasks");
        demoRequest.addHeader("Authorization", "Bearer demo-token");
        MockHttpServletResponse demoResponse = new MockHttpServletResponse();
        Assertions.assertFalse(interceptor.preHandle(demoRequest, demoResponse, new Object()));
        Assertions.assertEquals(401, demoResponse.getStatus());

        MockHttpServletRequest missingRequest = new MockHttpServletRequest("GET", "/api/v1/audit/tasks/1/file");
        MockHttpServletResponse missingResponse = new MockHttpServletResponse();
        Assertions.assertFalse(interceptor.preHandle(missingRequest, missingResponse, new Object()));
        Assertions.assertEquals(401, missingResponse.getStatus());
    }
}
