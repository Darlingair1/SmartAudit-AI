package com.smartaudit.backend.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.smartaudit.backend.entity.AuditTask;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AuditTaskMapper extends BaseMapper<AuditTask> {
}

