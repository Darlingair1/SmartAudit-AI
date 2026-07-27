package com.smartaudit.backend.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.smartaudit.backend.entity.AuditCallbackLog;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AuditCallbackLogMapper extends BaseMapper<AuditCallbackLog> {
}

