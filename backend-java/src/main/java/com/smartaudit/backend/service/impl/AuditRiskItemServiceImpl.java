package com.smartaudit.backend.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.smartaudit.backend.entity.AuditRiskItem;
import com.smartaudit.backend.mapper.AuditRiskItemMapper;
import com.smartaudit.backend.service.AuditRiskItemService;
import org.springframework.stereotype.Service;

@Service
public class AuditRiskItemServiceImpl extends ServiceImpl<AuditRiskItemMapper, AuditRiskItem>
        implements AuditRiskItemService {
}

