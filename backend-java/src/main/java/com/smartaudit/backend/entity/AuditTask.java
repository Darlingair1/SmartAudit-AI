package com.smartaudit.backend.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@TableName("audit_task")
public class AuditTask implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private String taskNo;
    private String taskName;
    private String fileName;
    private String fileStorageType;
    private String filePath;
    private String fileSha256;
    private Long fileSize;
    private String status;
    private Integer progress;
    private Long initiatorUserId;
    private String pythonJobId;
    private String aiModel;
    private Integer riskTotal;
    private Integer highRiskCount;
    private Integer mediumRiskCount;
    private Integer lowRiskCount;
    private String errorCode;
    private String errorMessage;
    private LocalDateTime startTime;
    private LocalDateTime completeTime;
    private String extJson;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic(value = "0", delval = "1")
    private Integer isDeleted;
}

