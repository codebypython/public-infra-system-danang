"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";
import {
  BarChart3,
  Camera,
  CircleUser,
  ClipboardList,
  Command,
  LogOut,
  Map as MapIcon,
  Shield,
  Wrench,
} from "lucide-react";

import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/lib/store/auth";
import { cn } from "@/lib/utils";
import { NotificationBell } from "@/components/NotificationBell";

type Role = "citizen" | "operator" | "taskforce" | "admin";

const NAV: Record<Role, { href: string; label: string; icon: any }[]> = {
  citizen: [
    { href: "/map", label: "Bản đồ", icon: MapIcon },
    { href: "/report", label: "Báo cáo sự cố", icon: ClipboardList },
    { href: "/my-tickets", label: "Báo cáo của tôi", icon: ClipboardList },
  ],
  operator: [
    { href: "/operator/command-center", label: "Command Center", icon: Command },
    { href: "/operator/reports", label: "Báo cáo", icon: ClipboardList },
    { href: "/operator/tasks", label: "Tác vụ", icon: Wrench },
    { href: "/operator/analytics", label: "Phân tích", icon: BarChart3 },
    { href: "/map", label: "Bản đồ", icon: MapIcon },
  ],
  taskforce: [
    { href: "/taskforce/my-tasks", label: "Tác vụ của tôi", icon: Wrench },
    { href: "/taskforce/route", label: "Lộ trình", icon: MapIcon },
  ],
  admin: [
    { href: "/admin/dashboard", label: "Tổng quan", icon: BarChart3 },
    { href: "/admin/users", label: "Người dùng", icon: CircleUser },
    { href: "/admin/assets", label: "Tài sản", icon: MapIcon },
    { href: "/admin/cameras", label: "Camera AI", icon: Camera },
    { href: "/admin/audit", label: "Audit Log", icon: Shield },
    { href: "/operator/command-center", label: "Command Center", icon: Command },
  ],
};

export function AppShell({
  role,
  children,
}: {
  role: Role;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const clear = useAuthStore((s) => s.clear);

  useEffect(() => {
    if (!useAuthStore.getState().isAuthenticated()) {
      router.replace("/login");
    }
  }, [router]);

  useEffect(() => {
    if (user) return;
    apiClient
      .get<any>("/auth/me")
      .then((u) => useAuthStore.getState().setUser(u))
      .catch(() => clear());
  }, [user, clear]);

  const nav = useMemo(() => NAV[role], [role]);

  async function logout() {
    try {
      if (refreshToken) {
        await apiClient.post(
          "/auth/logout",
          { refresh_token: refreshToken },
          { skipAuth: true }
        );
      }
    } catch {
      /* ignore */
    } finally {
      clear();
      router.push("/login");
    }
  }

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 border-r border-border bg-card hidden lg:flex flex-col">
        <Link
          href="/"
          className="flex items-center gap-2 px-4 h-14 border-b border-border font-semibold"
        >
          <div className="size-8 rounded-lg bg-primary text-primary-foreground grid place-items-center font-bold text-sm">
            ĐN
          </div>
          Đà Nẵng Infra
        </Link>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map((n) => {
            const Icon = n.icon;
            const active = pathname === n.href || pathname?.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-accent text-foreground"
                )}
              >
                <Icon className="size-4" />
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-border space-y-2">
          <div className="flex items-center gap-2 px-2 py-1.5">
            <div className="size-8 rounded-full bg-accent grid place-items-center text-sm font-semibold">
              {user?.full_name?.[0] ?? user?.email?.[0]?.toUpperCase()}
            </div>
            <div className="text-xs">
              <div className="font-medium truncate">{user?.full_name ?? user?.email}</div>
              <div className="text-muted-foreground capitalize">{role}</div>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded-md hover:bg-accent"
          >
            <LogOut className="size-4" />
            Đăng xuất
          </button>
        </div>
      </aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-border flex items-center justify-between px-4 lg:px-6 bg-card">
          <div className="font-medium capitalize">
            {nav.find((n) => pathname === n.href)?.label ??
              nav.find((n) => pathname?.startsWith(n.href))?.label ??
              "Dashboard"}
          </div>
          <div className="flex items-center gap-2">
            <NotificationBell />
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
