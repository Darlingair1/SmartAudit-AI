INSERT INTO sys_user (id, username, password_hash, role_code, status, is_deleted)
VALUES (1, 'e2e-admin', 'E2ePass1234!', 'ADMIN', 1, 0)
ON DUPLICATE KEY UPDATE username = VALUES(username), password_hash = VALUES(password_hash), role_code = VALUES(role_code), status = 1, is_deleted = 0;
