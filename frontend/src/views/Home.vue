<template>
  <section class="home-page">
    <div class="hero-bar">
      <div class="hero-title-group">
        <h1>SmartAudit-AI 审查任务台</h1>
        <p>企业合同/招投标智能审查工作台</p>
      </div>
      <div class="hero-actions">
        <el-switch
          v-model="autoRefresh"
          inline-prompt
          active-text="自动刷新"
          inactive-text="已暂停"
          @change="handleAutoRefreshChange"
        />
        <el-button data-testid="new-task" type="primary" size="large" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新建审查任务
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="table-header">
          <span>任务列表（每 5 秒自动刷新）</span>
          <el-button :loading="loading" @click="loadTasks">立即刷新</el-button>
        </div>
      </template>

      <el-table data-testid="task-table" :data="tableData" v-loading="loading" border stripe>
        <el-table-column prop="taskNo" label="任务编号" min-width="180" />
        <el-table-column prop="taskName" label="任务名" min-width="220" />
        <el-table-column label="状态" width="140" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="dark">
              {{ row.status || "UNKNOWN" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险数(高/中/低)" min-width="180" align="center">
          <template #default="{ row }">
            <span class="risk-count high">{{ row.highRiskCount ?? 0 }}</span>
            <span class="split">/</span>
            <span class="risk-count medium">{{ row.mediumRiskCount ?? 0 }}</span>
            <span class="split">/</span>
            <span class="risk-count low">{{ row.lowRiskCount ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button data-testid="view-task" link type="primary" @click="goDetail(row)">查看详情</el-button>
            <el-button data-testid="delete-task" link type="danger" @click="removeTask(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager-wrap">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="query.pageSize"
          :current-page="query.pageNum"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="createDialogVisible"
      title="新建审查任务"
      width="560px"
      :close-on-click-modal="false"
      @closed="resetCreateForm"
    >
      <el-form ref="formRef" :model="createForm" :rules="rules" label-width="100px">
        <el-form-item label="任务名称" prop="taskName">
        <el-input data-testid="task-name" v-model="createForm.taskName" maxlength="80" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="上传 PDF" prop="file">
          <el-upload data-testid="pdf-upload"
            ref="uploadRef"
            drag
            action="#"
            :auto-upload="false"
            :show-file-list="true"
            :limit="1"
            accept=".pdf"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽 PDF 到这里，或点击上传</div>
          </el-upload>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button data-testid="create-task" type="primary" :loading="submitLoading" @click="submitCreateTask">创建任务</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, UploadFilled } from "@element-plus/icons-vue";
import { createAuditTask, deleteAuditTask, getAuditTaskPage } from "../api/audit";

const router = useRouter();
const formRef = ref();
const uploadRef = ref();
const autoRefreshTimer = ref(null);

const loading = ref(false);
const submitLoading = ref(false);
const createDialogVisible = ref(false);
const autoRefresh = ref(true);
const tableData = ref([]);
const total = ref(0);
const selectedFile = ref(null);

const query = reactive({
  pageNum: 1,
  pageSize: 10
});

const createForm = reactive({
  taskName: "",
  file: null
});

const rules = {
  taskName: [{ required: true, message: "请输入任务名称", trigger: "blur" }],
  file: [{ required: true, message: "请上传 PDF 文件", trigger: "change" }]
};

const statusTagType = (status) => {
  const s = (status || "").toUpperCase();
  if (s === "COMPLETED") return "success";
  if (s === "FAILED") return "danger";
  if (s === "PROCESSING") return "warning";
  return "info";
};

const normalizePage = (data) => {
  if (Array.isArray(data)) {
    return { records: data, total: data.length };
  }
  return {
    records: data?.records || [],
    total: Number(data?.total || 0)
  };
};

const loadTasks = async (silent = false) => {
  if (!silent) loading.value = true;
  try {
    const data = await getAuditTaskPage(query);
    const page = normalizePage(data);
    tableData.value = page.records;
    total.value = page.total;
  } finally {
    if (!silent) loading.value = false;
  }
};

const startAutoRefresh = () => {
  stopAutoRefresh();
  autoRefreshTimer.value = setInterval(async () => {
    if (document.hidden || !autoRefresh.value || createDialogVisible.value || loading.value) {
      return;
    }
    try {
      await loadTasks(true);
    } catch (error) {
      console.warn("auto refresh failed", error);
    }
  }, 5000);
};

const stopAutoRefresh = () => {
  if (autoRefreshTimer.value) {
    clearInterval(autoRefreshTimer.value);
    autoRefreshTimer.value = null;
  }
};

const handleAutoRefreshChange = (enabled) => {
  if (enabled) {
    startAutoRefresh();
    ElMessage.success("已开启自动刷新");
  } else {
    stopAutoRefresh();
    ElMessage.info("已暂停自动刷新");
  }
};

const handlePageChange = (page) => {
  query.pageNum = page;
  loadTasks();
};

const openCreateDialog = () => {
  createDialogVisible.value = true;
};

const handleFileChange = (uploadFile) => {
  selectedFile.value = uploadFile.raw || null;
  createForm.file = selectedFile.value;
};

const handleFileRemove = () => {
  selectedFile.value = null;
  createForm.file = null;
};

const resetCreateForm = () => {
  createForm.taskName = "";
  createForm.file = null;
  selectedFile.value = null;
  formRef.value?.clearValidate();
  uploadRef.value?.clearFiles();
};

const submitCreateTask = async () => {
  await formRef.value?.validate();
  if (!selectedFile.value) {
    ElMessage.warning("请先上传 PDF 文件");
    return;
  }

  submitLoading.value = true;
  try {
    const taskNo = `WEB-${Date.now()}`;
    const formData = new FormData();
    formData.append("taskName", createForm.taskName);
    formData.append("file", selectedFile.value);
    formData.append("taskNo", taskNo);

    await createAuditTask(formData);
    ElMessage.success("任务创建成功");
    createDialogVisible.value = false;
    await loadTasks();
  } finally {
    submitLoading.value = false;
  }
};

const removeTask = async (row) => {
  await ElMessageBox.confirm(`确认删除任务 ${row.taskNo || row.id} 吗？`, "删除确认", {
    type: "warning",
    confirmButtonText: "删除",
    cancelButtonText: "取消"
  });
  await deleteAuditTask(row.id);
  ElMessage.success("任务已删除");
  await loadTasks();
};

const goDetail = (row) => {
  router.push({ name: "detail", params: { id: String(row.id) } });
};

onMounted(async () => {
  await loadTasks();
  if (autoRefresh.value) {
    startAutoRefresh();
  }
});

onBeforeUnmount(stopAutoRefresh);
</script>

<style scoped lang="scss">
.home-page {
  display: grid;
  gap: 18px;
}

.hero-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: 16px;
  padding: 20px 22px;
  background: linear-gradient(125deg, #fff4ea 0%, #f3fbff 100%);
  border: 1px solid #f1e7da;
}

.hero-title-group h1 {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 700;
  color: #2b2b2b;
}

.hero-title-group p {
  margin: 0;
  color: #6f6f6f;
  font-size: 14px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.table-card {
  border-radius: 16px;
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.risk-count {
  font-weight: 700;
}

.risk-count.high {
  color: #d73a49;
}

.risk-count.medium {
  color: #d28800;
}

.risk-count.low {
  color: #2a78c6;
}

.split {
  margin: 0 6px;
  color: #b0b0b0;
}

.pager-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .hero-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .hero-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
