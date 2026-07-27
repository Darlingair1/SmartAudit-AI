package com.smartaudit.backend.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("audit_risk_item")
public class AuditRiskItem implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long taskId;
    private Integer seqNo;
    private String riskType;
    private String riskLevel;
    private BigDecimal riskScore;
    private String clauseTitle;
    private String clausePosition;
    private Integer pageNo;
    private String contractExcerpt;
    private String riskDesc;
    private String suggestion;
    private String legalBasis;
    private String evidence;
    private Integer reviewStatus;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic(value = "0", delval = "1")
    private Integer isDeleted;
}
