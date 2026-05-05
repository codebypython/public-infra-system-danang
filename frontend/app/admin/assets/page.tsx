"use client";

import { useEffect, useState } from "react";
import { Trash2, Upload } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { apiClient } from "@/lib/api/client";
import { ASSET_TYPE_MAP, ASSET_TYPES, STATUS_LABELS } from "@/lib/config";
import { formatDate } from "@/lib/utils";

export default function AdminAssetsPage() {
  return (
    <AppShell role="admin">
      <AssetsList />
    </AppShell>
  );
}

function AssetsList() {
  const [items, setItems] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [importing, setImporting] = useState(false);

  async function refresh() {
    const data = await apiClient.get<any>("/assets", {
      searchParams: {
        q: q || null,
        type: type || null,
        status: status || null,
        page_size: 200,
      },
    });
    setItems(data.items);
  }
  useEffect(() => {
    refresh();
  }, [q, type, status]);

  async function remove(id: string) {
    if (!confirm("Xoá tài sản này?")) return;
    await apiClient.delete(`/assets/${id}`);
    refresh();
  }

  async function bulkImport(file: File) {
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const result = await apiClient.postForm<any>("/assets/bulk-import", fd);
      alert(`Import: ${result.success} thành công, ${result.errors.length} lỗi`);
      refresh();
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Quản lý tài sản hạ tầng</h1>
        <label className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-sm cursor-pointer">
          <Upload className="size-4" />
          {importing ? "Đang import…" : "Import GeoJSON"}
          <input
            type="file"
            accept="application/geo+json,application/json"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) bulkImport(f);
            }}
          />
        </label>
      </div>
      <div className="flex gap-3 mb-4">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Tìm theo tên / mã…"
          className="px-3 py-2 rounded-md border border-input bg-card flex-1"
        />
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="px-3 py-2 rounded-md border border-input bg-card"
        >
          <option value="">Tất cả loại</option>
          {ASSET_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="px-3 py-2 rounded-md border border-input bg-card"
        >
          <option value="">Tất cả trạng thái</option>
          {["active", "damaged", "maintenance", "retired"].map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s] ?? s}
            </option>
          ))}
        </select>
      </div>
      <div className="rounded-xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-accent">
            <tr>
              <Th>Mã</Th>
              <Th>Tên</Th>
              <Th>Loại</Th>
              <Th>Trạng thái</Th>
              <Th>Tạo lúc</Th>
              <Th>QR</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id} className="border-t border-border">
                <Td>
                  <span className="font-mono text-xs">{a.code}</span>
                </Td>
                <Td>{a.name}</Td>
                <Td>
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="size-2.5 rounded-full"
                      style={{ background: ASSET_TYPE_MAP[a.asset_type]?.color }}
                    />
                    {ASSET_TYPE_MAP[a.asset_type]?.label ?? a.asset_type}
                  </span>
                </Td>
                <Td>
                  <span className="px-2 py-0.5 rounded-full bg-accent text-xs">
                    {STATUS_LABELS[a.status] ?? a.status}
                  </span>
                </Td>
                <Td>{formatDate(a.created_at)}</Td>
                <Td>
                  {a.qr_code_url && (
                    <a
                      href={a.qr_code_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary text-xs underline-offset-4 hover:underline"
                    >
                      QR
                    </a>
                  )}
                </Td>
                <Td>
                  <button
                    onClick={() => remove(a.id)}
                    className="text-danger hover:opacity-70"
                    title="Xoá"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="text-left px-3 py-2 font-medium">{children}</th>;
}
function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-3 py-2">{children}</td>;
}
