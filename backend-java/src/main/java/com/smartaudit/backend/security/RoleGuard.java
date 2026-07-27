package com.smartaudit.backend.security;

import cn.hutool.core.util.StrUtil;

public final class RoleGuard {

    private RoleGuard() {
    }

    public static void requireAny(String... allowedRoles) {
        AuthPrincipal principal = AuthContext.get();
        if (principal == null) {
            throw new SecurityException("unauthorized");
        }
        String role = StrUtil.blankToDefault(principal.getRoleCode(), "EMPLOYEE").toUpperCase();
        for (String allowedRole : allowedRoles) {
            if (role.equalsIgnoreCase(allowedRole)) {
                return;
            }
        }
        throw new SecurityException("forbidden");
    }
}
