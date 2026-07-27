import { createRouter, createWebHistory } from "vue-router";
import { hasToken } from "../utils/auth";

const routes = [
  {
    path: "/login",
    name: "login",
    component: () => import("../views/Login.vue"),
    meta: { requiresAuth: false }
  },
  {
    path: "/",
    name: "home",
    component: () => import("../views/Home.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/task/:id",
    name: "detail",
    component: () => import("../views/Detail.vue"),
    props: true,
    meta: { requiresAuth: true }
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/"
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

router.beforeEach((to, from, next) => {
  const loggedIn = hasToken();
  if (to.meta.requiresAuth && !loggedIn) {
    next({ name: "login", query: { redirect: to.fullPath } });
    return;
  }

  if (to.name === "login" && loggedIn) {
    next((to.query.redirect && String(to.query.redirect)) || "/");
    return;
  }

  next();
});

export default router;

