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
  signInWithGoogle: () => Promise<void>;
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
  signInWithGoogle: async () => {},
  signOut: async () => {},
  refreshUser: async () => {},
});

function extractErrorMessage(err: unknown, fallback: string): string {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (typeof err === "object" && err !== null) {
    const obj = err as Record<string, unknown>;
    if (typeof obj.message === "string" && obj.message.trim().length > 0) {
      return obj.message;
    }
    if (typeof obj.statusText === "string" && obj.statusText.trim().length > 0) {
      return obj.statusText;
    }
  }
  return fallback;
}

export function UserProvider({ children }: { children: React.ReactNode }) {
  // 1. Reactive session hook from Neon Auth (powered by Better Auth React)
  const sessionResult = authClient.useSession();
  const sessionData = sessionResult?.data;
  const sessionPending = sessionResult?.isPending;
  const refetch = sessionResult?.refetch;

  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [loadingProfile, setLoadingProfile] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Sync session changes reactively
  const syncSession = useCallback(async () => {
    if (sessionPending) return;

    if (sessionData?.user) {
      const sessionUser = sessionData.user;
      const sessionToken =
        sessionData.session?.token || sessionData.session?.id || "";

      if (sessionToken) {
        api.setToken(sessionToken);
        setTokenState(sessionToken);
      }

      // Sync backend domain user profile
      try {
        setLoadingProfile(true);
        const me = await api.getMe();
        setUser(me);
      } catch {
        // Fallback to Neon Auth session data if backend profile is still provisioning
        setUser({
          id: sessionUser.id,
          email: sessionUser.email,
          auth_id: sessionUser.id,
          created_at: new Date().toISOString(),
        });
      } finally {
        setLoadingProfile(false);
      }
    } else {
      api.setToken(null);
      setUser(null);
      setTokenState(null);
      setLoadingProfile(false);
    }
  }, [sessionData, sessionPending]);

  useEffect(() => {
    syncSession();
  }, [syncSession]);

  const refreshUser = useCallback(async () => {
    if (refetch) {
      await refetch();
    }
    const sessionRes = await authClient.getSession().catch(() => null);
    if (sessionRes?.data?.user) {
      const sessionUser = sessionRes.data.user;
      const sessionToken =
        sessionRes.data.session?.token || sessionRes.data.session?.id || "";
      if (sessionToken) {
        api.setToken(sessionToken);
        setTokenState(sessionToken);
      }
      try {
        const me = await api.getMe();
        setUser(me);
      } catch {
        setUser({
          id: sessionUser.id,
          email: sessionUser.email,
          auth_id: sessionUser.id,
          created_at: new Date().toISOString(),
        });
      }
    } else {
      api.setToken(null);
      setUser(null);
      setTokenState(null);
    }
  }, [refetch]);

  const signIn = async (email: string, password: string) => {
    setError(null);
    try {
      const res = await authClient.signIn.email({
        email: email.trim(),
        password,
      });

      if (res?.error) {
        const msg = extractErrorMessage(res.error, "Invalid email or password");
        throw new Error(msg);
      }

      await refreshUser();
    } catch (err: unknown) {
      const msg = extractErrorMessage(err, "Invalid email or password");
      setError(msg);
      throw new Error(msg);
    }
  };

  const signUp = async (email: string, password: string, name?: string) => {
    setError(null);
    try {
      const res = await authClient.signUp.email({
        email: email.trim(),
        password,
        name: name || email.split("@")[0],
      });

      if (res?.error) {
        const msg = extractErrorMessage(res.error, "Failed to create account with Neon Auth");
        throw new Error(msg);
      }

      await refreshUser();
    } catch (err: unknown) {
      const msg = extractErrorMessage(err, "Failed to create account");
      setError(msg);
      throw new Error(msg);
    }
  };

  const signInWithGoogle = async () => {
    setError(null);
    try {
      const res = await authClient.signIn.social({
        provider: "google",
        callbackURL: "/",
      });

      if (res?.error) {
        const msg = extractErrorMessage(res.error, "Google sign-in failed");
        throw new Error(msg);
      }
    } catch (err: unknown) {
      const msg = extractErrorMessage(err, "Google sign-in failed. Please try again.");
      setError(msg);
      throw new Error(msg);
    }
  };

  const signOut = async () => {
    try {
      await authClient.signOut().catch(() => {});
    } finally {
      api.setToken(null);
      setUser(null);
      setTokenState(null);
      if (refetch) {
        await refetch();
      }
      if (typeof window !== "undefined") {
        window.location.href = "/sign-in";
      }
    }
  };

  const effectiveUser: User | null =
    user ||
    (sessionData?.user
      ? {
          id: sessionData.user.id,
          email: sessionData.user.email,
          auth_id: sessionData.user.id,
          created_at: new Date().toISOString(),
        }
      : null);

  const isAuthenticated = !!effectiveUser || (!!sessionData?.user && !sessionPending);
  const loading = sessionPending;
  const effectiveUserId = effectiveUser?.id || null;

  return (
    <UserContext.Provider
      value={{
        user: effectiveUser,
        userId: effectiveUserId,
        token,
        isAuthenticated,
        loading,
        error,
        signIn,
        signUp,
        signInWithGoogle,
        signOut,
        refreshUser,
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
