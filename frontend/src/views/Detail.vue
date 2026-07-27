<template>
  <section data-testid="task-detail" class="detail-page" v-loading="loading">
    <el-card class="headline-card" shadow="never">
      <div class="headline-content">
        <div class="task-meta">
          <h2>{{ detail.taskName || "审查任务详情" }}</h2>
          <div class="meta-row">
            <el-tag data-testid="task-status" :type="statusTagType(detail.status)" size="large" effect="dark">
              {{ statusText(detail.status) }}
            </el-tag>
            <el-tag data-testid="sse-status" :type="sseTagType" effect="plain">
              {{ sseStatusText }}
            </el-tag>
            <span>文件：{{ detail.fileName || "-" }}</span>
            <span>任务编号：{{ detail.taskNo || "-" }}</span>
          </div>
        </div>

        <div class="action-group">
          <el-button size="large" @click="goTaskList">返回任务列表</el-button>
          <el-button size="large" @click="refresh">刷新</el-button>
          <el-button
            type="danger"
            size="large"
            data-testid="trigger-audit"
            class="trigger-btn"
            :loading="triggerLoading"
            :disabled="triggerDisabled"
            @click="startAudit"
          >
            开始 AI 审查
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="summary-strip" shadow="never">
      <div class="summary-list">
        <div class="summary-item high">
          <span class="label">高风险</span>
          <strong>{{ detail.highRiskCount ?? 0 }}</strong>
        </div>
        <div class="summary-item medium">
          <span class="label">中风险</span>
          <strong>{{ detail.mediumRiskCount ?? 0 }}</strong>
        </div>
        <div class="summary-item low">
          <span class="label">低风险</span>
          <strong>{{ detail.lowRiskCount ?? 0 }}</strong>
        </div>
        <div class="summary-item total">
          <span class="label">风险总数</span>
          <strong>{{ riskItems.length }}</strong>
        </div>
      </div>
    </el-card>

    <div class="workspace" :class="{ 'risk-focus': riskFocusMode }">
      <el-card shadow="never" class="pdf-pane">
        <template #header>
          <div class="pane-header">
            <span>PDF 预览</span>
            <div class="pdf-toolbar">
              <el-segmented
                v-model="pdfViewMode"
                class="pdf-view-mode"
                :options="pdfViewModeOptions"
                size="small"
                @change="changePdfViewMode"
              />
              <span data-testid="pdf-page-status" class="pdf-page-status">第 {{ pdfPageNumber }} / {{ pdfPageCount || "-" }} 页</span>
            </div>
          </div>
        </template>

        <div data-testid="pdf-preview"
          ref="pdfScrollContainer"
          class="pdf-viewer-wrap"
          @scroll.passive="handlePdfScroll"
        >
          <div v-if="pdfSource" class="viewer-shell">
            <vue-pdf-embed
              ref="pdfApp"
              id="pdf-document"
              class="pdf-viewer"
              :source="pdfSource"
              :find-controller="pdfFindController"
              :width="pdfRenderWidth || undefined"
              text-layer
              annotation-layer
              @loaded="onPdfLoaded"
              @rendered="onPdfRendered"
              @rendering-failed="onPdfRenderingFailed"
            />
          </div>
          <el-empty v-else description="暂无可预览 PDF" />
        </div>
      </el-card>

      <el-card shadow="never" class="risk-pane">
        <template #header>
          <div class="pane-header">
            <div class="risk-header-left">
              <span>风险洞察</span>
              <el-tag type="danger" effect="dark">核心视图</el-tag>
            </div>
            <div class="risk-header-right">
              <el-tag type="info">共 {{ riskItems.length }} 条</el-tag>
              <el-button text type="primary" @click="toggleRiskFocusMode">
                {{ riskFocusMode ? "切换平衡视图" : "切换风险聚焦" }}
              </el-button>
            </div>
          </div>
        </template>

        <el-scrollbar class="risk-scroll">
          <el-empty v-if="!riskItems.length" description="暂无风险明细" />
          <el-collapse
            v-else
            v-model="activePanel"
            accordion
            class="risk-collapse"
            @change="handleRiskPanelChange"
          >
            <el-collapse-item
              data-testid="risk-item"
              v-for="item in riskItems"
              :key="riskKey(item)"
              :name="riskKey(item)"
              class="risk-collapse-item"
            >
              <template #title>
                <div class="collapse-title">
                  <div class="collapse-main">
                    <div class="collapse-name">{{ item.clauseTitle || `条款 #${item.seqNo ?? '-'}` }}</div>
                    <div class="collapse-type">{{ item.riskType || "未分类风险" }}</div>
                  </div>
                  <el-tag :type="riskLevelTagType(item.riskLevel)" effect="dark">
                    {{ riskLevelText(item.riskLevel) }}
                  </el-tag>
                </div>
              </template>

              <p class="line"><strong>定位：</strong> {{ item.clausePosition || "-" }}</p>
              <p class="line"><strong>页码：</strong> {{ item.pageNo || 1 }}</p>

              <div data-testid="risk-highlight" class="quote-block">
                <p class="label">合同原文片段</p>
                <p>{{ item.contractExcerpt || "-" }}</p>
              </div>

              <div class="reason-block">
                <p class="label">分析原因</p>
                <p>{{ item.riskDesc || "未提供分析原因" }}</p>
              </div>

              <div class="suggestion-block">
                <p class="label">AI 修改建议</p>
                <p>{{ item.suggestion || "-" }}</p>
              </div>

              <p class="line"><strong>法律依据：</strong> {{ item.legalBasis || "-" }}</p>
            </el-collapse-item>
          </el-collapse>
        </el-scrollbar>
      </el-card>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import VuePdfEmbed, { usePdfSearch } from "vue-pdf-embed";
import "vue-pdf-embed/dist/styles/annotationLayer.css";
import "vue-pdf-embed/dist/styles/textLayer.css";

import { getAuditTaskDetail, getAuditTaskFile, triggerAuditTask } from "../api/audit";
import { getToken } from "../utils/auth";

const route = useRoute();
const router = useRouter();
const taskId = computed(() => route.params.id);

const loading = ref(false);
const triggerLoading = ref(false);
const sseState = ref("DISCONNECTED");
const sseSource = ref(null);
const sseConnected = computed(() => sseState.value === "CONNECTED");
const sseTagType = computed(() => ["CONNECTED", "COMPLETED"].includes(sseState.value) ? "success" : "info");
const sseStatusText = computed(() => {
  if (sseState.value === "CONNECTED") return "实时通道已连接";
  if (sseState.value === "COMPLETED") return "实时通道已完成";
  if (sseState.value === "FINISHED") return "实时通道已结束";
  return "实时通道未连接";
});

const detail = reactive({
  id: null,
  taskNo: "",
  taskName: "",
  status: "",
  fileName: "",
  filePath: "",
  highRiskCount: 0,
  mediumRiskCount: 0,
  lowRiskCount: 0,
  riskItems: []
});

const riskItems = computed(() => detail.riskItems || []);
const triggerDisabled = computed(() => ["PROCESSING", "COMPLETED"].includes((detail.status || "").toUpperCase()));

const pdfApp = ref(null);
const pdfScrollContainer = ref(null);
const pdfPageNumber = ref(1);
const pdfPageCount = ref(0);
const pdfSource = shallowRef(null);
const pdfSourceTaskId = ref(null);
const pdfResourceBaseUrl = `${window.location.origin}/pdfjs`;
const pdfDocument = shallowRef(null);
const pdfRendered = ref(false);
const PDF_BODY_VIEW_SCALE = 1.22;
const pdfViewMode = ref("body");
const pdfViewModeOptions = [
  { label: "正文", value: "body" },
  { label: "整页", value: "page" }
];
const pdfFitWidth = ref(0);
const pdfRenderWidth = ref(0);
let locateRequestId = 0;
let pdfScrollFrame = 0;
let pdfResizeObserver = null;
let pendingZoomAnchor = null;
const {
  clear: clearPdfSearch,
  currentMatchPage,
  find: findInPdf,
  findController: pdfFindController,
  matchCount
} = usePdfSearch(pdfDocument);
const activePanel = ref("");
const riskFocusMode = ref(true);

const releasePdfSource = () => {
  pdfSource.value = null;
  pdfSourceTaskId.value = null;
  pdfApp.value = null;
  pdfDocument.value = null;
  pdfRendered.value = false;
  pdfPageCount.value = 0;
  pdfPageNumber.value = 1;
};

const loadPdfSource = async (id) => {
  if (!id || (pdfSourceTaskId.value === id && pdfSource.value)) {
    return;
  }

  const pdfBuffer = await getAuditTaskFile(id);
  if (!(pdfBuffer instanceof ArrayBuffer) || pdfBuffer.byteLength === 0) {
    throw new Error("PDF 文件内容为空");
  }

  const signature = new TextDecoder("ascii").decode(new Uint8Array(pdfBuffer, 0, Math.min(5, pdfBuffer.byteLength)));
  if (signature !== "%PDF-") {
    throw new Error("文件接口未返回有效的 PDF 内容");
  }

  releasePdfSource();
  pdfSource.value = {
    data: new Uint8Array(pdfBuffer),
    cMapUrl: `${pdfResourceBaseUrl}/cmaps/`,
    cMapPacked: true,
    standardFontDataUrl: `${pdfResourceBaseUrl}/standard_fonts/`,
    wasmUrl: `${pdfResourceBaseUrl}/wasm/`,
    useSystemFonts: true
  };
  pdfSourceTaskId.value = id;
};

const onPdfLoaded = (document) => {
  pdfDocument.value = document;
  pdfPageCount.value = document?.numPages ?? 0;
  if (pdfPageNumber.value > pdfPageCount.value) {
    pdfPageNumber.value = 1;
  }
};

const onPdfRendered = () => {
  pdfRendered.value = true;
  if (!pendingZoomAnchor) {
    return;
  }
  const anchor = pendingZoomAnchor;
  pendingZoomAnchor = null;
  nextTick(() => {
    window.requestAnimationFrame(() => {
      const container = pdfScrollContainer.value;
      const page = document.getElementById(`pdf-document-${anchor.page}`);
      if (!container || !page) {
        return;
      }
      const pageTop = page.getBoundingClientRect().top
        - container.getBoundingClientRect().top
        + container.scrollTop;
      container.scrollTop = Math.max(0, pageTop + page.offsetHeight * anchor.offsetRatio - 12);
    });
  });
};

const onPdfRenderingFailed = (error) => {
  console.error("PDF rendering failed", error);
  ElMessage.error(`PDF 渲染失败：${error?.message || "未知错误"}`);
};

const capturePdfAnchor = () => {
  const container = pdfScrollContainer.value;
  const page = document.getElementById(`pdf-document-${pdfPageNumber.value}`);
  if (!container || !page || !page.offsetHeight) {
    return { page: pdfPageNumber.value, offsetRatio: 0 };
  }
  const pageTop = page.getBoundingClientRect().top
    - container.getBoundingClientRect().top
    + container.scrollTop;
  return {
    page: pdfPageNumber.value,
    offsetRatio: Math.max(0, Math.min(1, (container.scrollTop - pageTop + 12) / page.offsetHeight))
  };
};

const changePdfViewMode = (mode) => {
  if (!pdfFitWidth.value) {
    return;
  }
  pendingZoomAnchor = capturePdfAnchor();
  pdfRendered.value = false;
  pdfViewMode.value = mode;
  pdfRenderWidth.value = Math.round(
    pdfFitWidth.value * (mode === "body" ? PDF_BODY_VIEW_SCALE : 1)
  );
};

const updatePdfFitWidth = () => {
  const container = pdfScrollContainer.value;
  if (!container) {
    return;
  }
  const nextFitWidth = Math.max(280, container.clientWidth - 26);
  if (nextFitWidth === pdfFitWidth.value) {
    return;
  }
  pdfFitWidth.value = nextFitWidth;
  pdfRenderWidth.value = Math.round(
    nextFitWidth * (pdfViewMode.value === "body" ? PDF_BODY_VIEW_SCALE : 1)
  );
};

const statusTagType = (status) => {
  const s = (status || "").toUpperCase();
  if (s === "COMPLETED") return "success";
  if (s === "FAILED") return "danger";
  if (s === "PROCESSING") return "warning";
  return "info";
};

const statusText = (status) => {
  const s = (status || "").toUpperCase();
  if (s === "COMPLETED") return "已完成";
  if (s === "FAILED") return "已失败";
  if (s === "PROCESSING") return "处理中";
  if (s === "PENDING") return "待处理";
  return "未知";
};

const riskLevelTagType = (level) => {
  const s = (level || "").toUpperCase();
  if (s === "HIGH") return "danger";
  if (s === "MEDIUM") return "warning";
  return "primary";
};

const riskLevelText = (level) => {
  const s = (level || "").toUpperCase();
  if (s === "HIGH") return "高风险";
  if (s === "MEDIUM") return "中风险";
  return "低风险";
};

const riskKey = (item) => `${item.id ?? "tmp"}-${item.seqNo ?? ""}-${item.pageNo ?? ""}`;

const applyDetail = (data) => {
  detail.id = data?.id ?? null;
  detail.taskNo = data?.taskNo ?? "";
  detail.taskName = data?.taskName ?? "";
  detail.status = data?.status ?? "";
  detail.fileName = data?.fileName ?? "";
  detail.filePath = data?.filePath ?? "";
  detail.highRiskCount = data?.highRiskCount ?? 0;
  detail.mediumRiskCount = data?.mediumRiskCount ?? 0;
  detail.lowRiskCount = data?.lowRiskCount ?? 0;
  detail.riskItems = data?.riskItems ?? [];
  if (!detail.riskItems.length) {
    activePanel.value = "";
    return;
  }
  const currentExists = detail.riskItems.some((item) => riskKey(item) === activePanel.value);
  if (!currentExists) {
    activePanel.value = riskKey(detail.riskItems[0]);
  }
};

const fetchDetail = async (silent = false) => {
  if (!silent) {
    loading.value = true;
  }
  try {
    const data = await getAuditTaskDetail(taskId.value);
    applyDetail(data);
    await loadPdfSource(detail.id);
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }
};

const refreshUntilTerminal = async () => {
  // The callback SSE can arrive just before the backend transaction commits.
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await fetchDetail(true);
    const status = (detail.status || "").toUpperCase();
    if (status === "COMPLETED" || status === "FAILED") return status;
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  return (detail.status || "").toUpperCase();
};

const closeSse = (nextState = "DISCONNECTED") => {
  if (sseSource.value) {
    sseSource.value.abort();
    sseSource.value = null;
  }
  sseState.value = nextState;
};

const connectSse = async () => {
  closeSse();
  const controller = new AbortController();
  sseSource.value = controller;
  try {
    const response = await fetch(`/api/v1/audit/tasks/${taskId.value}/sse`, {
      headers: { Authorization: `Bearer ${getToken()}` },
      signal: controller.signal
    });
    if (!response.ok || !response.body) {
      throw new Error(`SSE connection failed: ${response.status}`);
    }
    sseState.value = "CONNECTED";
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (!controller.signal.aborted) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() || "";
      for (const event of events) {
        const status = event.split(/\r?\n/)
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim())
          .join("\n")
          .toUpperCase();
        if (status === "COMPLETED" || status === "FAILED") {
          closeSse(status === "COMPLETED" ? "COMPLETED" : "FINISHED");
          const finalStatus = await refreshUntilTerminal();
          finalStatus === "COMPLETED"
            ? ElMessage.success("AI 审查完成")
            : finalStatus === "FAILED"
              ? ElMessage.error("AI 审查失败")
              : ElMessage.warning("任务状态同步超时，请刷新页面");
          return;
        }
      }
    }
  } catch {
    if (!controller.signal.aborted) {
      ElMessage.warning("实时通道已断开，请手动刷新");
      closeSse();
    }
  }
};

const startAudit = async () => {
  triggerLoading.value = true;
  try {
    // Complete the SSE handshake before starting a fast mock/AI job.
    connectSse();
    for (let attempt = 0; attempt < 20 && !sseConnected.value; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    await triggerAuditTask(taskId.value);
    ElMessage.success("任务已提交到 AI 引擎");
    await fetchDetail(true);
  } catch (error) {
    closeSse();
    throw error;
  } finally {
    triggerLoading.value = false;
  }
};

const goTaskList = () => {
  router.push({ name: "home" });
};

const refresh = () => fetchDetail();

const toggleRiskFocusMode = () => {
  riskFocusMode.value = !riskFocusMode.value;
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const buildSearchCandidates = (item) => {
  const source = String(item?.contractExcerpt || "").trim();
  const clauseTitle = String(item?.clauseTitle || "").trim();
  if (!source) {
    return clauseTitle ? [clauseTitle] : [];
  }

  const normalized = source
    .replace(/\s+/g, " ")
    .replace(/\u3000/g, " ")
    .replace(/^\d+[.、]\s*/g, "")
    .trim();
  const compact = normalized.replace(/\s+/g, "");
  const segments = normalized
    .split(/\.{3,}|…+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);
  const sentenceChunks = compact
    .split(/[。；;，,、:：!?！？()（）【】[\]-]/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 6)
    .sort((a, b) => b.length - a.length);

  const candidates = new Set();
  const append = (q) => {
    if (q && q.length >= 4) {
      candidates.add(q);
    }
  };

  append(normalized);
  append(compact);
  append(segments[0]);
  append(segments[1]);
  append((segments[0] || normalized).slice(0, 40));
  append((compact || normalized).slice(0, 24));
  append((compact || normalized).slice(8, 36));
  append((compact || normalized).slice(20, 52));
  append(clauseTitle);
  append(sentenceChunks[0]);
  append(sentenceChunks[1]);
  append(sentenceChunks[2]);

  return Array.from(candidates).slice(0, 12);
};

const waitForPdfRender = async () => {
  for (let i = 0; i < 60 && !pdfRendered.value; i += 1) {
    await sleep(50);
  }
  return pdfRendered.value;
};

const scrollToPdfPage = (pageNumber, behavior = "smooth") => {
  const container = pdfScrollContainer.value;
  const page = document.getElementById(`pdf-document-${pageNumber}`);
  if (!container || !page) {
    return false;
  }

  const top = page.getBoundingClientRect().top
    - container.getBoundingClientRect().top
    + container.scrollTop
    - 12;
  container.scrollTo({ top: Math.max(0, top), behavior });
  pdfPageNumber.value = pageNumber;
  return true;
};

const handlePdfScroll = () => {
  if (pdfScrollFrame) {
    return;
  }
  pdfScrollFrame = window.requestAnimationFrame(() => {
    pdfScrollFrame = 0;
    const container = pdfScrollContainer.value;
    if (!container) {
      return;
    }
    const containerTop = container.getBoundingClientRect().top;
    let nearestPage = pdfPageNumber.value;
    let nearestDistance = Number.POSITIVE_INFINITY;
    container.querySelectorAll(".vue-pdf-embed__page").forEach((page, index) => {
      const distance = Math.abs(page.getBoundingClientRect().top - containerTop - 12);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestPage = index + 1;
      }
    });
    pdfPageNumber.value = nearestPage;
  });
};

const searchPdfCandidate = async (query, requestId) => {
  clearPdfSearch();
  await nextTick();
  findInPdf(query, {
    caseSensitive: false,
    entireWord: false,
    highlightAll: true,
    matchDiacritics: false
  });

  for (let i = 0; i < 40 && requestId === locateRequestId; i += 1) {
    if (matchCount.value > 0) {
      return currentMatchPage.value;
    }
    await sleep(50);
  }
  return 0;
};

const handleRiskPanelChange = async (name) => {
  const panelName = Array.isArray(name) ? name[0] : name;
  if (!panelName) {
    return;
  }
  const item = riskItems.value.find((risk) => riskKey(risk) === String(panelName));
  if (!item) {
    return;
  }
  await jumpAndHighlight(item);
};

const jumpAndHighlight = async (item) => {
  activePanel.value = riskKey(item);

  if (!pdfSource.value) {
    ElMessage.warning("PDF 资源不可用");
    return;
  }

  const requestId = ++locateRequestId;
  await waitForPdfRender();
  if (requestId !== locateRequestId) {
    return;
  }

  const positionPage = Number(String(item?.clausePosition || "").match(/page\s*(\d+)/i)?.[1]);
  const requestedPage = Number(item?.pageNo) > 0 ? Number(item.pageNo) : positionPage || 1;
  const targetPage = pdfPageCount.value
    ? Math.min(requestedPage, pdfPageCount.value)
    : requestedPage;
  scrollToPdfPage(targetPage);

  const candidates = buildSearchCandidates(item);
  for (const query of candidates) {
    const matchedPage = await searchPdfCandidate(query, requestId);
    if (requestId !== locateRequestId) {
      return;
    }
    if (matchedPage > 0) {
      await nextTick();
      scrollToPdfPage(matchedPage);
      return;
    }
  }

  clearPdfSearch();
  scrollToPdfPage(targetPage);
};

onMounted(async () => {
  await nextTick();
  updatePdfFitWidth();
  if (window.ResizeObserver && pdfScrollContainer.value) {
    pdfResizeObserver = new ResizeObserver(updatePdfFitWidth);
    pdfResizeObserver.observe(pdfScrollContainer.value);
  }
  await fetchDetail();
  if ((detail.status || "").toUpperCase() === "PROCESSING") {
    connectSse();
  }
});

onBeforeUnmount(() => {
  closeSse();
  pdfResizeObserver?.disconnect();
  if (pdfScrollFrame) {
    window.cancelAnimationFrame(pdfScrollFrame);
  }
  releasePdfSource();
});
</script>

<style scoped lang="scss">
.detail-page {
  display: grid;
  grid-template-rows: auto auto 1fr;
  gap: 16px;
  height: calc(100vh - 120px);
  min-height: 700px;
  overflow: hidden;
}

.headline-card {
  border-radius: 16px;
  border: 1px solid #e8d7c7;
  background: radial-gradient(circle at top left, #fff5e9, #fbfbfb 55%);
}

.headline-content {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.task-meta h2 {
  margin: 0 0 10px;
  font-size: 24px;
  color: #2b2b2b;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #646464;
}

.action-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.trigger-btn {
  min-width: 160px;
  font-weight: 700;
}

.summary-strip {
  border-radius: 16px;
  border: 1px solid #e8edf5;
}

.summary-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  border-radius: 12px;
  border: 1px solid #ebeef5;
  background: #fff;
  padding: 10px 14px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.summary-item .label {
  margin: 0;
  font-size: 14px;
  color: #5f6368;
  text-transform: none;
  letter-spacing: normal;
}

.summary-item strong {
  font-size: 28px;
  line-height: 1;
}

.summary-item.high strong {
  color: #d73a49;
}

.summary-item.medium strong {
  color: #d28800;
}

.summary-item.low strong {
  color: #2a78c6;
}

.summary-item.total strong {
  color: #1f2d3d;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: 16px;
  min-height: 0;
  overflow: hidden;
}

.workspace.risk-focus {
  grid-template-columns: minmax(0, 0.72fr) minmax(0, 1.28fr);
}

.pdf-pane,
.risk-pane {
  min-width: 0;
  min-height: 0;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
}

.pdf-pane :deep(.el-card__body),
.risk-pane :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.pane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 700;
}

.risk-header-left,
.risk-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pdf-viewer-wrap {
  flex: 1;
  min-height: 0;
  border-radius: 12px;
  border: 1px solid #ececec;
  background: #f8fafc;
  overflow-x: hidden;
  overflow-y: auto;
}

.workspace.risk-focus .pdf-pane {
  opacity: 0.93;
}

.risk-pane {
  border: 1px solid #f0d8b5;
  background: linear-gradient(180deg, #fffaf3 0%, #ffffff 120px);
}

.viewer-shell {
  min-height: 100%;
  padding: 12px;
}

.pdf-viewer {
  min-height: 100%;
}

.pdf-viewer :deep(canvas) {
  display: block;
  max-width: none;
  height: auto !important;
  margin: 0 auto;
}

.pdf-viewer :deep(.vue-pdf-embed__page) {
  width: fit-content;
  left: 50%;
  transform: translateX(-50%);
  margin: 0 auto 16px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.16);
}

.pdf-viewer :deep(.vue-pdf-embed__page:last-child) {
  margin-bottom: 0;
}

.pdf-viewer :deep(.textLayer .highlight) {
  background: rgba(250, 204, 21, 0.58);
  border-radius: 2px;
}

.pdf-viewer :deep(.textLayer .highlight.selected) {
  background: rgba(249, 115, 22, 0.68);
}

.pdf-page-status {
  font-size: 13px;
  font-weight: 400;
  color: #606266;
  white-space: nowrap;
}

.pdf-toolbar {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.pdf-view-mode {
  --el-segmented-item-selected-bg-color: #ffffff;
  flex: none;
}

.pdf-view-mode :deep(.el-segmented__item-selected) {
  color: #409eff;
}

.risk-scroll {
  flex: 1;
  min-height: 0;
}

.risk-collapse {
  border-top: none;
  border-bottom: none;
}

.risk-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 58px;
  padding: 10px 6px;
  border-bottom: 1px solid #ebeef5;
}

.risk-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: 1px solid #ebeef5;
  background: transparent;
}

.risk-collapse :deep(.el-collapse-item__content) {
  padding: 12px 6px 16px;
}

.collapse-title {
  width: calc(100% - 24px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.collapse-main {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.collapse-name {
  font-size: 20px;
  font-weight: 700;
  color: #2d2d2d;
  line-height: 1.3;
}

.collapse-type {
  font-size: 12px;
  color: #7b8794;
}

.line {
  margin: 8px 0;
  color: #505050;
}

.quote-block {
  margin: 10px 0;
  padding: 12px;
  border-radius: 10px;
  background: #f3f4f6;
  border-left: 4px solid #9ca3af;
  color: #3f3f46;
}

.reason-block {
  margin: 10px 0;
  padding: 12px;
  border-radius: 10px;
  background: #fff7e6;
  border-left: 4px solid #e6a23c;
  color: #7a4f12;
}

.suggestion-block {
  margin: 10px 0;
  padding: 12px;
  border-radius: 10px;
  background: #eefaf1;
  border-left: 4px solid #26a269;
  color: #1f6a46;
}

.label {
  margin: 0 0 6px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #747474;
}

@media (max-width: 1280px) {
  .detail-page {
    height: auto;
    min-height: 0;
    overflow: visible;
  }

  .workspace {
    grid-template-columns: 1fr;
    overflow: visible;
  }

  .workspace.risk-focus {
    grid-template-columns: 1fr;
  }

  .summary-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .pdf-viewer-wrap {
    height: 65vh;
    min-height: 420px;
  }
}

@media (max-width: 900px) {
  .headline-content {
    flex-direction: column;
    align-items: flex-start;
  }

  .action-group {
    width: 100%;
    flex-wrap: wrap;
  }

  .summary-list {
    grid-template-columns: 1fr;
  }

  .pane-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .risk-header-right {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
