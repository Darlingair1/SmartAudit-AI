package com.smartaudit.backend.security;

import cn.hutool.core.util.StrUtil;
import cn.hutool.crypto.digest.BCrypt;
import com.smartaudit.backend.entity.SysUser;
import com.smartaudit.backend.service.SysUserService;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class BootstrapAdminInitializer implements ApplicationRunner {

    private final SysUserService sysUserService;

    @Value("${smartaudit.security.bootstrap-admin.username:admin}")
    private String username;

    @Value("${smartaudit.security.bootstrap-admin.password:}")
    private String password;

    @Value("${smartaudit.security.bootstrap-admin.real-name:Bootstrap Administrator}")
    private String realName;

    @Override
    public void run(ApplicationArguments args) {
        String rawPassword = StrUtil.trim(password);
        if (StrUtil.isBlank(rawPassword)) {
            return;
        }
        validatePassword(rawPassword);
        if (sysUserService.count() > 0) {
            return;
        }

        SysUser admin = new SysUser();
        admin.setId(1L);
        admin.setUsername(StrUtil.blankToDefault(StrUtil.trim(username), "admin"));
        admin.setPasswordHash(BCrypt.hashpw(rawPassword, BCrypt.gensalt()));
        admin.setRealName(StrUtil.blankToDefault(StrUtil.trim(realName), "Bootstrap Administrator"));
        admin.setRoleCode("ADMIN");
        admin.setStatus(1);
        if (!sysUserService.save(admin)) {
            throw new IllegalStateException("failed to create bootstrap administrator");
        }
    }

    private void validatePassword(String value) {
        boolean hasUpper = value.chars().anyMatch(Character::isUpperCase);
        boolean hasLower = value.chars().anyMatch(Character::isLowerCase);
        boolean hasDigit = value.chars().anyMatch(Character::isDigit);
        if (value.startsWith("<") || value.length() < 12 || !hasUpper || !hasLower || !hasDigit) {
            throw new IllegalStateException(
                    "SMARTAUDIT_BOOTSTRAP_ADMIN_PASSWORD must contain 12+ characters with upper/lower/digit");
        }
    }
}
