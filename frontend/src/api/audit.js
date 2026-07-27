import axios from "axios";
import { ElMessage } from "element-plus";
import router from "../router";
import { getToken, removeToken } from "../utils/auth";

const service = axios.create({
  baseURL: "/api",
  timeout: 20000
});

service.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

service.interceptors.response.use(
  (response) => {
    const res = response.data;
    if (typeof res?.code === "number" && res.code !== 200) {
      ElMessage.error(res.msg || "请求失败");
      return Promise.reject(new Error(res.msg || "Request failed"));
    }
    return res?.data ?? res;
  },
  (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      removeToken();
      if (router.currentRoute.value.name !== "login") {
        router.replace({
          name: "login",
          query: { redirect: router.currentRoute.value.fullPath }
        });
      }
      ElMessage.error("登录已过期，请重新登录");
      return Promise.reject(error);
    }

    ElMessage.error(error?.response?.data?.msg || error.message || "网络异常");
    return Promise.reject(error);
  }
);

export const createAuditTask = (payload) => {
  if (payload instanceof FormData) {
    return service.post("/v1/audit/tasks", payload, {
      headers: {
        "Content-Type": "multipart/form-data"
      }
    });
  }
  return service.post("/v1/audit/tasks", payload);
};

export const getAuditTaskPage = (params) => service.get("/v1/audit/tasks", { params });

export const getAuditTaskDetail = (id) => service.get(`/v1/audit/tasks/${id}`);

export const triggerAuditTask = (id) => service.post(`/v1/audit/tasks/${id}/trigger`);

export const getAuditTaskFile = (id) =>
  service.get(`/v1/audit/tasks/${id}/file`, {
    responseType: "arraybuffer"
  });

export const deleteAuditTask = (id) => service.delete(`/v1/audit/tasks/${id}`);

export const loginByPassword = (payload) => service.post("/v1/auth/login", payload);
