"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { User } from "../types";
import { authClient } from "./auth-client";
import { api } from "./api";

interface UserContextValue {
  user: User | null;
  userId: string | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name?: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const UserContext = createContext<UserContextValue>({
  user: null,
  userId: null,
  token: null,
  isAuthenticated: false,
  loading: true,
  error: null,
  signIn: async () => {},
  signUp: async () => {},
  signOut: async () => {},
  refreshUser: async () => {},
});

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const restoreSession = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // 1. Query managed Neon Auth session
      const sessionRes = await authClient.getSession().catch(() => null);
      if (sessionRes?.data?.session?.token) {
        const sessionToken = sessionRes.data.session.token;
        api.setToken(sessionToken);
        setTokenState(sessionToken);

        // 2. Resolve domain user profile from backend
        try {
          const me = await api.getMe();
          setUser(me);
        } catch {
          // If backend profile is being provisioned, fallback to Neon session info
          setUser({
            id: sessionRes.data.user.id,
            email: sessionRes.data.user.email,
            auth_id: sessionRes.data.user.id,
            created_at: new Date().toISOString(),
          });
        }
      } else {
        // No active Neon Auth session
        api.setToken(null);
        setUser(null);
        setTokenState(null);
      }
    } catch (err: any) {
      console.warn("Neon Auth session restoration failed:", err?.message);
      api.setToken(null);
      setUser(null);
      setTokenState(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const signIn = async (email: string, password: string) => {
    setError(null);
    setLoading(true);
    try {
      const res = await authClient.signIn.email({
        email: email.trim(),
        password,
      });

      if (res.error) {
        throw new Error(res.error.message || "Invalid email or password");
      }

      await restoreSession();
    } catch (err: any) {
      const msg = err?.message || "Invalid email or password";
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  };

  const signUp = async (email: string, password: string, name?: string) => {
    setError(null);
    setLoading(true);
    try {
      const res = await authClient.signUp.email({
        email: email.trim(),
        password,
        name: name || email.split("@")[0],
      });

      if (res.error) {
        throw new Error(res.error.message || "Failed to create account with Neon Auth");
      }

      await restoreSession();
    } catch (err: any) {
      const msg = err?.message || "Failed to create account";
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  };

  const signOut = async () => {
    try {
      await authClient.signOut().catch(() => {});
    } finally {
      api.setToken(null);
      setUser(null);
      setTokenState(null);
      if (typeof window !== "undefined") {
        window.location.href = "/sign-in";
      }
    }
  };

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  return (
    <UserContext.Provider
      value={{
        user,
        userId: user?.id || null,
        token,
        isAuthenticated: !!user,
        loading,
        error,
        signIn,
        signUp,
        signOut,
        refreshUser: restoreSession,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error("useUser must be used within a UserProvider");
  }
  return context;
}
