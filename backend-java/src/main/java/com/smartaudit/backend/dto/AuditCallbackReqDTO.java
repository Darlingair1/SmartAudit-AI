package com.smartaudit.backend.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class AuditCallbackReqDTO {

    private String callbackId;
    private String taskId;
    private String taskNo;
    private String pythonJobId;
    private String status;
    private String finishedAt;
    private SummaryDTO summary;
    private List<RiskItemDTO> riskItems;
    private ErrorDTO error;

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class SummaryDTO {
        private Integer riskTotal;
        private Integer highRiskCount;
        private Integer mediumRiskCount;
        private Integer lowRiskCount;
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class RiskItemDTO {
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
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class ErrorDTO {
        private String code;
        private String message;
    }
}
