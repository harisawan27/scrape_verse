"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import {
  User as UserIcon,
  Mail,
  Shield,
  Key,
  Copy,
  Check,
  Edit2,
  Trash2,
  LogOut,
  Sparkles,
  AlertTriangle,
  Loader2,
  ExternalLink,
  Radar,
  Database,
  Cloud,
  Layers,
  Calendar,
  Lock,
} from "lucide-react";
import { Header } from "../../components/layout/Header";
import { useUser } from "../../lib/userContext";
import { formatRelativeTime } from "../../lib/utils";

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

export default function SettingsPage() {
  const router = useRouter();
  const {
    user,
    userId,
    isAuthenticated,
    loading: userLoading,
    updateUserName,
    linkGoogleAccount,
    deleteAccount,
    signOut,
  } = useUser();

  // Name editing state
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameSuccess, setNameSuccess] = useState(false);

  // Copy UUID state
  const [copiedId, setCopiedId] = useState(false);

  // Google linking state
  const [linkingGoogle, setLinkingGoogle] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  // Delete modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  // Protect route
  useEffect(() => {
    if (!userLoading && !isAuthenticated) {
      router.replace("/sign-in");
    }
  }, [isAuthenticated, userLoading, router]);

  // Sync name input when user loads
  useEffect(() => {
    if (user?.name) {
      setNameInput(user.name);
    } else if (user?.email) {
      setNameInput(user.email.split("@")[0]);
    }
  }, [user]);

  const handleCopyId = () => {
    if (userId) {
      navigator.clipboard.writeText(userId);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const handleSaveName = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nameInput.trim()) return;

    try {
      setSavingName(true);
      await updateUserName(nameInput.trim());
      setIsEditingName(false);
      setNameSuccess(true);
      setTimeout(() => setNameSuccess(false), 3000);
    } catch (err) {
      console.error("Failed to update name:", err);
    } finally {
      setSavingName(false);
    }
  };

  const handleLinkGoogle = async () => {
    try {
      setLinkingGoogle(true);
      setLinkError(null);
      await linkGoogleAccount();
    } catch (err: any) {
      setLinkError(err?.message || "Failed to link Google account");
      setLinkingGoogle(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmText.toLowerCase() !== "delete my account") return;

    try {
      setDeleting(true);
      await deleteAccount();
    } catch (err) {
      console.error("Failed to delete account:", err);
      setDeleting(false);
    }
  };

  if (userLoading || (!isAuthenticated && userLoading)) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <Radar className="w-8 h-8 text-radar-cyan animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Loading user settings...</p>
        </div>
      </div>
    );
  }

  const displayName = user?.name || user?.email?.split("@")[0] || "Web Radar User";
  const userInitials = displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex-1 flex flex-col min-h-full">
      <Header
        title="Account & Tenant Settings"
        subtitle="Manage your identity, profile credentials, and workspace security"
      />

      <div className="flex-1 p-6 md:p-8 space-y-8 max-w-4xl mx-auto w-full">
        {/* 1. Profile & Identity Card */}
        <div className="rounded-2xl bg-[#0B0F19]/90 border border-space-700/80 p-6 md:p-8 shadow-xl relative overflow-hidden backdrop-blur-xl">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-cyan-400 to-teal-400" />

          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 pb-6 border-b border-space-800">
            <div className="flex items-center gap-4">
              {/* Profile Image or Initials Avatar */}
              <div className="relative">
                {user?.image ? (
                  <div className="h-16 w-16 rounded-2xl overflow-hidden border-2 border-cyan-400/50 shadow-lg shadow-cyan-500/20">
                    <img
                      src={user.image}
                      alt={displayName}
                      className="h-full w-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-xl font-extrabold text-space-950 shadow-lg shadow-cyan-500/20">
                    {userInitials}
                  </div>
                )}
                <span className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full bg-emerald-500 border-2 border-[#0B0F19]" />
              </div>

              {/* User Info & Edit Name */}
              <div>
                {!isEditingName ? (
                  <div className="flex items-center gap-2.5">
                    <h2 className="text-xl font-bold text-white tracking-tight">
                      {displayName}
                    </h2>
                    <button
                      onClick={() => setIsEditingName(true)}
                      className="p-1 rounded-lg text-slate-400 hover:text-cyan-400 hover:bg-space-800 transition-colors"
                      title="Edit Name"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    {nameSuccess && (
                      <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
                        <Check className="w-3 h-3" /> Saved
                      </span>
                    )}
                  </div>
                ) : (
                  <form onSubmit={handleSaveName} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={nameInput}
                      onChange={(e) => setNameInput(e.target.value)}
                      placeholder="Enter display name"
                      autoFocus
                      required
                      className="px-3 py-1 bg-space-950 border border-cyan-500/70 rounded-lg text-sm text-white focus:outline-none focus:ring-1 focus:ring-cyan-400"
                    />
                    <button
                      type="submit"
                      disabled={savingName}
                      className="px-3 py-1 bg-cyan-400 hover:bg-cyan-300 text-space-950 font-bold text-xs rounded-lg transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      {savingName ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Check className="w-3 h-3" />
                      )}
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsEditingName(false)}
                      className="px-2.5 py-1 text-slate-400 hover:text-white text-xs transition-colors"
                    >
                      Cancel
                    </button>
                  </form>
                )}
                <p className="text-xs text-slate-400 font-mono mt-0.5">{user?.email}</p>
              </div>
            </div>

            {/* Role Badge */}
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 text-xs font-bold uppercase tracking-wider">
                Tenant Owner
              </span>
            </div>
          </div>

          {/* Account Details Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-6">
            <div className="p-4 rounded-xl bg-space-950/60 border border-space-800 space-y-1">
              <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                <span className="flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-cyan-400" />
                  Primary Email
                </span>
                <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 font-sans font-semibold">
                  Verified
                </span>
              </div>
              <p className="text-sm font-semibold text-white truncate">{user?.email}</p>
            </div>

            <div className="p-4 rounded-xl bg-space-950/60 border border-space-800 space-y-1">
              <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                <span className="flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-cyan-400" />
                  Tenant ID (UUID)
                </span>
                <button
                  onClick={handleCopyId}
                  className="text-[10px] text-slate-400 hover:text-cyan-400 flex items-center gap-1 transition-colors cursor-pointer"
                >
                  {copiedId ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
              <p className="text-xs font-mono text-slate-300 truncate">{userId}</p>
            </div>

            <div className="p-4 rounded-xl bg-space-950/60 border border-space-800 space-y-1">
              <span className="text-xs text-slate-400 font-mono flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-cyan-400" />
                Member Since
              </span>
              <p className="text-xs font-mono text-slate-300">
                {user?.created_at
                  ? new Date(user.created_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })
                  : "Active Member"}
              </p>
            </div>

            <div className="p-4 rounded-xl bg-space-950/60 border border-space-800 space-y-1">
              <span className="text-xs text-slate-400 font-mono flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-emerald-400" />
                PostgreSQL Schema
              </span>
              <p className="text-xs font-mono text-emerald-400">
                neon_auth + public.watches (Isolated)
              </p>
            </div>
          </div>
        </div>

        {/* 2. Authentication & Connected Providers */}
        <div className="rounded-2xl bg-[#0B0F19]/90 border border-space-700/80 p-6 md:p-8 shadow-xl backdrop-blur-xl space-y-6">
          <div className="border-b border-space-800 pb-4">
            <h3 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
              <Key className="w-4 h-4 text-cyan-400" />
              Connected Identity Providers
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Sign in seamlessly with Google or your standard email and password.
            </p>
          </div>

          {linkError && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
              <span>{linkError}</span>
            </div>
          )}

          <div className="space-y-3">
            {/* Google Provider Card */}
            <div className="p-4 rounded-xl bg-space-950/70 border border-space-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-space-900 border border-space-700 flex items-center justify-center flex-shrink-0">
                  <GoogleIcon className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-bold text-white">Google Identity</p>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Enabled
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Allows 1-click single sign-on across all devices.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleLinkGoogle}
                disabled={linkingGoogle}
                className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-space-850 hover:bg-space-800 text-white font-semibold text-xs border border-space-700 hover:border-slate-500 transition-colors disabled:opacity-50 cursor-pointer flex-shrink-0"
              >
                {linkingGoogle ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                    <span>Connecting...</span>
                  </>
                ) : (
                  <>
                    <GoogleIcon className="w-3.5 h-3.5" />
                    <span>Connect Google Account</span>
                  </>
                )}
              </button>
            </div>

            {/* Email / Password Provider Card */}
            <div className="p-4 rounded-xl bg-space-950/70 border border-space-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-space-900 border border-space-700 flex items-center justify-center flex-shrink-0">
                  <Lock className="w-4 h-4 text-cyan-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-bold text-white">Email & Password</p>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                      Active
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Secured with argon2id hashed credentials in Neon Auth.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 3. Session Management & Sign Out */}
        <div className="rounded-2xl bg-[#0B0F19]/90 border border-space-700/80 p-6 md:p-8 shadow-xl backdrop-blur-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">Active Session</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Terminate your current authenticated session on this device.
            </p>
          </div>

          <button
            type="button"
            onClick={signOut}
            className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-space-850 hover:bg-space-800 text-slate-200 hover:text-white border border-space-700 font-semibold text-xs transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4 text-rose-400" />
            <span>Sign Out of Web Radar</span>
          </button>
        </div>

        {/* 4. Danger Zone */}
        <div className="rounded-2xl bg-rose-950/20 border border-rose-500/30 p-6 md:p-8 shadow-xl backdrop-blur-xl space-y-4">
          <div className="border-b border-rose-500/20 pb-3">
            <h3 className="text-base font-bold text-rose-300 tracking-tight flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              Danger Zone
            </h3>
            <p className="text-xs text-rose-400/80 mt-0.5">
              Permanently delete your Web Radar tenant workspace and all configured Watches.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-white">Delete Entire Account</p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Once deleted, your active scraper schedules and semantic change histories cannot be recovered.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setDeleteModalOpen(true)}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow-lg shadow-rose-600/20 transition-all cursor-pointer flex-shrink-0"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete Account</span>
            </button>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-[#0B0F19] border border-rose-500/40 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-400">
              <div className="h-10 w-10 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
              </div>
              <div>
                <h4 className="text-base font-bold text-white">Confirm Account Deletion</h4>
                <p className="text-xs text-slate-400 font-mono">This action is irreversible</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              This will permanently delete your Neon Auth profile, all associated watches, run history, and snapshot intelligence.
            </p>

            <div className="space-y-1.5">
              <label className="block text-[11px] text-slate-400 font-mono">
                To confirm, type <strong className="text-rose-400">delete my account</strong> below:
              </label>
              <input
                type="text"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                placeholder="delete my account"
                className="w-full px-3.5 py-2 bg-space-950 border border-rose-500/40 rounded-xl text-sm text-white placeholder-slate-600 focus:outline-none focus:border-rose-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setDeleteModalOpen(false);
                  setDeleteConfirmText("");
                }}
                disabled={deleting}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:text-white bg-space-900 hover:bg-space-850 transition-colors"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleDeleteAccount}
                disabled={
                  deleting || deleteConfirmText.toLowerCase() !== "delete my account"
                }
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              >
                {deleting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Permanently Delete</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
