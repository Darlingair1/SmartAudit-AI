package com.smartaudit.backend.controller;

import cn.hutool.core.util.StrUtil;
import cn.hutool.crypto.digest.BCrypt;
import com.smartaudit.backend.common.Result;
import com.smartaudit.backend.dto.LoginReqDTO;
import com.smartaudit.backend.dto.LoginRespDTO;
import com.smartaudit.backend.entity.SysUser;
import com.smartaudit.backend.security.AuthPrincipal;
import com.smartaudit.backend.security.JwtTokenService;
import com.smartaudit.backend.service.SysUserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;

@Tag(name = "Auth")
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final SysUserService sysUserService;
    private final JwtTokenService jwtTokenService;

    @Operation(summary = "Login and issue JWT")
    @PostMapping("/login")
    public Result<LoginRespDTO> login(@RequestBody @Valid LoginReqDTO req) {
        SysUser user = sysUserService.lambdaQuery()
                .eq(SysUser::getUsername, StrUtil.trim(req.getUsername()))
                .eq(SysUser::getStatus, 1)
                .one();
        if (user == null) {
            return Result.fail(401, "invalid username or password");
        }
        String stored = StrUtil.blankToDefault(user.getPasswordHash(), "");
        boolean passwordOk = verifyPassword(req.getPassword(), stored);
        if (!passwordOk) {
            return Result.fail(401, "invalid username or password");
        }

        user.setLastLoginTime(LocalDateTime.now());
        sysUserService.updateById(user);

        AuthPrincipal principal = new AuthPrincipal(
                user.getId(),
                user.getUsername(),
                StrUtil.blankToDefault(user.getRoleCode(), "EMPLOYEE")
        );
        String token = jwtTokenService.createToken(principal);
        return Result.success(new LoginRespDTO(token, principal.getUserId(), principal.getUsername(), principal.getRoleCode()));
    }

    private boolean verifyPassword(String rawPassword, String storedHash) {
        if (StrUtil.hasBlank(rawPassword, storedHash)) {
            return false;
        }
        if (storedHash.startsWith("$2a$") || storedHash.startsWith("$2b$") || storedHash.startsWith("$2y$")) {
            return BCrypt.checkpw(rawPassword, storedHash);
        }
        // 兼容早期明文数据，建议迁移为 BCrypt。
        return StrUtil.equals(rawPassword, storedHash);
    }
}
