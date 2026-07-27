package com.smartaudit.backend.service.impl;

import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.smartaudit.backend.entity.AuditCallbackLog;
import com.smartaudit.backend.mapper.AuditCallbackLogMapper;
import com.smartaudit.backend.service.AuditCallbackLogService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
public class AuditCallbackLogServiceImpl extends ServiceImpl<AuditCallbackLogMapper, AuditCallbackLog>
        implements AuditCallbackLogService {

    @Override
    public AuditCallbackLog findByCallbackId(String callbackId) {
        if (StrUtil.isBlank(callbackId)) {
            return null;
        }
        return lambdaQuery()
                .eq(AuditCallbackLog::getCallbackId, callbackId)
                .last("limit 1")
                .one();
    }

    @Override
    @Transactional(propagation = Propagation.REQUIRES_NEW, rollbackFor = Exception.class)
    public void saveLogWithNewTransaction(AuditCallbackLog callbackLog) {
        if (callbackLog == null) {
            return;
        }
        try {
            save(callbackLog);
        } catch (DuplicateKeyException ex) {
            log.warn("Callback log duplicate callbackId={}, ignore insert", callbackLog.getCallbackId());
        }
    }
}

