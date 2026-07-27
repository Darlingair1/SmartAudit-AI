package com.smartaudit.backend.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI smartAuditOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("SmartAudit-AI Backend API")
                        .version("v1.0.0")
                        .description("SmartAudit-AI Java backend service APIs"));
    }
}

