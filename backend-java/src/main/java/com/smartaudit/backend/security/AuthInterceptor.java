package com.smartaudit.backend.security;

import cn.hutool.core.util.StrUtil;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

@Component
public class AuthInterceptor implements HandlerInterceptor {

    private final JwtTokenService jwtTokenService;

    @Value("${smartaudit.security.strict-auth-enabled:false}")
    private boolean strictAuthEnabled;

    public AuthInterceptor(JwtTokenService jwtTokenService) {
        this.jwtTokenService = jwtTokenService;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String path = StrUtil.blankToDefault(request.getRequestURI(), "");
        if (path.startsWith("/api/v1/internal/") || path.startsWith("/api/v1/auth/")) {
            return true;
        }

        String authHeader = request.getHeader("Authorization");
        String token = parseBearerToken(authHeader);
        AuthPrincipal principal = jwtTokenService.parseAndVerify(token);

        // 非严格模式允许 demo token 便于本地演示；严格模式只接受签名 JWT。
        if (principal == null && !strictAuthEnabled && "demo-token".equals(token)) {
            principal = new AuthPrincipal(1L, "demo", "ADMIN");
        }

        if (principal == null) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json;charset=UTF-8");
            try {
                response.getWriter().write("{\"code\":401,\"msg\":\"unauthorized\",\"data\":null}");
            } catch (Exception ignored) {
                // no-op
            }
            return false;
        }
        AuthContext.set(principal);
        return true;
    }

    @Override
    public void afterCompletion(
            HttpServletRequest request,
            HttpServletResponse response,
            Object handler,
            Exception ex) {
        AuthContext.clear();
    }

    private String parseBearerToken(String authHeader) {
        if (StrUtil.isBlank(authHeader)) {
            return "";
        }
        String prefix = "Bearer ";
        if (!StrUtil.startWithIgnoreCase(authHeader, prefix)) {
            return "";
        }
        return StrUtil.trim(authHeader.substring(prefix.length()));
    }
}
