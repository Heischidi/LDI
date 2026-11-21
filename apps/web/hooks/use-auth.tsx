"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  clearStoredSession,
  getStoredTokens,
  ldiApi,
  setStoredSession,
} from "@/lib/api-client";
import type { UserSummary } from "@/types";

interface AuthContextValue {
  user: UserSummary | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
  hasRole: () => false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const { access } = getStoredTokens();
    if (!access) {
      setLoading(false);
      return;
    }
    ldiApi
      .me()
      .then((u) => setUser(u))
      .catch(() => {
        clearStoredSession();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await ldiApi.login(email, password);
    setStoredSession(res);
    setUser(res.user);
    router.push("/dashboard");
  };

  const logout = async () => {
    try {
      await ldiApi.logout();
    } catch {
      // ignore network error during logout
    }
    clearStoredSession();
    setUser(null);
    router.push("/login");
  };

  const hasRole = (...roles: string[]) => {
    if (!user) return false;
    if (user.role === "SUPER_ADMIN" || user.role === "CEO") return true;
    return roles.includes(user.role);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
