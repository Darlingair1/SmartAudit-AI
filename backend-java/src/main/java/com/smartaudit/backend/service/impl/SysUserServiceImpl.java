package com.smartaudit.backend.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.smartaudit.backend.entity.SysUser;
import com.smartaudit.backend.mapper.SysUserMapper;
import com.smartaudit.backend.service.SysUserService;
import org.springframework.stereotype.Service;

@Service
public class SysUserServiceImpl extends ServiceImpl<SysUserMapper, SysUser> implements SysUserService {
}

