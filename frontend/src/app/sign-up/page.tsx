"use client";

import React, { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Radar,
  Lock,
  Mail,
  ArrowRight,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  Check,
  Circle,
  Shield,
  ShieldCheck,
  Zap,
  Activity,
} from "lucide-react";
import { useUser } from "../../lib/userContext";

interface PasswordRule {
  id: string;
  label: string;
  validator: (p: string) => boolean;
}

const PASSWORD_RULES: PasswordRule[] = [
  {
    id: "length",
    label: "8+ characters",
    validator: (p) => p.length >= 8,
  },
  {
    id: "lowercase",
    label: "Lowercase letter (a-z)",
    validator: (p) => /[a-z]/.test(p),
  },
  {
    id: "uppercase",
    label: "Uppercase letter (A-Z)",
    validator: (p) => /[A-Z]/.test(p),
  },
  {
    id: "number",
    label: "Number (0-9)",
    validator: (p) => /[0-9]/.test(p),
  },
  {
    id: "special",
    label: "Special character (!@#$...)",
    validator: (p) => /[^A-Za-z0-9]/.test(p),
  },
];

export default function SignUpPage() {
  const router = useRouter();
  const { signUp, isAuthenticated } = useUser();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If already authenticated, redirect
  React.useEffect(() => {
    if (isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, router]);

  // Compute rule satisfaction in real-time
  const ruleStatuses = useMemo(() => {
    return PASSWORD_RULES.map((rule) => ({
      ...rule,
      passed: rule.validator(password),
    }));
  }, [password]);

  const passedCount = useMemo(() => {
    return ruleStatuses.filter((r) => r.passed).length;
  }, [ruleStatuses]);

  // Strength score: 0 to 4
  const strength = useMemo(() => {
    if (!password) return { score: 0, label: "", color: "bg-slate-700", text: "text-slate-500" };
    if (passedCount <= 2) return { score: 1, label: "Weak", color: "bg-rose-500", text: "text-rose-400" };
    if (passedCount === 3) return { score: 2, label: "Fair", color: "bg-amber-500", text: "text-amber-400" };
    if (passedCount === 4) return { score: 3, label: "Good", color: "bg-cyan-500", text: "text-cyan-400" };
    return { score: 4, label: "Strong & Secure", color: "bg-emerald-500", text: "text-emerald-400" };
  }, [password, passedCount]);

  const passwordsMatch = useMemo(() => {
    if (!confirmPassword) return null;
    return password === confirmPassword;
  }, [password, confirmPassword]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("Please enter both email and password.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (passedCount < 3) {
      setError("Please choose a stronger password containing uppercase, lowercase, and numbers or symbols.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match. Please verify your confirmation.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await signUp(email.trim(), password);
      router.push("/");
    } catch (err: any) {
      setError(err?.message || "Failed to create account. Email may already be in use.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#07090E] text-slate-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Dynamic Ambient Background Elements */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[34rem] h-[34rem] bg-gradient-to-tr from-cyan-600/15 via-blue-500/10 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 left-1/4 w-80 h-80 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-10 right-1/4 w-72 h-72 bg-teal-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Grid Overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293d0a_1px,transparent_1px),linear-gradient(to_bottom,#1f293d0a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        {/* Brand Header */}
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
            Create your account
          </h1>
          <p className="mt-2 text-sm text-slate-400 max-w-sm">
            Continuous background surveillance with semantic change detection.
          </p>
        </div>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        {/* Glassmorphism Card */}
        <div className="bg-[#0B0F19]/90 backdrop-blur-2xl py-8 px-6 shadow-2xl shadow-black/80 rounded-2xl border border-slate-800/80 sm:px-10 relative">
          
          {/* Top subtle glow line */}
          <div className="absolute top-0 inset-x-8 h-px bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent" />

          {error && (
            <div className="mb-5 p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/50 flex items-start gap-2.5 text-rose-200 text-sm animate-shake">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            {/* Email Field */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Email address
              </label>
              <div className="relative rounded-xl">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="block w-full pl-10 pr-3.5 py-2.5 bg-[#0F1422] border border-slate-700/80 rounded-xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all shadow-inner"
                />
              </div>
            </div>

            {/* Password Field with Eye Toggle */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Password
                </label>
                {password && (
                  <span className={`text-xs font-semibold ${strength.text}`}>
                    {strength.label}
                  </span>
                )}
              </div>
              <div className="relative rounded-xl">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className="block w-full pl-10 pr-10 py-2.5 bg-[#0F1422] border border-slate-700/80 rounded-xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all shadow-inner"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200 transition-colors focus:outline-none"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>

              {/* Password Strength Indicator Bars */}
              {password.length > 0 && (
                <div className="mt-2 space-y-2">
                  <div className="grid grid-cols-4 gap-1.5 h-1.5">
                    {[1, 2, 3, 4].map((step) => (
                      <div
                        key={step}
                        className={`h-full rounded-full transition-all duration-300 ${
                          strength.score >= step ? strength.color : "bg-slate-800"
                        }`}
                      />
                    ))}
                  </div>

                  {/* Interactive Real-Time Rules Checklist */}
                  <div className="pt-1.5 grid grid-cols-2 gap-1.5 text-[11px]">
                    {ruleStatuses.map((rule) => (
                      <div
                        key={rule.id}
                        className={`flex items-center gap-1.5 py-1 px-2 rounded-md transition-colors ${
                          rule.passed
                            ? "bg-emerald-950/40 text-emerald-300 border border-emerald-800/40"
                            : "bg-slate-900/60 text-slate-400 border border-slate-800/60"
                        }`}
                      >
                        {rule.passed ? (
                          <Check className="w-3 h-3 text-emerald-400 shrink-0" />
                        ) : (
                          <Circle className="w-2.5 h-2.5 text-slate-600 shrink-0" />
                        )}
                        <span className="truncate">{rule.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Confirm Password Field with Eye Toggle */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Confirm Password
                </label>
                {confirmPassword && (
                  <span
                    className={`text-xs font-semibold ${
                      passwordsMatch ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {passwordsMatch ? "Passwords match" : "Mismatch"}
                  </span>
                )}
              </div>
              <div className="relative rounded-xl">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter your password"
                  className={`block w-full pl-10 pr-10 py-2.5 bg-[#0F1422] border rounded-xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 transition-all shadow-inner ${
                    confirmPassword && !passwordsMatch
                      ? "border-rose-700/80 focus:ring-rose-500/50 focus:border-rose-500"
                      : "border-slate-700/80 focus:ring-cyan-500/50 focus:border-cyan-500"
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200 transition-colors focus:outline-none"
                >
                  {showConfirmPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center gap-2 py-2.5 px-4 border border-transparent rounded-xl shadow-lg shadow-cyan-500/20 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 via-cyan-600 to-teal-500 hover:from-blue-500 hover:via-cyan-500 hover:to-teal-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 focus:ring-offset-[#07090E] transition-all disabled:opacity-50 disabled:cursor-not-allowed transform active:scale-[0.99]"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating Account with Neon Auth...
                  </>
                ) : (
                  <>
                    Create Account & Get Started
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Sign In Link */}
          <div className="mt-6 pt-5 border-t border-slate-800/80 text-center">
            <p className="text-sm text-slate-400">
              Already have an account?{" "}
              <Link href="/sign-in" className="font-semibold text-cyan-400 hover:text-cyan-300 hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        </div>

        {/* Feature Badges Footer */}
        <div className="mt-8 grid grid-cols-3 gap-2 text-center">
          <div className="flex flex-col items-center gap-1 p-2 rounded-xl bg-slate-900/40 border border-slate-800/40 text-slate-400">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-[11px] font-medium">Neon Auth</span>
          </div>
          <div className="flex flex-col items-center gap-1 p-2 rounded-xl bg-slate-900/40 border border-slate-800/40 text-slate-400">
            <Zap className="w-4 h-4 text-cyan-400" />
            <span className="text-[11px] font-medium">Bright Data</span>
          </div>
          <div className="flex flex-col items-center gap-1 p-2 rounded-xl bg-slate-900/40 border border-slate-800/40 text-slate-400">
            <Activity className="w-4 h-4 text-indigo-400" />
            <span className="text-[11px] font-medium">Self-Healing</span>
          </div>
        </div>
      </div>
    </div>
  );
}
