"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Eye, EyeOff, LogIn } from "lucide-react";

import { ApiError, apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/lib/store/auth";

const DEMO = [
  { role: "Admin", email: "admin@danang.gov.vn", password: "Admin@123" },
  { role: "Operator", email: "operator@danang.gov.vn", password: "Op@12345" },
  { role: "TaskForce", email: "tech@danang.gov.vn", password: "Tech@123" },
  { role: "Citizen", email: "citizen@danang.gov.vn", password: "User@123" },
];

export default function LoginPage() {
  const router = useRouter();
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await apiClient.post<{
        access_token: string;
        refresh_token: string;
      }>("/auth/login", { email, password }, { skipAuth: true });
      setTokens(tokens.access_token, tokens.refresh_token);
      const me = await apiClient.get<any>("/auth/me");
      setUser(me);
      const dest =
        me.role === "admin"
          ? "/admin/dashboard"
          : me.role === "operator"
          ? "/operator/command-center"
          : me.role === "taskforce"
          ? "/taskforce/my-tasks"
          : "/map";
      router.push(dest);
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Đăng nhập thất bại");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen grid lg:grid-cols-2">
      <section className="hidden lg:flex flex-col justify-between bg-primary text-primary-foreground p-10 relative overflow-hidden">
        <div className="absolute inset-0 opacity-20 pointer-events-none">
          <div className="absolute -top-32 -left-32 size-96 rounded-full bg-white/30 blur-3xl" />
          <div className="absolute bottom-0 right-0 size-[28rem] rounded-full bg-white/20 blur-3xl" />
        </div>
        <div className="relative">
          <div className="flex items-center gap-2 font-semibold">
            <div className="size-9 rounded-xl bg-white text-primary grid place-items-center font-bold">
              ĐN
            </div>
            <div>Đà Nẵng Smart Infrastructure</div>
          </div>
          <h1 className="mt-12 text-4xl font-bold leading-tight max-w-md">
            Quản lý hạ tầng — đồng bộ, thông minh, real-time.
          </h1>
          <p className="mt-4 max-w-md opacity-90">
            Một nền tảng cho 4 vai trò: Citizen, Operator, TaskForce và Admin.
          </p>
        </div>
        <div className="relative space-y-2 text-sm opacity-90">
          <p className="font-medium">Tài khoản demo:</p>
          <ul className="space-y-1 font-mono text-xs">
            {DEMO.map((d) => (
              <li key={d.email}>
                <span className="inline-block w-20">{d.role}</span>
                {d.email} / {d.password}
              </li>
            ))}
          </ul>
        </div>
      </section>
      <section className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-md space-y-5">
          <div>
            <h2 className="text-2xl font-bold">Đăng nhập</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Sử dụng tài khoản đã được cấp.
            </p>
          </div>
          {error && (
            <div className="px-3 py-2 rounded-md text-sm bg-danger/10 text-danger border border-danger/30">
              {error}
            </div>
          )}
          <label className="block text-sm">
            <span className="font-medium">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-md border border-input bg-card focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="ban@danang.gov.vn"
              autoComplete="email"
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium">Mật khẩu</span>
            <div className="relative">
              <input
                type={show ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full px-3 py-2 pr-10 rounded-md border border-input bg-card focus:outline-none focus:ring-2 focus:ring-ring"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShow((s) => !s)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground"
                aria-label={show ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              >
                {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </label>
          <button
            type="submit"
            disabled={loading}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground font-medium disabled:opacity-60"
          >
            <LogIn className="size-4" />
            {loading ? "Đang đăng nhập…" : "Đăng nhập"}
          </button>
          <div className="flex flex-wrap gap-2 pt-2">
            {DEMO.map((d) => (
              <button
                key={d.email}
                type="button"
                onClick={() => {
                  setEmail(d.email);
                  setPassword(d.password);
                }}
                className="text-xs px-2.5 py-1 rounded-md border border-border bg-card hover:bg-accent"
              >
                Dùng {d.role}
              </button>
            ))}
          </div>
        </form>
      </section>
    </main>
  );
}
