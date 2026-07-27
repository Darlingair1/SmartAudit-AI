package com.smartaudit.backend.common;

import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

import java.util.Objects;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleMethodArgumentNotValidException(MethodArgumentNotValidException ex) {
        String msg = extractFirstError(ex.getBindingResult(), "request validation failed");
        return Result.fail(400, msg);
    }

    @ExceptionHandler(BindException.class)
    public Result<Void> handleBindException(BindException ex) {
        String msg = extractFirstError(ex.getBindingResult(), "binding failed");
        return Result.fail(400, msg);
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public Result<Void> handleHttpMessageNotReadableException(HttpMessageNotReadableException ex) {
        return Result.fail(400, "request body is invalid");
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public Result<Void> handleIllegalArgumentException(IllegalArgumentException ex) {
        return Result.fail(400, ex.getMessage());
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public Result<Void> handleMaxUploadSizeExceededException(MaxUploadSizeExceededException ex) {
        return Result.fail(413, "upload file is too large, max size is 30MB");
    }

    @ExceptionHandler(SecurityException.class)
    public Result<Void> handleSecurityException(SecurityException ex, HttpServletResponse response) {
        int code = "forbidden".equalsIgnoreCase(ex.getMessage()) ? 403 : 401;
        response.setStatus(code);
        return Result.fail(code, ex.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception ex) {
        log.error("Unhandled exception", ex);
        return Result.fail(500, "internal server error");
    }

    private String extractFirstError(BindingResult bindingResult, String defaultMsg) {
        FieldError fieldError = bindingResult.getFieldError();
        if (Objects.isNull(fieldError)) {
            return defaultMsg;
        }
        return fieldError.getField() + ": " + fieldError.getDefaultMessage();
    }
}
