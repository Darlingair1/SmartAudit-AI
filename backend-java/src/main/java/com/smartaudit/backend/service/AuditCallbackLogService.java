package com.smartaudit.backend.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.smartaudit.backend.entity.AuditCallbackLog;

public interface AuditCallbackLogService extends IService<AuditCallbackLog> {

    AuditCallbackLog findByCallbackId(String callbackId);

    void saveLogWithNewTransaction(AuditCallbackLog callbackLog);
}

