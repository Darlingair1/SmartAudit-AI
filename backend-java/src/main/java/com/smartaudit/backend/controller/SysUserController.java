package com.smartaudit.backend.controller;

import cn.hutool.core.util.StrUtil;
import cn.hutool.crypto.digest.BCrypt;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.smartaudit.backend.common.Result;
import com.smartaudit.backend.entity.SysUser;
import com.smartaudit.backend.security.RoleGuard;
import com.smartaudit.backend.service.SysUserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "SysUser")
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class SysUserController {

    private final SysUserService sysUserService;

    @Operation(summary = "Create user")
    @PostMapping
    public Result<SysUser> create(@RequestBody SysUser sysUser) {
        RoleGuard.requireAny("ADMIN");
        if (StrUtil.isBlank(sysUser.getPasswordHash())) {
            return Result.fail(400, "password cannot be blank");
        }
        preparePassword(sysUser);
        boolean saved = sysUserService.save(sysUser);
        if (!saved) {
            return Result.fail(500, "create user failed");
        }
        sanitizeUser(sysUser);
        return Result.success(sysUser);
    }

    @Operation(summary = "Get user by id")
    @GetMapping("/{id}")
    public Result<SysUser> getById(@PathVariable Long id) {
        RoleGuard.requireAny("ADMIN");
        SysUser user = sysUserService.getById(id);
        if (user == null) {
            return Result.fail(404, "user not found");
        }
        sanitizeUser(user);
        return Result.success(user);
    }

    @Operation(summary = "Get user page list")
    @GetMapping
    public Result<IPage<SysUser>> page(
            @RequestParam(defaultValue = "1") Long pageNum,
            @RequestParam(defaultValue = "10") Long pageSize,
            @RequestParam(required = false) String username,
            @RequestParam(required = false) String realName,
            @RequestParam(required = false) Integer status) {
        RoleGuard.requireAny("ADMIN");
        LambdaQueryWrapper<SysUser> queryWrapper = Wrappers.lambdaQuery();
        if (StrUtil.isNotBlank(username)) {
            queryWrapper.like(SysUser::getUsername, username);
        }
        if (StrUtil.isNotBlank(realName)) {
            queryWrapper.like(SysUser::getRealName, realName);
        }
        if (status != null) {
            queryWrapper.eq(SysUser::getStatus, status);
        }
        queryWrapper.orderByDesc(SysUser::getCreateTime);
        IPage<SysUser> page = sysUserService.page(new Page<>(pageNum, pageSize), queryWrapper);
        if (page.getRecords() != null) {
            page.getRecords().forEach(this::sanitizeUser);
        }
        return Result.success(page);
    }

    @Operation(summary = "Update user")
    @PutMapping("/{id}")
    public Result<Boolean> update(@PathVariable Long id, @RequestBody SysUser sysUser) {
        RoleGuard.requireAny("ADMIN");
        if (sysUserService.getById(id) == null) {
            return Result.fail(404, "user not found");
        }
        if (StrUtil.isNotBlank(sysUser.getPasswordHash())) {
            preparePassword(sysUser);
        }
        sysUser.setId(id);
        boolean updated = sysUserService.updateById(sysUser);
        if (!updated) {
            return Result.fail(500, "update user failed");
        }
        return Result.success(Boolean.TRUE);
    }

    @Operation(summary = "Delete user (logical)")
    @DeleteMapping("/{id}")
    public Result<Boolean> delete(@PathVariable Long id) {
        RoleGuard.requireAny("ADMIN");
        if (sysUserService.getById(id) == null) {
            return Result.fail(404, "user not found");
        }
        boolean deleted = sysUserService.removeById(id);
        if (!deleted) {
            return Result.fail(500, "delete user failed");
        }
        return Result.success(Boolean.TRUE);
    }

    private void sanitizeUser(SysUser user) {
        if (user != null) {
            user.setPasswordHash(null);
        }
    }

    private void preparePassword(SysUser user) {
        String raw = StrUtil.trim(user.getPasswordHash());
        if (raw.startsWith("$2a$") || raw.startsWith("$2b$") || raw.startsWith("$2y$")) {
            return;
        }
        if (!isStrongPassword(raw)) {
            throw new IllegalArgumentException("password too weak, require 8+ chars with upper/lower/digit");
        }
        user.setPasswordHash(BCrypt.hashpw(raw, BCrypt.gensalt()));
    }

    private boolean isStrongPassword(String password) {
        if (StrUtil.isBlank(password) || password.length() < 8) {
            return false;
        }
        boolean hasUpper = false;
        boolean hasLower = false;
        boolean hasDigit = false;
        for (char ch : password.toCharArray()) {
            if (Character.isUpperCase(ch)) {
                hasUpper = true;
            } else if (Character.isLowerCase(ch)) {
                hasLower = true;
            } else if (Character.isDigit(ch)) {
                hasDigit = true;
            }
        }
        return hasUpper && hasLower && hasDigit;
    }
}
