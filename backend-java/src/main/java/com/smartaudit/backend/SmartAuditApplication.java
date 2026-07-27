package com.smartaudit.backend;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
// 扫描 MyBatis-Plus 的 Mapper 接口，避免每个 Mapper 单独加注解。
@MapperScan("com.smartaudit.backend.mapper")
public class SmartAuditApplication {

    public static void main(String[] args) {
        // Spring Boot 应用启动入口：初始化 IOC 容器、Web 容器、自动配置。
        SpringApplication.run(SmartAuditApplication.class, args);
    }
}
