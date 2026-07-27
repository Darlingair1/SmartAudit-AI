# Third-Party Licenses

This document records the direct dependencies, bundled browser resources, external services, and optional model assets used by SmartAudit-AI. It is informational and does not replace the original license texts.

## Frontend dependencies

| Component | Version basis | License |
| --- | --- | --- |
| Vue | `package-lock.json` | MIT |
| Vue Router | `package-lock.json` | MIT |
| Element Plus | `package-lock.json` | MIT |
| Element Plus Icons Vue | `package-lock.json` | MIT |
| Axios | `package-lock.json` | MIT |
| vue-pdf-embed | `package-lock.json` | MIT |
| PDF.js (`pdfjs-dist`) | `package-lock.json` | Apache-2.0 |
| Vite and Vue plugin | `package-lock.json` | MIT |
| Sass | `package-lock.json` | MIT |

The lock file is authoritative for installed versions. Package license texts remain available in each npm package distribution.

## Bundled PDF.js resources

The following browser resources are redistributed with the frontend. Their original license files are retained beside the files:

| Resource | License | Retained notice |
| --- | --- | --- |
| Adobe CMaps | BSD-3-Clause-style Adobe license | `frontend/public/pdfjs/cmaps/LICENSE` |
| Foxit/PDFium standard fonts | BSD-3-Clause | `frontend/public/pdfjs/standard_fonts/LICENSE_FOXIT` |
| Liberation fonts | SIL Open Font License 1.1 | `frontend/public/pdfjs/standard_fonts/LICENSE_LIBERATION` |
| JBIG2 WASM and fallback | BSD-3-Clause and Apache-2.0 components | `frontend/public/pdfjs/wasm/LICENSE_JBIG2`, `LICENSE_PDFJS_JBIG2` |
| OpenJPEG WASM and fallback | BSD-2-Clause and BSD-3-Clause components | `frontend/public/pdfjs/wasm/LICENSE_OPENJPEG`, `LICENSE_PDFJS_OPENJPEG` |
| QCMS WASM | MIT and BSD-3-Clause components | `frontend/public/pdfjs/wasm/LICENSE_QCMS`, `LICENSE_PDFJS_QCMS` |

Do not remove these license files when building or redistributing the frontend.

## Java direct dependencies

| Component | Version basis | License |
| --- | --- | --- |
| Spring Boot starters | `pom.xml` / resolved dependency tree | Apache-2.0 |
| MyBatis-Plus | `pom.xml` | Apache-2.0 |
| MySQL Connector/J | Spring Boot dependency management | GPL-2.0 with Universal FOSS Exception 1.0 |
| Lombok | Spring Boot dependency management | MIT |
| springdoc-openapi | `pom.xml` | Apache-2.0 |
| Hutool | `pom.xml` | MulanPSL-2.0 |

MySQL Connector/J is used as an external database driver. Its Universal FOSS Exception permits distribution with qualifying free/open-source applications; redistributors should preserve its original notices and reassess obligations for their packaging model.

## Python direct dependencies

| Component | License |
| --- | --- |
| FastAPI | MIT |
| Uvicorn | BSD-3-Clause |
| Pydantic | MIT |
| LangChain core, OpenAI, community, Chroma, Hugging Face and text splitters integrations | MIT |
| ChromaDB | Apache-2.0 |
| Sentence Transformers | Apache-2.0 |
| pypdf | BSD-3-Clause |
| Requests | Apache-2.0 |
| python-dotenv | BSD-3-Clause |

`ai-python/requirements.txt` is currently unpinned. The license review above covers the declared direct projects as checked on 2026-07-26; phase 4 will pin versions and phase 6 will automate dependency and license checks.

## Optional local models

Model weights are excluded from this Git repository and are not redistributed:

| Model | Upstream | License shown by upstream model card |
| --- | --- | --- |
| BAAI/bge-m3 | https://huggingface.co/BAAI/bge-m3 | MIT |
| BAAI/bge-reranker-v2-m3 | https://huggingface.co/BAAI/bge-reranker-v2-m3 | Apache-2.0 |

Users downloading model weights are responsible for reviewing the current upstream model card and license. Local files under `models/` remain outside the repository and release artifacts.

## External model service

DeepSeek is an external API service and its model, platform, and API implementation are not redistributed by this repository. Use is governed by DeepSeek's current API documentation, terms of use, privacy policy, pricing, and applicable law:

- https://api-docs.deepseek.com/
- https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html
- https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html

Users must ensure they have the rights and permissions needed to submit contract content. Service terms can change independently of this project.

## Test data

`虚构风险合同测试样本.pdf` is a synthetic fixture supplied with this project and is licensed under Apache-2.0 together with the project, solely as fictional test material. It must not be represented as a real agreement or legal template. Other PDFs, runtime uploads, databases, and files under ignored storage directories are not part of the open-source distribution.

## Compatibility conclusion

The reviewed direct dependencies and bundled resources may be used with an Apache-2.0 licensed application provided their original notices and license-specific conditions remain intact. No model weight is committed or packaged. This inventory is not legal advice; redistributors remain responsible for their own compliance review.
