import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { login as apiLogin, logout as apiLogout, whoami } from "@/lib/auth";

interface AuthState {
  loggedIn: boolean;
  username: string | null;
  userId: number | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  loggedIn: false,
  username: null,
  userId: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  // 初始化时检查登录状态
  useEffect(() => {
    whoami().then((data) => {
      if (data.logged_in && data.username) {
        setLoggedIn(true);
        setUsername(data.username);
        setUserId(data.user_id ?? null);
      }
      setLoading(false);
    });
  }, []);

  const login = useCallback(async (uname: string, password: string) => {
    const data = await apiLogin(uname, password);
    setLoggedIn(true);
    setUsername(data.username);
    setUserId(data.user_id);
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setLoggedIn(false);
    setUsername(null);
    setUserId(null);
  }, []);

  return (
    <AuthContext.Provider value={{ loggedIn, username, userId, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
