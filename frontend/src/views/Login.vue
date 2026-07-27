<template>
  <section class="login-page">
    <div class="login-bg-shape"></div>
    <el-card class="login-card" shadow="always">
      <h2>SmartAudit-AI</h2>
      <p class="sub">请输入账号密码登录</p>

      <el-form data-testid="login-form" ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input data-testid="username" v-model="form.username" clearable placeholder="请输入用户名" @keyup.enter="submitLogin" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input data-testid="password"
            v-model="form.password"
            type="password"
            show-password
            clearable
            placeholder="请输入密码"
            @keyup.enter="submitLogin"
          />
        </el-form-item>
      </el-form>

      <div class="actions">
        <el-button data-testid="login-submit" class="full" type="primary" :loading="loading" @click="submitLogin">登录</el-button>
        <el-button class="full" @click="useDemoToken">使用演示 Token（仅非严格模式）</el-button>
      </div>
    </el-card>
  </section>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { loginByPassword } from "../api/audit";
import { setToken } from "../utils/auth";

const router = useRouter();
const route = useRoute();
const formRef = ref();
const loading = ref(false);

const form = reactive({
  username: "",
  password: ""
});

const rules = {
  username: [{ required: true, message: "请输入用户名", trigger: ["blur", "change"] }],
  password: [{ required: true, message: "请输入密码", trigger: ["blur", "change"] }]
};

const goAfterLogin = () => {
  const redirect = route.query.redirect ? String(route.query.redirect) : "/";
  router.replace(redirect);
};

const submitLogin = async () => {
  await formRef.value?.validate();
  loading.value = true;
  try {
    const data = await loginByPassword({
      username: form.username.trim(),
      password: form.password
    });
    if (!data?.token) {
      throw new Error("登录成功但未返回 token");
    }
    setToken(data.token);
    ElMessage.success("登录成功");
    goAfterLogin();
  } finally {
    loading.value = false;
  }
};

const useDemoToken = () => {
  setToken("demo-token");
  ElMessage.success("已写入演示 Token");
  goAfterLogin();
};
</script>

<style scoped lang="scss">
.login-page {
  min-height: calc(100vh - 120px);
  display: grid;
  place-items: center;
  position: relative;
  overflow: hidden;
}

.login-bg-shape {
  position: absolute;
  width: 420px;
  height: 420px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(249, 171, 0, 0.25) 0%, rgba(249, 171, 0, 0) 70%);
  top: -90px;
  right: -90px;
}

.login-card {
  width: 420px;
  border-radius: 16px;
  position: relative;
  z-index: 1;
}

.login-card h2 {
  margin: 6px 0;
  font-size: 26px;
}

.sub {
  margin: 0 0 20px;
  color: #777;
}

.actions {
  display: grid;
  gap: 10px;
}

.full {
  width: 100%;
}

@media (max-width: 600px) {
  .login-card {
    width: 94%;
  }
}
</style>
