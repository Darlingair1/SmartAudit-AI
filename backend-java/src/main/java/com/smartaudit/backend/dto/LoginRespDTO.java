package com.smartaudit.backend.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class LoginRespDTO {
    private String token;
    private Long userId;
    private String username;
    private String roleCode;
}
