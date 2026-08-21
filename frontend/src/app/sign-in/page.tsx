"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Radar,
  Lock,
  Mail,
  ArrowRight,
  Loader2,
  AlertCircle,
  Eye,
  EyeOff,
  ShieldCheck,
  Zap,
  Activity,
  Info,
} from "lucide-react";
import { useUser } from "../../lib/userContext";

function GoogleIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.27 21.43 7.35 24 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 10.03 0 12s.45 3.82 1.25 5.42l4.03-3.15Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.35 0 3.27 2.57 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98Z"
      />
    </svg>
  );
}

function SignInForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signIn, signInWithGoogle, isAuthenticated, loading: userLoading } = useUser();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Inspect URL parameters for OAuth errors
  useEffect(() => {
    const urlError = searchParams?.get("error");
    const urlErrorDesc = searchParams?.get("error_description");

    if (urlError) {
      if (urlError === "account_not_linked" || urlError === "unable_to_link_account") {
        setError(
          "An account with this email was registered using email & password. Sign in with your password below, then click 'Connect Google' in the sidebar to link your Google login."
        );
      } else if (urlError === "access_denied") {
        setError("Google authentication was cancelled.");
      } else {
        setError(urlErrorDesc || `Google sign-in error: ${urlError}`);
      }
    }
  }, [searchParams]);

  // If already authenticated, redirect to Command Center
  useEffect(() => {
    if (!userLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, userLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("Please enter both email and password.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await signIn(email.trim(), password);
      router.replace("/");
      router.refresh();
    } catch (err: any) {
      setError(err?.message || "Invalid email or password. Please verify your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    try {
      setGoogleLoading(true);
      setError(null);
      await signInWithGoogle();
    } catch (err: any) {
      setError(err?.message || "Google sign-in failed. Please try again.");
      setGoogleLoading(false);
    }
  };

  return (
    <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
      {/* Brand Header & Radar Badge */}
      <div className="flex flex-col items-center justify-center text-center mb-8">
        <Link href="/" className="inline-flex items-center gap-3 group mb-4">
          <div className="relative flex items-center justify-center h-12 w-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-cyan-500 p-0.5 shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform">
            <div className="w-full h-full bg-[#0B0F19] rounded-[14px] flex items-center justify-center">
              <Radar className="w-6 h-6 text-cyan-400 animate-spin-slow" />
            </div>
            <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-cyan-400 shadow-[0_0_10px_#06b6d4] animate-pulse" />
          </div>
          <div className="text-left">
            <span className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-100 to-slate-400">
              Web Radar
            </span>
            <span className="block text-[10px] uppercase font-bold tracking-widest text-cyan-400">
              Autonomous Monitoring
            </span>
          </div>
        </Link>

        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
          Sign in to Web Radar
        </h1>
        <p className="mt-2 text-sm text-slate-400 max-w-sm">
          Autonomous, persistent web monitoring with Bright Data scrapers & Neon PostgreSQL.
        </p>
      </div>

      {/* Auth Card */}
      <div className="bg-[#0B0F19]/90 border border-space-700/80 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-cyan-400 to-teal-400" />

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-rose-300 text-sm animate-in fade-in slide-in-from-top-2">
            <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium text-rose-200">Authentication Notice</p>
              <p className="mt-0.5 text-xs text-rose-300/90 leading-relaxed">{error}</p>
            </div>
          </div>
        )}

        {/* 1. Continue with Google */}
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={loading || googleLoading}
          className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-space-850 hover:bg-space-800 text-white font-medium text-sm rounded-xl border border-space-700/80 shadow-md hover:border-slate-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed group cursor-pointer"
        >
          {googleLoading ? (
            <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
          ) : (
            <GoogleIcon className="w-5 h-5 flex-shrink-0" />
          )}
          <span>Continue with Google</span>
        </button>

        {/* 2. Divider */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-space-700/70" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-[#0B0F19] px-3 text-slate-500 font-medium tracking-wider">
              or continue with email
            </span>
          </div>
        </div>

        {/* 3. Email & Password Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Email Address
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                <Mail className="h-4 w-4" />
              </div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                autoComplete="email"
                required
                className="w-full pl-10 pr-4 py-2.5 bg-space-950/80 border border-space-700 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                <Lock className="h-4 w-4" />
              </div>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
                className="w-full pl-10 pr-11 py-2.5 bg-space-950/80 border border-space-700 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-500 hover:text-slate-300 focus:outline-none"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || googleLoading}
            className="w-full mt-2 flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-semibold text-sm text-space-950 bg-gradient-to-r from-cyan-400 to-blue-500 hover:from-cyan-300 hover:to-blue-400 shadow-lg shadow-cyan-500/25 active:scale-[0.99] transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-space-950" />
                <span>Signing In...</span>
              </>
            ) : (
              <>
                <span>Sign In</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer Switch to Sign Up */}
        <div className="mt-6 pt-5 border-t border-space-800 text-center">
          <p className="text-sm text-slate-400">
            Don&apos;t have an account?{" "}
            <Link
              href="/sign-up"
              className="font-semibold text-cyan-400 hover:text-cyan-300 transition-colors inline-flex items-center gap-1"
            >
              Create Account
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </p>
        </div>
      </div>

      {/* Security badge */}
      <div className="mt-8 flex items-center justify-center gap-2 text-xs text-slate-500 font-mono">
        <ShieldCheck className="w-4 h-4 text-emerald-400/80" />
        <span>Secured by Managed Neon Auth & AES-256 PostgreSQL</span>
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <div className="min-h-screen w-full bg-[#07090E] text-slate-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Dynamic Ambient Background Elements */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[34rem] h-[34rem] bg-gradient-to-tr from-blue-600/15 via-cyan-500/10 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 right-1/4 w-80 h-80 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-10 left-1/4 w-72 h-72 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Grid Overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293d0a_1px,transparent_1px),linear-gradient(to_bottom,#1f293d0a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      <Suspense fallback={
        <div className="sm:mx-auto sm:w-full sm:max-w-md text-center py-12">
          <Loader2 className="w-8 h-8 text-cyan-400 animate-spin mx-auto mb-3" />
          <p className="text-xs text-slate-400 font-mono">Loading authentication...</p>
        </div>
      }>
        <SignInForm />
      </Suspense>
    </div>
  );
}
