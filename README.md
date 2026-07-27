# SmartAudit-AI

## 0. 测试前必读（先配置再启动）

请先完成以下 4 步，再运行 `start-smartaudit.bat`。  
如果跳过，最常见现象是：页面可打开，但创建任务/触发审查报错（500）。

### 0.1 必做 4 步（按顺序）

1. **创建 MySQL 空库**
- Flyway 会在 Java 后端首次启动时自动创建和迁移表结构。
- `docs/smartaudit_schema.sql` 仅作为结构参考，不要再手工导入，以免与 Flyway 迁移状态冲突。
- 命令：`mysql -h 127.0.0.1 -P 3306 -u root -p -e "CREATE DATABASE IF NOT EXISTS smartaudit_ai DEFAULT CHARACTER SET utf8mb4;"`

2. **配置 Java 数据库连接**
- 配置位置：`backend-java/src/main/resources/application.yml`
- 推荐用环境变量：`DB_URL`、`DB_USER`、`DB_PASS`

3. **配置 Python 模型参数**
- 模板文件：`ai-python/.env.example`
- 复制为：`ai-python/.env`
- 至少填写：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`LLM_MODEL`（默认 `deepseek-v4-flash`）

4. **配置回调鉴权 + 初始用户**
- 环境变量：`SMARTAUDIT_CALLBACK_TOKEN`（Java/Python 回调一致）
- 环境变量：`SMARTAUDIT_JWT_SECRET`（后端 JWT 签名密钥）
- 环境变量：`SMARTAUDIT_AI_INTERNAL_TOKEN` / `INTERNAL_API_TOKEN`（Java->Python 内部调用令牌，需一致）
- 环境变量：`SMARTAUDIT_CALLBACK_SIGNATURE_SECRET` / `CALLBACK_SIGNATURE_SECRET`（Python 回调签名密钥，需一致）
- 首次空库启动时填写 `SMARTAUDIT_BOOTSTRAP_ADMIN_PASSWORD`；系统只会在用户表为空时创建管理员，首次登录后应从配置中移除该变量。

### 0.1.1 推荐：统一配置文件（最省事）

建议直接在项目根目录执行：
- 复制 `env.deploy.example` 为 `env.deploy`
- 在 `env.deploy` 中一次性填写 Java + Python 的关键配置
- 启动脚本 `start-smartaudit.bat` 会自动加载该文件

> `env.deploy` 已加入 `.gitignore`，不会被提交。

### 0.2 配置示例（Windows PowerShell）

```powershell
# 1) 创建空库；表结构由 Flyway 在后端启动时自动迁移
mysql -h 127.0.0.1 -P 3306 -u root -p -e "CREATE DATABASE IF NOT EXISTS smartaudit_ai DEFAULT CHARACTER SET utf8mb4;"

# 2) Java 数据库配置
$env:DB_URL="jdbc:mysql://127.0.0.1:3306/smartaudit_ai?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true"
$env:DB_USER="root"
$env:DB_PASS="你的数据库密码"

# 3) 回调鉴权
$env:SMARTAUDIT_CALLBACK_TOKEN="your_callback_token"
$env:SMARTAUDIT_JWT_SECRET="your_long_random_jwt_secret"
$env:SMARTAUDIT_AI_INTERNAL_TOKEN="your_internal_token"
$env:SMARTAUDIT_CALLBACK_SIGNATURE_SECRET="your_callback_sign_secret"
```

> 4) AI 密钥与 Python 内部令牌请编辑 `ai-python/.env`（由 `.env.example` 复制而来），不要提交真实密钥。  
> 其中 `INTERNAL_API_TOKEN` 要与 `SMARTAUDIT_AI_INTERNAL_TOKEN` 一致，`CALLBACK_SIGNATURE_SECRET` 要与 `SMARTAUDIT_CALLBACK_SIGNATURE_SECRET` 一致。
> 若使用 `env.deploy`，上述变量可统一写在 `env.deploy`，`start-smartaudit.bat` 会自动注入。

### 0.3 首次拉起（仅第一次需要）

```powershell
# Java 依赖（仓库自带 Maven Wrapper，Java 21）
.\backend-java\mvnw.cmd -f backend-java\pom.xml -DskipTests package

# Python 依赖（建议使用虚拟环境后执行）
python -m pip install -r ai-python/requirements.lock.txt

# 前端依赖
npm --prefix frontend install
```

支持版本：Java 21、Maven 3.9（或仓库 Wrapper）、Node.js 20+、npm 10+、Python 3.10-3.12、MySQL 8.0+。Linux/macOS 可执行 `./start-smartaudit.sh`；需要包含 MySQL 的完整隔离环境时执行 `docker compose up --build`（首次运行前复制 `env.deploy.example` 和 `ai-python/.env.example`）。

---

## 1. 项目概述

**SmartAudit-AI** 是一套面向企业法务/采购的合同与招投标文件智能审查系统。  
系统目标是将“人工逐页审阅”升级为“AI 辅助审阅 + 结构化风险输出”，显著缩短审查时间并降低漏审风险。

---

## 2. 解决的核心业务问题

在传统流程中，合同审查存在以下痛点：
- 文件长（几十到上百页），人工审阅耗时高
- 重点条款容易遗漏（如违约金、付款周期、知识产权、争议解决）
- 审查输出不统一，难复盘、难统计

本项目提供：
- 自动提取高/中/低风险
- 输出结构化风险明细（原文片段、分析原因、建议、法律依据）
- 任务全流程可跟踪（待处理、处理中、完成、失败）

---

## 3. 当前可演示能力（MVP+）

1. 上传 PDF 后创建审查任务
2. 一键触发 AI 审查（异步）
3. Java 与 Python 微服务回调闭环
4. 前端实时查看任务状态（SSE 推送）
5. 详情页展示风险统计与风险列表
6. PDF 本地预览，支持与风险内容联动定位
7. 删除任务时可联动清理对应本地 PDF

---

## 4. 系统架构（管理视角）

- 前端管理台：Vue3 + Element Plus
- 业务中台：Java Spring Boot + MySQL
- AI 引擎：Python FastAPI + LangChain

**处理模式**：异步回调架构（适合大模型 1-3 分钟处理时延）
- 前端发起任务 -> Java 落库 -> 调用 Python
- Python 受理后后台执行审查
- 审查完成后回调 Java
- Java 更新任务与风险明细并通知前端刷新

---

## 5. 本地部署与启动方式

### 5.1 一键启动（推荐）

项目根目录执行：

```bat
start-smartaudit.bat
```

该脚本会启动 3 个服务：
- Java 后端：`http://localhost:8080`
- Python AI：`http://localhost:8000`
- 前端页面：`http://localhost:5173`

> 当前仓库已保留单窗口一键启动脚本，便于演示和统一关停。

### 5.2 访问地址

- 业务页面：`http://localhost:5173`
- 后端接口文档（Swagger）：`http://localhost:8080/swagger-ui.html`
- AI 健康检查：`http://localhost:8000/health`

---

## 6. 登录与初始账号说明

### 6.1 前端登录（演示模式）

当前后端已支持 **账号密码登录换取 JWT**：
- 登录接口：`POST /api/v1/auth/login`
- 参数：`username`, `password`
- 返回：`token`（前端 `Authorization: Bearer <token>`）

兼容模式说明：
- 当 `SMARTAUDIT_STRICT_AUTH_ENABLED=false` 时，仍允许 `demo-token` 便于本地演示。
- 生产建议开启 `SMARTAUDIT_STRICT_AUTH_ENABLED=true`。

### 6.2 数据库初始用户（业务必需）

由于任务表有发起人外键，数据库需保证至少存在 1 条用户记录。首次空库启动时可配置：
- `SMARTAUDIT_BOOTSTRAP_ADMIN_USERNAME=admin`
- `SMARTAUDIT_BOOTSTRAP_ADMIN_PASSWORD=<至少 12 位且包含大小写字母和数字>`

系统仅在用户表为空时创建引导管理员：
- `sys_user.id = 1`
- `username = admin`
- `role_code = ADMIN`

首次登录成功后应删除 `SMARTAUDIT_BOOTSTRAP_ADMIN_PASSWORD`，后续用户通过管理员接口维护。系统不会提供固定默认密码。

---

## 7. MySQL 交付与初始化要求（重点）

本节已合并到 **第 0 节（测试前必读）**，只保留核心信息：
- MySQL 版本：8.x（`utf8mb4`）
- 数据库迁移：`backend-java/src/main/resources/db/migration/`
- 结构参考：`docs/smartaudit_schema.sql`
- 默认库名：`smartaudit_ai`
- Java 数据源配置：`backend-java/src/main/resources/application.yml`

---

## 8. 安全与合规（当前状态）

已实现：
- 回调接口 Token 校验（防伪造回调）
- 本地受控目录读写（限制文件路径，禁止远程 URL 直读）
- 任务与回调日志留痕
- JWT 严格鉴权与基于角色的接口授权
- SSE 携带 Authorization Header 的鉴权连接
- PDF 文件头、类型、大小、文件名与托管路径校验
- 回调签名、时间窗、Nonce 重放防护和请求频率限制
- 生产环境弱密钥启动阻断和任务/PDF 定期清理

建议生产部署继续补齐：
- 企业 SSO 和组织级数据隔离
- 密钥托管与配置加密
- 数据脱敏与审计报表

漏洞报告方式见 [SECURITY.md](SECURITY.md)，数据保留和删除行为见 [docs/DATA_RETENTION.md](docs/DATA_RETENTION.md)。

---

## 9. 验收建议（给项目经理）

建议按以下 6 步做演示验收：
1. 启动系统并进入首页
2. 上传一份合同 PDF 创建任务
3. 点击“开始 AI 审查”
4. 观察状态从 `PENDING/PROCESSING` 到 `COMPLETED`
5. 检查风险统计与风险明细是否生成
6. 删除任务，确认关联 PDF 已清理

---

## 10. 里程碑与后续规划

### 已完成
- 端到端闭环（上传 -> AI -> 回调 -> 展示）
- 本地部署可运行版本
- SSE 实时刷新
- 风险明细结构化落库

### 下一阶段建议
- 引入向量检索（Embedding + VectorDB）提升长文召回质量
- 增加规则引擎与行业模板（金融/制造/政企）
- 增加审查报告导出（PDF/Word）
- 对接组织权限体系与操作审计

---

## 11. 项目资料索引

- 数据库 DDL：`docs/smartaudit_schema.sql`
- 接口契约：`docs/smartaudit_api.md`
- Java 后端：`backend-java/`
- Python AI：`ai-python/`
- 前端项目：`frontend/`

---

## 12. 说明

本 README 面向管理与验收阅读，强调业务价值、交付状态与部署要点。  
如需开发细节（类设计、行级代码说明、调参方案），可在评审会提供技术版说明文档。

---

## 13. 许可证、第三方组件与合规说明

### 13.1 项目许可证与商用

SmartAudit-AI 的原创代码及随项目提供的虚构测试样本采用 [Apache License 2.0](LICENSE)。在遵守许可证、保留版权与 `NOTICE` 声明的前提下，可以使用、修改、分发和商用本项目。

第三方组件仍适用各自许可证，不因本项目采用 Apache-2.0 而改变。直接依赖、PDF.js 二进制资源、字体、WASM、本地模型和外部服务的许可边界见 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)。

### 13.2 测试数据

仓库不分发合同 PDF 测试样本。用于本地演示或测试的 PDF 应由使用者自行准备，并确保不包含真实个人、客户或机密信息。`storage/`、`backend-java/storage/`、数据库和其他本地 PDF 属于运行数据，不在开源授权范围内，也不会进入 Git 仓库。

### 13.3 合同数据与 DeepSeek

启用 DeepSeek 审查时，系统会从 PDF 提取合同正文，并将完成审查所需的正文片段、提示词和上下文通过网络发送到配置的 DeepSeek API 地址。DeepSeek 是独立的第三方服务，其数据处理适用 DeepSeek 当前的服务条款、隐私政策、价格和所在地区法律；本项目不随仓库分发 DeepSeek 模型或平台代码。

请勿在没有合法依据和必要授权时上传个人信息、商业秘密、受保密义务约束的合同或其他敏感数据。部署者应根据所在地法律和组织政策评估跨境传输、数据保留、访问控制及供应商合规要求，并向最终用户提供适当的隐私告知。需要完全本地处理时，应关闭外部 API 并配置符合要求的本地模型服务。

### 13.4 本地 BGE 模型

`BAAI/bge-m3`（MIT）和 `BAAI/bge-reranker-v2-m3`（Apache-2.0）仅作为可选本地模型使用。模型权重位于被忽略的 `models/`，不会提交或打入公开发布包；下载和使用时仍应复核上游最新模型卡及许可条款。

### 13.5 免责声明

本项目及其 AI 输出仅用于辅助合同信息整理和风险提示，不构成法律意见、律师服务或对合同效力与风险的保证。生成式模型可能产生遗漏、不准确或虚构内容，使用者必须结合合同原文、实际交易背景和适用法律进行人工复核，并在必要时咨询具备相应资质的法律专业人士。
