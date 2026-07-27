# SmartAudit-AI 接口设计文档

## 1. 架构合理性简析（异步回调）
采用 `前端 -> Java -> Python -> Java Callback` 的异步架构，核心价值是将 1-3 分钟的大模型处理从同步链路中拆出：

1. 前端提交后立即拿到 `taskId`，避免长连接超时。
2. Java 聚焦鉴权、状态流转、事务落库；Python 聚焦 RAG 与推理，职责边界清晰。
3. 通过 `callbackId` 幂等去重 + 回调日志，可保证失败重试和最终一致性。
4. 双服务可独立扩缩容，吞吐能力更高，便于企业级可观测与审计。

---

## 2. 统一返回格式（Java 端）

```json
{
  "code": 200,
  "msg": "success",
  "data": {}
}
```

---

## 3. 核心 API

### 3.1 [前端 -> Java] 提交合同审查任务

| 项 | 内容 |
|---|---|
| Method | `POST` |
| URL | `/api/v1/audit/tasks` |
| Content-Type | `multipart/form-data` |
| 鉴权 | `Authorization: Bearer <JWT>` |
| 幂等建议 | `Idempotency-Key` 请求头 |

请求参数：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `taskName` | string | 是 | 任务名称 |
| `file` | file(PDF) | 是 | 合同 PDF 文件 |
| `ruleSetCodes` | string | 否 | 风险规则集编码，逗号分隔 |
| `bizNo` | string | 否 | 业务单号 |

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "191234567890123456",
    "taskNo": "AT202602240001",
    "status": "PENDING",
    "createTime": "2026-02-24 10:12:23"
  }
}
```

### 3.2 [前端 -> Java] 查询单个审查任务详情（含风险明细）

| 项 | 内容 |
|---|---|
| Method | `GET` |
| URL | `/api/v1/audit/tasks/{taskId}` |
| 鉴权 | `Authorization: Bearer <JWT>` |

路径参数：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `taskId` | string(long) | 是 | 审查任务ID |

响应示例：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "191234567890123456",
    "taskNo": "AT202602240001",
    "taskName": "采购合同审查",
    "status": "COMPLETED",
    "progress": 100,
    "fileName": "采购合同V3.pdf",
    "filePath": "oss://smartaudit/contracts/2026/02/24/abc.pdf",
    "initiatorUserId": "10001",
    "riskSummary": {
      "total": 3,
      "high": 1,
      "medium": 1,
      "low": 1
    },
    "riskItems": [
      {
        "id": "191234567890123999",
        "seqNo": 1,
        "riskType": "违约责任",
        "riskLevel": "HIGH",
        "riskScore": 92.5,
        "clauseTitle": "违约金条款",
        "clausePosition": "P12-第3段",
        "contractExcerpt": "乙方违约需按合同总额30%支付违约金...",
        "riskDesc": "违约金比例显著偏高，可能导致重大财务风险。",
        "suggestion": "建议改为“以实际损失为基础，且不超过合同总额的10%”。",
        "legalBasis": "民法典合同编公平原则"
      }
    ],
    "createTime": "2026-02-24 10:12:23",
    "updateTime": "2026-02-24 10:15:41"
  }
}
```

### 3.3 [Java -> Python] 触发 AI 审查（异步受理）

| 项 | 内容 |
|---|---|
| Method | `POST` |
| URL | `/internal/v1/ai/audit/jobs` |
| Content-Type | `application/json` |
| 鉴权 | 内网 + mTLS/HMAC（建议） |
| 语义 | Python 仅返回“已受理”，后台异步处理 |

请求报文：

```json
{
  "taskId": "191234567890123456",
  "taskNo": "AT202602240001",
  "filePath": "oss://smartaudit/contracts/2026/02/24/abc.pdf",
  "fileName": "采购合同V3.pdf",
  "callbackUrl": "https://java.example.com/api/v1/internal/audit/tasks/callback",
  "callbackToken": "hmac-secret-id-01",
  "modelName": "deepseek-v4-flash",
  "ruleSetCodes": ["PENALTY", "PAYMENT_TERM", "TERMINATION"],
  "traceId": "trace-8f2d7a31"
}
```

响应报文（Python）：

```json
{
  "accepted": true,
  "status": "ACCEPTED",
  "pythonJobId": "pyjob_20260224_00001",
  "message": "task queued"
}
```

### 3.4 [Python -> Java] AI 审查完成异步回调

| 项 | 内容 |
|---|---|
| Method | `POST` |
| URL | `/api/v1/internal/audit/tasks/callback` |
| Content-Type | `application/json` |
| 鉴权 | `X-Signature` + `X-Timestamp` + `X-Nonce`（HMAC） |
| 幂等键 | `callbackId`（唯一） |

请求报文：

```json
{
  "callbackId": "cb_20260224_000001",
  "taskId": "191234567890123456",
  "taskNo": "AT202602240001",
  "pythonJobId": "pyjob_20260224_00001",
  "status": "COMPLETED",
  "finishedAt": "2026-02-24 10:15:40",
  "summary": {
    "riskTotal": 3,
    "highRiskCount": 1,
    "mediumRiskCount": 1,
    "lowRiskCount": 1
  },
  "riskItems": [
    {
      "seqNo": 1,
      "riskType": "违约责任",
      "riskLevel": "HIGH",
      "riskScore": 92.5,
      "clauseTitle": "违约金条款",
      "clausePosition": "P12-第3段",
      "contractExcerpt": "乙方违约需按合同总额30%支付违约金...",
      "riskDesc": "违约金比例显著偏高，可能导致重大财务风险。",
      "suggestion": "建议改为“以实际损失为基础，且不超过合同总额的10%”。",
      "legalBasis": "民法典合同编公平原则",
      "evidence": "历史司法案例相似条款判罚偏高"
    }
  ],
  "error": null
}
```

Java 回调响应（统一封装）：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "ack": true,
    "taskId": "191234567890123456",
    "updatedStatus": "COMPLETED"
  }
}
```

失败回调示例（`status=FAILED`）：

```json
{
  "callbackId": "cb_20260224_000002",
  "taskId": "191234567890123456",
  "taskNo": "AT202602240001",
  "pythonJobId": "pyjob_20260224_00001",
  "status": "FAILED",
  "finishedAt": "2026-02-24 10:15:40",
  "summary": {
    "riskTotal": 0,
    "highRiskCount": 0,
    "mediumRiskCount": 0,
    "lowRiskCount": 0
  },
  "riskItems": [],
  "error": {
    "code": "MODEL_TIMEOUT",
    "message": "LLM inference timeout after 180s"
  }
}
```
