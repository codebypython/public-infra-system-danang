"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ApiError, apiClient } from "@/lib/api/client";
import { formatDate } from "@/lib/utils";

export default function AdminUsersPage() {
  return (
    <AppShell role="admin">
      <UsersList />
    </AppShell>
  );
}

const ROLES = ["citizen", "operator", "taskforce", "admin"];

function UsersList() {
  const [items, setItems] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  async function refresh() {
    const data = await apiClient.get<any>("/users", {
      searchParams: { q: q || null, role: role || null, page_size: 100 },
    });
    setItems(data.items);
  }
  useEffect(() => {
    refresh();
  }, [q, role]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Quản lý người dùng</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-sm"
        >
          + Tạo người dùng
        </button>
      </div>
      <div className="flex gap-3 mb-4">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Tìm theo email / username / tên…"
          className="px-3 py-2 rounded-md border border-input bg-card flex-1"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="px-3 py-2 rounded-md border border-input bg-card"
        >
          <option value="">Tất cả role</option>
          {ROLES.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </div>
      <div className="rounded-xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-accent">
            <tr>
              <Th>Email</Th>
              <Th>Username</Th>
              <Th>Họ tên</Th>
              <Th>Role</Th>
              <Th>Trạng thái</Th>
              <Th>Đăng nhập gần nhất</Th>
            </tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.id} className="border-t border-border">
                <Td>{u.email}</Td>
                <Td>{u.username}</Td>
                <Td>{u.full_name ?? "—"}</Td>
                <Td>
                  <span className="px-2 py-0.5 rounded-full bg-accent text-xs capitalize">
                    {u.role}
                  </span>
                </Td>
                <Td>
                  <span
                    className={
                      "px-2 py-0.5 rounded-full text-xs " +
                      (u.is_active
                        ? "bg-success/10 text-success"
                        : "bg-muted text-muted-foreground")
                    }
                  >
                    {u.is_active ? "Hoạt động" : "Vô hiệu"}
                  </span>
                </Td>
                <Td>{formatDate(u.last_login_at)}</Td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={6} className="p-4 text-center text-muted-foreground">
                  Không có người dùng
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {showCreate && <CreateUserModal onClose={() => setShowCreate(false)} onCreated={refresh} />}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="text-left px-3 py-2 font-medium">{children}</th>;
}
function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-3 py-2">{children}</td>;
}

function CreateUserModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    email: "",
    username: "",
    password: "",
    full_name: "",
    role: "citizen",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      await apiClient.post("/users", form);
      onCreated();
      onClose();
    } catch (e) {
      if (e instanceof ApiError) setErr(e.message);
      else setErr("Lỗi");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 grid place-items-center p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-xl bg-card border border-border p-5"
      >
        <h2 className="font-semibold text-lg">Tạo người dùng</h2>
        {err && (
          <p className="mt-2 text-sm text-danger bg-danger/10 px-3 py-2 rounded-md">
            {err}
          </p>
        )}
        <div className="mt-3 space-y-3">
          <Field label="Email">
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full px-3 py-2 rounded-md border border-input bg-background"
            />
          </Field>
          <Field label="Username">
            <input
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="w-full px-3 py-2 rounded-md border border-input bg-background"
            />
          </Field>
          <Field label="Mật khẩu (tối thiểu 8)">
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="w-full px-3 py-2 rounded-md border border-input bg-background"
            />
          </Field>
          <Field label="Họ tên">
            <input
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className="w-full px-3 py-2 rounded-md border border-input bg-background"
            />
          </Field>
          <Field label="Role">
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="w-full px-3 py-2 rounded-md border border-input bg-background"
            >
              {ROLES.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </Field>
        </div>
        <div className="mt-5 flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-3 py-2 rounded-md border border-border"
          >
            Huỷ
          </button>
          <button
            onClick={submit}
            disabled={busy}
            className="px-3 py-2 rounded-md bg-primary text-primary-foreground"
          >
            {busy ? "Đang tạo…" : "Tạo"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-sm">
      <span className="font-medium">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
