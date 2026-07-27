<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand" @click="goHome">
        <div class="logo-dot"></div>
        <div>
          <h1>SmartAudit-AI</h1>
          <p>Enterprise Contract Intelligence Console</p>
        </div>
      </div>

      <div class="topbar-actions" v-if="!isLoginPage">
        <el-tag type="success" effect="plain" round>已登录</el-tag>
        <el-button type="danger" plain @click="logout">退出登录</el-button>
      </div>
    </header>

    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";
import { removeToken } from "./utils/auth";

const router = useRouter();
const route = useRoute();
const isLoginPage = computed(() => route.name === "login");

const goHome = () => {
  if (!isLoginPage.value) {
    router.push("/");
  }
};

const logout = async () => {
  try {
    await ElMessageBox.confirm("确定退出登录吗？", "提示", {
      type: "warning"
    });
    removeToken();
    router.replace("/login");
  } catch {
    // ignore cancel
  }
};
</script>

<style lang="scss">
:root {
  --bg-grad-a: #fff7ee;
  --bg-grad-b: #f3f9ff;
  --line: #ebe7df;
  --text-main: #2f2f2f;
  --text-sub: #747474;
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  margin: 0;
  width: 100%;
  min-height: 100%;
}

body {
  font-family: "IBM Plex Sans", "Noto Sans SC", "PingFang SC", sans-serif;
  color: var(--text-main);
  background: linear-gradient(140deg, var(--bg-grad-a), var(--bg-grad-b));
}

.app-shell {
  min-height: 100vh;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  padding: 12px 24px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}

.logo-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: linear-gradient(120deg, #ef4444, #f59e0b);
  box-shadow: 0 0 0 6px rgba(245, 158, 11, 0.12);
}

.brand h1 {
  margin: 0;
  line-height: 1.1;
  font-size: 20px;
}

.brand p {
  margin: 2px 0 0;
  color: var(--text-sub);
  font-size: 12px;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.app-main {
  max-width: 1240px;
  margin: 0 auto;
  padding: 22px;
}

@media (max-width: 768px) {
  .topbar {
    padding: 10px 14px;
  }

  .app-main {
    padding: 14px;
  }

  .topbar-actions .el-tag {
    display: none;
  }
}
</style>

