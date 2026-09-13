// 认证相关 API 调用
import { API_BASE_URL } from "./api";

export interface LoginResponse {
  username: string;
  user_id: number;
}

export interface WhoamiResponse {
  logged_in: boolean;
  username?: string;
  user_id?: number;
}

// 登录
export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE_URL}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include", // 携带/接收 Cookie
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || `登录失败 (HTTP ${res.status})`);
  }

  return res.json();
}

// 登出
export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}/api/logout`, {
    method: "POST",
    credentials: "include",
  });
}

// 检查当前登录状态
export async function whoami(): Promise<WhoamiResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/whoami`, {
      credentials: "include",
    });
    if (!res.ok) return { logged_in: false };
    return res.json();
  } catch {
    return { logged_in: false };
  }
}
