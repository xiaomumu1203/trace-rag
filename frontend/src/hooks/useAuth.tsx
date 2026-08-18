"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { authApi, clearToken, getToken, setToken } from "@/lib/api";
import type { User } from "@/lib/types";

const USERNAME_KEY = "learntrace_username";

interface AuthContextValue {
  user: User | null;
  username: string | null;
  isAuthed: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (data: { username: string; email: string; password: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [token, setTokenState] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    setTokenState(getToken());
    setUsername(localStorage.getItem(USERNAME_KEY));
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      clearToken();
      localStorage.removeItem(USERNAME_KEY);
      setTokenState(null);
      setUsername(null);
      router.replace("/login");
    };

    window.addEventListener("learntrace:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("learntrace:unauthorized", handleUnauthorized);
  }, [router]);

  const login = useCallback(
    async (uname: string, password: string) => {
      const res = await authApi.login(uname, password);
      setToken(res.access_token);
      setTokenState(res.access_token);
      localStorage.setItem(USERNAME_KEY, uname);
      setUsername(uname);
      router.push("/knowledge-bases");
    },
    [router]
  );

  const register = useCallback(
    async (data: { username: string; email: string; password: string }) => {
      await authApi.register(data);
      // 注册成功后自动登录
      await login(data.username, data.password);
    },
    [login]
  );

  const logout = useCallback(() => {
    clearToken();
    localStorage.removeItem(USERNAME_KEY);
    setTokenState(null);
    setUsername(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user: username ? { id: 0, username, email: "" } : null,
        username,
        isAuthed: !!token,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}
