# SmartAudit-AI 开源改造路线图

> 创建日期：2026-07-25  
> 当前状态：阶段 1 至阶段 5 已完成，阶段 6 进行中
> 维护规则：所有阶段初始状态均为“未完成”。只有在交付物完成且验收标准全部通过后，才能将阶段状态改为“已完成”，并勾选对应任务。

## 状态约定

| 标记 | 含义 |
| --- | --- |
| `未完成` | 尚未开始，或仍有任务、验证、文档未完成 |
| `进行中` | 已开始实施，但尚未通过本阶段全部验收 |
| `已完成` | 本阶段任务全部完成，并通过验收标准 |
| `[ ]` | 待完成任务 |
| `[x]` | 已完成且已验证任务 |

## 总体发布门槛

首次公开 GitHub 仓库前，至少必须完成阶段 1 至阶段 4。阶段 5 至阶段 7 可以在首个公开版本前后持续推进，但每个公开 Release 必须通过阶段 6 定义的发布检查。

---

## 阶段 1：敏感信息与仓库清理

**状态：已完成**

### 目标

保证任何真实密钥、运行数据、大模型权重、本地构建产物和开发机配置不会进入 Git 历史。

### 任务

- [x] 核查 `env.deploy` 中的数据库密码、JWT Secret、回调 Token、内部 Token 和签名 Secret；已轮换应用内部密钥，并确认仅限本机、从未外泄的数据库密码无需轮换。
- [x] 轮换 `ai-python/.env` 中的内部 Token、签名 Secret 和其他有效凭证。
- [x] 将 `env.deploy.example`、`ai-python/.env.example` 中的敏感值统一替换为明显占位符。
- [x] 确认示例配置不包含可直接用于部署的固定默认密钥。
- [x] 扩充 `.gitignore`，至少排除：
  - `models/`
  - `release/`
  - `frontend/dist/`
  - `backend-java/target/`
  - `backend-java/.m2/`
  - `*.bak`
  - `*.zip`
  - 虚拟环境、日志、运行存储、缓存文件和 IDE 配置
- [x] 移除或归档 `start-smartaudit.bat.bak`、旧交付包、构建产物和性能测试残留。
- [x] 决定测试 PDF 是否允许公开；允许公开时补充“虚构样本”与许可说明，否则从仓库移除。
- [x] 添加密钥扫描配置，并使用 Gitleaks 对待提交文件执行扫描。
- [x] 在首次 `git init` 和首次提交前检查 Git 暂存清单。

### 验收标准

- [x] Gitleaks 扫描结果为零有效密钥泄漏。
- [x] `git status --short` 中不出现 `.env`、`env.deploy`、模型权重、日志、数据库或用户上传文件。
- [x] 仓库中不存在大于 100 MB 的非必要文件。
- [x] 示例配置可公开阅读，但无法直接作为生产密钥使用。
- [x] 所有可能外泄的真实密钥均已轮换；仅限本机且从未提交或分享的数据库密码和 DeepSeek API Key 已确认无需轮换。

### 最终验收确认

- [x] 已确认数据库密码始终仅保存在本机被忽略的 `env.deploy` 中，从未提交或对外分享，无需轮换。
- [x] 已确认 DeepSeek API Key 始终仅保存在本机环境变量中，从未提交或对外分享，无需轮换。
- [x] 使用 `start-smartaudit.bat` 完成启动回归，前端、Java 后端和 Python AI 服务均正常响应，严格鉴权仍然生效。

---

## 阶段 2：许可证与开源合规

**状态：已完成**

### 目标

明确项目代码、测试样本和第三方资源的授权边界，使公开使用和二次开发具备清晰的法律依据。

### 任务

- [x] 确定项目许可证，采用 Apache License 2.0。
- [x] 在根目录添加 `LICENSE`。
- [x] 添加 `NOTICE` 和第三方许可证清单。
- [x] 保留 PDF.js CMap、WASM、Foxit 字体和 Liberation 字体的许可证文件。
- [x] 核查前端、Java、Python 直接依赖的许可证兼容性。
- [x] 核查 BGE 模型、DeepSeek API 及测试 PDF 的许可和再分发限制。
- [x] 在 README 中增加“许可证”和“第三方组件”章节。
- [x] 增加“本项目输出不构成法律意见”的免责声明。
- [x] 说明合同文件会发送到所配置的大模型服务商，并提示用户遵守隐私及数据合规要求。

### 验收标准

- [x] 根目录存在明确有效的项目许可证。
- [x] 所有随仓库分发的第三方二进制资源均保留许可证。
- [x] 模型权重不违反原模型许可证或再分发条款。
- [x] README 中可以明确回答“代码能否商用”“测试数据能否使用”“合同数据会发送到哪里”。

---

## 阶段 3：安全机制完善

**状态：已完成**

### 目标

修复影响真实部署的鉴权和数据安全问题，建立可公开审查的安全边界。

### 任务

- [x] 修复 SSE 鉴权，避免原生 `EventSource` 无法携带 Authorization Header。
- [x] 评估采用支持 Header 的 SSE 客户端或安全的 HttpOnly Cookie 方案；采用带 Bearer Header 的流式 `fetch`，不将令牌放入 URL 或可由脚本读取的 Cookie。
- [x] 为 PDF 下载、任务详情、任务删除和审计触发接口补齐权限测试。
- [x] 禁止生产环境接受 `demo-token`。
- [x] 确保生产环境在默认 Secret、空 Secret 或弱 Secret 下拒绝启动。
- [x] 检查上传 PDF 的文件类型、文件头、大小、路径穿越和文件名处理。
- [x] 为大模型请求、内部回调和回调签名增加超时、重试上限和重放防护。
- [x] 确保日志不记录 API Key、Authorization Header、完整合同正文或敏感回调载荷。
- [x] 增加任务和 PDF 的保留期限、删除行为及清理策略说明。
- [x] 添加 `SECURITY.md`，说明漏洞报告渠道和支持版本。

### 验收标准

- [x] 严格鉴权开启时，登录、PDF 预览、SSE、审计和删除流程全部正常。
- [x] 未授权请求均返回正确的 401 或 403。
- [x] 常见恶意上传和路径穿越测试无法访问托管目录之外的文件。
- [x] 日志抽查不包含密钥和完整合同正文。
- [x] 安全相关自动化测试全部通过。

---

## 阶段 4：可复现安装与跨平台启动

**状态：已完成**

### 目标

让陌生开发者无需依赖当前开发机环境，也能按文档稳定完成安装和启动。

### 任务

- [x] 明确支持的 Java、Maven、Node.js、npm、Python 和 MySQL 版本。
- [x] 为 Java 后端添加 Maven Wrapper。
- [x] 锁定 Python 依赖版本，生成可复现的锁文件。
- [x] 保留并验证前端 `package-lock.json`。
- [x] 增加 `docker-compose.yml`，统一启动 MySQL、Java 后端、Python AI 服务和前端。
- [x] 为三个服务分别添加 Dockerfile。
- [x] 增加 Linux/macOS 启动脚本。
- [x] 保留并验证 Windows `start-smartaudit.bat`。
- [x] 将本地 BGE 模型改为可选下载，不直接提交权重。
- [x] 提供模型下载脚本、来源、版本和 SHA256 校验。
- [x] 将 DeepSeek 模型名、API 地址和 Provider 完全配置化。
- [x] 引入 Flyway 管理数据库结构和后续迁移。
- [x] 提供最小可运行配置和生产配置示例。

### 验收标准

- [x] 一台干净环境可以仅根据 README 在 30 分钟内启动项目。
- [x] Windows 脚本启动流程通过。
- [x] Docker Compose 配置通过静态校验。
- [x] Linux/macOS 启动脚本通过 shell 基础校验。
- [x] 依赖锁文件和前端 lockfile 已纳入安装流程。
- [x] 数据库可从空库自动迁移到当前版本。

---

## 阶段 5：自动化测试与代码质量

**状态：已完成**

### 目标

建立覆盖核心业务路径的自动化测试，让外部贡献者能够安全修改代码。

### 任务

- [x] 为 Python 服务配置正式的 `pytest` 测试入口和覆盖率统计。
- [x] 增加合同解析、分块、风险抽取、失败降级和回调签名测试。
- [x] 使用可注入 LLM 客户端覆盖 DeepSeek 成功、限流、超时、400 和 500 响应。
- [x] 扩充 Java 控制器、服务、文件存储和数据库集成测试。
- [x] 增加前端单元测试框架与组件测试。
- [x] 增加 Playwright 端到端测试：
  - 登录
  - PDF 上传
  - 审计触发
  - SSE 状态更新
  - PDF 连续预览
  - 风险点击定位和高亮
  - 任务删除
- [x] 增加代码格式化和静态检查工具。
- [x] 清理未使用函数、历史兼容代码和测试残留文件。
- [x] 设置合理的最低覆盖率门槛，并逐步提高。

### 验收标准

- [x] Java、Python、前端测试可用单一命令分别执行。
- [x] 核心端到端流程在无真实大模型费用的情况下可重复运行。
- [x] 本地测试、静态检查和构建全部通过（CI 自动化属于阶段 6）。
- [x] 核心鉴权、文件处理和回调代码具备明确测试覆盖。

---

## 阶段 6：CI、供应链与发布流程

**状态：进行中**

### 目标

让每次提交和发布都经过一致的自动检查，并降低依赖与供应链风险。

### 任务

- [x] 添加 GitHub Actions 工作流，执行 Java 测试、Python 测试和前端构建。
- [x] 添加 Gitleaks 密钥扫描。
- [x] 添加 CodeQL 或同类静态安全扫描。
- [x] 添加依赖漏洞扫描和 Dependabot。
- [x] 生成软件物料清单（SBOM）。
- [ ] 配置分支保护和 Pull Request 必须检查项。
- [x] 建立语义化版本规范。
- [x] 添加 `CHANGELOG.md`。
- [x] 定义 Release 构建流程，禁止将本地密钥、日志、模型和用户数据打包。
- [x] 对 Docker 镜像和发布归档执行漏洞扫描。

### 验收标准

- [ ] Pull Request 必须通过构建、测试、密钥和安全扫描才能合并。
- [ ] Release 可以由固定工作流从干净环境生成。
- [ ] 发布产物内容经过自动清单检查。
- [ ] 依赖漏洞有明确的处理等级和升级流程。

> 仓库内工作流、扫描、SBOM、版本和发布流程已实现并通过本地静态校验。当前没有 Git remote，分支保护、必需检查、GHCR 可见性和真实 Release 仍需在 GitHub 远端创建后验收，因此阶段 6 保持“进行中”。

### 阶段 6 当前收口备注（2026-07-27）

本地依赖和容器验证已完成：LangChain 1.x、Transformers 5.5.0、FastAPI 0.140.0 已落地；PDF loader 已迁移到 `pypdf.PdfReader`；最终 AI 镜像内 `langchain==1.3.14`、`transformers==5.5.0`、`chromadb==0.6.3`，`pip check` 通过。Spring Boot 已升级到 3.5.16，Java 19/19、Python 23/23（34.21%）、前端单测 3/3（66.38%）、lint 和 build 均通过；Playwright E2E 最近一次完整验证为 5/5；`pip-audit --strict` 与生产 `npm audit` 均报告无已知漏洞。

Trivy 数据库下载和本地扫描已完成。使用 `aquasec/trivy:0.63.0` 对 backend、AI、frontend 三个正式发布镜像执行 `HIGH,CRITICAL` 且 `ignore-unfixed` 扫描，结果均为 0；测试专用 mock LLM 镜像不属于发布产物。源码和三个镜像的 CycloneDX SBOM 已成功生成并解析。按 Git 纳入边界构造的候选发布目录包含 371 个文件、约 4.4 MB，发布内容检查、Gitleaks 和 100 MB 大文件检查均通过。当前仅剩 GitHub 远端分支保护、必需检查、GHCR 可见性和真实 Release 验收，因此阶段 6 保持“进行中”。

---

## 阶段 7：文档、社区与长期维护

**状态：未完成**

### 目标

降低首次使用和参与贡献的门槛，形成可持续维护的开源项目结构。

### 任务

- [ ] 重构 README，增加项目定位、功能范围、架构图和界面截图。
- [ ] 提供 5 分钟快速开始指南。
- [ ] 提供完整环境变量表，标注必填项、默认值和安全建议。
- [ ] 增加常见问题和故障排查章节。
- [ ] 增加模型 Provider 切换文档。
- [ ] 增加数据存储、隐私和删除策略文档。
- [ ] 增加 `README_EN.md`。
- [ ] 添加 `CONTRIBUTING.md`。
- [ ] 添加 `CODE_OF_CONDUCT.md`。
- [ ] 添加 Issue 和 Pull Request 模板。
- [ ] 定义维护者、支持范围和版本支持周期。
- [ ] 增加结构化日志、请求 ID、任务 ID、模型耗时、Token 用量和失败阶段指标。
- [ ] 优化前端 PDF.js 大型构建块和按需资源加载。

### 验收标准

- [ ] 新用户无需阅读源码即可完成部署和首次审计。
- [ ] 外部贡献者可以根据贡献指南完成开发、测试和提交。
- [ ] Issue、漏洞和发布有明确处理流程。
- [ ] 文档与当前配置、命令和界面保持一致。

---

## 阶段进度总览

| 阶段 | 名称 | 状态 | 完成日期 |
| --- | --- | --- | --- |
| 1 | 敏感信息与仓库清理 | 已完成 | 2026-07-26 |
| 2 | 许可证与开源合规 | 已完成 | 2026-07-26 |
| 3 | 安全机制完善 | 已完成 | 2026-07-26 |
| 4 | 可复现安装与跨平台启动 | 已完成 | 2026-07-27 |
| 5 | 自动化测试与代码质量 | 已完成 | 2026-07-26 |
| 6 | CI、供应链与发布流程 | 进行中 | - |
| 7 | 文档、社区与长期维护 | 未完成 | - |

## 阶段验收记录

每完成一个阶段，在此追加验收记录，并同步更新阶段正文及进度总览。

### 记录模板

```text
阶段：
验收日期：
验收人：
完成内容：
执行的验证命令：
验证结果：
遗留问题：
关联提交或版本：
```

### 阶段 1 验收记录

```text
阶段：1 - 敏感信息与仓库清理
验收日期：2026-07-26
验收人：Codex 自动检查，凭据使用范围由项目所有者确认
完成内容：完善忽略规则和二进制属性；清理生成物；安全化示例配置；同步轮换应用内部密钥；配置并执行 Gitleaks；检查首次暂存清单；记录公开测试 PDF 范围。
执行的验证命令：gitleaks git --staged；git check-ignore；git diff --cached --name-only；mvn test；Python 回调服务测试；npm run build；start-smartaudit.bat 启动检查。
验证结果：Gitleaks 0 条泄漏；禁止路径 0 个；大于 100 MB 的待提交文件 0 个；Java 5/5、Python 2/2 测试通过；前端构建通过；5173、8000、8080 服务正常。
遗留问题：无阶段 1 阻塞项。项目许可证、第三方资源和测试 PDF 的最终许可条款在阶段 2 处理。
关联提交或版本：尚未创建首次提交。
```

### 阶段 2 验收记录

```text
阶段：2 - 许可证与开源合规
验收日期：2026-07-26
验收人：Codex 自动核查
完成内容：采用 Apache-2.0；添加 LICENSE、NOTICE 和第三方许可证清单；核查前端、Java、Python 直接依赖；核查并保留 PDF.js 资源许可；确认 BGE 权重不随仓库分发；记录 DeepSeek 服务与隐私边界；授权并说明虚构测试 PDF；补充 README 商用、数据流向和法律免责声明。
执行的验证命令：npm/PyPI/Maven 依赖元数据核查；Hugging Face 模型卡 API 核查；PDF 元数据与文本检查；PDF.js 许可证文件完整性检查；git check-ignore；mvn test；npm run build；gitleaks git --staged。
验证结果：项目许可证明确；9 份随仓库分发的 PDF.js 资源许可证齐全；BGE-M3 为 MIT、BGE reranker v2 m3 为 Apache-2.0 且权重均被忽略；Java 5/5 测试通过；前端构建通过；README 可明确回答商用、测试数据许可及合同数据发送位置。
遗留问题：Python 依赖版本锁定与自动化许可证扫描分别在阶段 4 和阶段 6 处理；本记录是工程合规核查，不替代特定司法辖区的专业法律意见。
关联提交或版本：尚未创建首次提交。
```

### 阶段 3 验收记录

```text
阶段：3 - 安全机制完善
验收日期：2026-07-26
验收人：Codex 自动检查
完成内容：使用带 Authorization Header 的流式 fetch 修复 SSE 鉴权；补齐接口角色和任务归属权限；生产环境强制严格鉴权与强 Secret；增加 PDF 扩展名、MIME、文件头、大小、文件名、随机落盘名、托管路径和 SHA-256 校验；修复回调 Nonce 抢占问题；限制 LLM 与回调超时和重试；最小化回调日志载荷；增加 90 天默认保留清理任务、SECURITY.md 和数据删除文档。
执行的验证命令：mvn test；Python unittest 与 compileall；npm run build；start-smartaudit.bat 启动回归；敏感日志静态检索；Git 禁止路径抽查。
验证结果：Java 16/16、Python 2/2 测试通过；Python 编译检查通过；前端生产构建通过；Java、Python、前端三服务均成功启动并正常关闭；未发现记录 Authorization、API Key、完整合同正文或敏感回调正文的日志语句；构建产物和运行数据未进入 Git 清单。
遗留问题：当前环境未提供 gitleaks 可执行文件，本阶段未重复执行密钥扫描；阶段 1 已完成的 Gitleaks 结果仍有效，本次新增内容已完成人工静态抽查。前端 PDF.js 大型构建块优化按阶段 7 处理。
关联提交或版本：尚未创建首次提交。
```

### 阶段 4 验收记录

```text
阶段：4 - 可复现安装与跨平台启动
验收日期：2026-07-27
验收人：Codex 自动检查
完成内容：锁定三端依赖并保留 Maven Wrapper；提供 Docker Compose、三服务 Dockerfile 和跨平台启动脚本；将 BGE 权重改为固定 revision、SHA256 校验的可选下载；配置化 LLM Provider、地址和模型；使用 Flyway 管理空库迁移；增加无固定密码的一次性管理员引导配置；修正文档和 Windows Wrapper 启动流程。
执行的验证命令：docker compose config --quiet；backend-java\\mvnw.cmd verify；ai-python\\venv\\Scripts\\python.exe -m pytest；npm run test:unit:coverage；npm run lint；npm run build；隔离 MySQL/backend 容器空库启动与登录验证。
验证结果：Compose 静态校验通过；Java 19/19、Python 23/23、前端 3/3 测试通过；lint 和 build 通过；空库自动执行 Flyway V1，随后仅在用户表为空时创建 BCrypt 管理员并成功登录取得 ADMIN JWT；模型锁文件包含固定来源、revision 和 SHA256。
遗留问题：当前 Windows 环境的 WSL Bash 不可用，Linux shell 语法沿用此前验收和 GitHub Actions 验证；真实跨平台 CI 运行属于阶段 6 远端验收。管理员引导密码首次登录后必须从部署配置移除。
关联提交或版本：尚未创建首次提交。
```

### 阶段 5 验收记录

```text
阶段：5 - 自动化测试与代码质量
验收日期：2026-07-26
验收人：Codex 自动检查
完成内容：补充 Python 核心解析、分块、去重、预算、查询构造、安全上下文、一致性检查和 trace 脱敏测试；修复并测试双阶段 E2E mock LLM 协议；补充前端 API 单元测试和 Vitest V8 覆盖率；增加 Java JaCoCo 门槛；补充 Playwright 审查、SSE、风险结果、PDF 页码、删除和登录流程；增加 Windows/Linux 阶段五统一测试入口；完成静态检查和测试残留审查。
执行的验证命令：backend-java\\mvnw.cmd verify；ai-python\\venv\\Scripts\\python.exe -m pytest；frontend\\npm run test:unit:coverage；frontend\\npm run lint；frontend\\npm run build；frontend\\npm run test:e2e。
验证结果：Java 测试全部通过并满足 JaCoCo 15% 行覆盖率门槛；Python 23/23 通过、覆盖率 34.21%；前端单元测试 3/3 通过、核心可测模块覆盖率 66.38%；前端 lint 和构建通过；完整 Playwright E2E 5/5 通过；审查流程在无真实大模型费用下重复产生 1 条风险并落库。
遗留问题：CI、密钥扫描、CodeQL、依赖扫描和发布流程属于阶段 6，未在本阶段实现；忽略的本地产物不进入 Git 清单。
关联提交或版本：尚未创建首次提交。
```
