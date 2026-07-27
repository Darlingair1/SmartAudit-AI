package com.smartaudit.backend.security;

import cn.hutool.crypto.digest.BCrypt;
import com.smartaudit.backend.entity.SysUser;
import com.smartaudit.backend.service.SysUserService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.test.util.ReflectionTestUtils;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class BootstrapAdminInitializerTest {

    @Test
    void createsAdminOnlyForEmptyDatabase() throws Exception {
        SysUserService service = mock(SysUserService.class);
        when(service.count()).thenReturn(0L);
        when(service.save(any(SysUser.class))).thenReturn(true);
        BootstrapAdminInitializer initializer = initializer(service, "ValidAdmin2026");

        initializer.run(new DefaultApplicationArguments(new String[0]));

        ArgumentCaptor<SysUser> captor = ArgumentCaptor.forClass(SysUser.class);
        verify(service).save(captor.capture());
        SysUser user = captor.getValue();
        Assertions.assertEquals(1L, user.getId());
        Assertions.assertEquals("ADMIN", user.getRoleCode());
        Assertions.assertTrue(BCrypt.checkpw("ValidAdmin2026", user.getPasswordHash()));
    }

    @Test
    void skipsBootstrapWhenPasswordIsEmptyOrUsersExist() throws Exception {
        SysUserService service = mock(SysUserService.class);
        BootstrapAdminInitializer emptyPassword = initializer(service, "");
        emptyPassword.run(new DefaultApplicationArguments(new String[0]));
        verify(service, never()).count();

        when(service.count()).thenReturn(1L);
        BootstrapAdminInitializer existingUser = initializer(service, "ValidAdmin2026");
        existingUser.run(new DefaultApplicationArguments(new String[0]));
        verify(service, never()).save(any(SysUser.class));
    }

    @Test
    void rejectsWeakOrPlaceholderPassword() {
        SysUserService service = mock(SysUserService.class);
        Assertions.assertThrows(IllegalStateException.class,
                () -> initializer(service, "<REQUIRED_PASSWORD>")
                        .run(new DefaultApplicationArguments(new String[0])));
        Assertions.assertThrows(IllegalStateException.class,
                () -> initializer(service, "short")
                        .run(new DefaultApplicationArguments(new String[0])));
    }

    private BootstrapAdminInitializer initializer(SysUserService service, String password) {
        BootstrapAdminInitializer initializer = new BootstrapAdminInitializer(service);
        ReflectionTestUtils.setField(initializer, "username", "admin");
        ReflectionTestUtils.setField(initializer, "password", password);
        ReflectionTestUtils.setField(initializer, "realName", "Administrator");
        return initializer;
    }
}
