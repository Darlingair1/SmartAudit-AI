package com.smartaudit.backend.dto;

import com.smartaudit.backend.entity.AuditRiskItem;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Data
public class AuditTaskDetailRespDTO {

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
    private Integer isDeleted;

    private List<RiskItemDTO> riskItems = new ArrayList<>();

    @Data
    public static class RiskItemDTO {
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
    }

    public static RiskItemDTO fromEntity(AuditRiskItem entity) {
        if (entity == null) {
            return null;
        }
        RiskItemDTO dto = new RiskItemDTO();
        dto.setId(entity.getId());
        dto.setTaskId(entity.getTaskId());
        dto.setSeqNo(entity.getSeqNo());
        dto.setRiskType(entity.getRiskType());
        dto.setRiskLevel(entity.getRiskLevel());
        dto.setRiskScore(entity.getRiskScore());
        dto.setClauseTitle(entity.getClauseTitle());
        dto.setClausePosition(entity.getClausePosition());
        dto.setPageNo(entity.getPageNo());
        dto.setContractExcerpt(entity.getContractExcerpt());
        dto.setRiskDesc(entity.getRiskDesc());
        dto.setSuggestion(entity.getSuggestion());
        dto.setLegalBasis(entity.getLegalBasis());
        dto.setEvidence(entity.getEvidence());
        dto.setReviewStatus(entity.getReviewStatus());
        return dto;
    }
}
