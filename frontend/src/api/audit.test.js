import { beforeEach, describe, expect, it, vi } from "vitest";

const { service } = vi.hoisted(() => ({
  service: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } }
  }
}));

vi.mock("axios", () => ({ default: { create: vi.fn(() => service) } }));

const {
  createAuditTask,
  getAuditTaskPage,
  getAuditTaskDetail,
  triggerAuditTask,
  getAuditTaskFile,
  deleteAuditTask,
  loginByPassword
} = await import("./audit");

describe("audit API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses multipart headers for file uploads", () => {
    const form = new FormData();
    createAuditTask(form);
    expect(service.post).toHaveBeenCalledWith("/v1/audit/tasks", form, {
      headers: { "Content-Type": "multipart/form-data" }
    });
  });

  it("exposes task and authentication endpoints", () => {
    getAuditTaskPage({ page: 1 });
    getAuditTaskDetail("t1");
    triggerAuditTask("t1");
    getAuditTaskFile("t1");
    deleteAuditTask("t1");
    loginByPassword({ username: "u", password: "p" });

    expect(service.get).toHaveBeenNthCalledWith(1, "/v1/audit/tasks", { params: { page: 1 } });
    expect(service.get).toHaveBeenNthCalledWith(2, "/v1/audit/tasks/t1");
    expect(service.get).toHaveBeenNthCalledWith(3, "/v1/audit/tasks/t1/file", { responseType: "arraybuffer" });
    expect(service.post).toHaveBeenCalledWith("/v1/audit/tasks/t1/trigger");
    expect(service.post).toHaveBeenCalledWith("/v1/auth/login", { username: "u", password: "p" });
    expect(service.delete).toHaveBeenCalledWith("/v1/audit/tasks/t1");
  });
});
