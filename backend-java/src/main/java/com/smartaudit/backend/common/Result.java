package com.smartaudit.backend.common;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Result<T> {

    // 业务状态码：200 表示成功，其它值表示失败原因。
    private Integer code;
    // 给前端展示或日志定位的消息文本。
    private String msg;
    // 真实业务数据载荷，失败时通常为 null。
    private T data;

    public static <T> Result<T> success() {
        return new Result<>(200, "success", null);
    }

    // 常用成功返回：统一封装 data，减少 Controller 重复代码。
    public static <T> Result<T> success(T data) {
        return new Result<>(200, "success", data);
    }

    // 自定义失败码与失败消息。
    public static <T> Result<T> fail(Integer code, String msg) {
        return new Result<>(code, msg, null);
    }

    public static <T> Result<T> fail(String msg) {
        return new Result<>(500, msg, null);
    }
}
