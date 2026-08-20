"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { User } from "../types";
import { api } from "./api";

interface UserContextValue {
  user: User | null;
  userId: string | null;
  loading: boolean;
  error: string | null;
  refreshUser: () => Promise<void>;
}

const UserContext = createContext<UserContextValue>({
  user: null,
  userId: null,
  loading: true,
  error: null,
  refreshUser: async () => {},
});

const USER_STORAGE_KEY = "web_radar_user_id";
const DEFAULT_EMAIL = "demo@webradar.io";

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const initUser = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.ensureUser(DEFAULT_EMAIL);
      setUser(res);
      if (typeof window !== "undefined") {
        localStorage.setItem(USER_STORAGE_KEY, res.id);
      }
    } catch (err: any) {
      console.error("Failed to initialize Web Radar user:", err);
      setError(err?.message || "Failed to connect to Web Radar backend");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    initUser();
  }, []);

  return (
    <UserContext.Provider
      value={{
        user,
        userId: user?.id || null,
        loading,
        error,
        refreshUser: initUser,
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
