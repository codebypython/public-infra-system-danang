"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, UserCheck, X } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ApiError, apiClient } from "@/lib/api/client";
import { INCIDENT_LABELS, SEVERITY_COLORS } from "@/lib/config";
import { formatDate, relativeTime } from "@/lib/utils";

const MapLibreCanvas = dynamic(() => import("@/components/map/MapLibreCanvas"), {
  ssr: false,
});

export default function CommandCenterPage() {
  return (
    <AppShell role="operator">
      <CommandCenter />
    </AppShell>
  );
}

function CommandCenter() {
  const [pending, setPending] = useState<any[]>([]);
  const [selected, setSelected] = useState<any | null>(null);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<string>("pending");

  async function refresh() {
    const data = await apiClient.get<{ items: any[] }>("/reports", {
      searchParams: { status: filter, page_size: 100 },
    });
    setPending(data.items);
  }

  useEffect(() => {
    refresh();
  }, [filter]);

  useEffect(() => {
    if (!selected) {
      setSuggestions([]);
      return;
    }
    apiClient
      .get<any[]>(`/reports/${selected.id}/timeline`)
      .catch(() => []);
  }, [selected]);

  async function accept(report: any) {
    setBusy(true);
    try {
      await apiClient.post(`/reports/${report.id}/accept`);
      await refresh();
      setSelected(null);
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
    }
  }

  async function reject(report: any) {
    const reason = prompt("Lý do từ chối?");
    if (!reason) return;
    setBusy(true);
    try {
      await apiClient.post(`/reports/${report.id}/reject`, { reason });
      await refresh();
      setSelected(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid lg:grid-cols-[400px_1fr_360px] h-[calc(100vh-3.5rem)]">
      <aside className="border-r border-border overflow-y-auto">
        <div className="p-3 border-b border-border bg-card sticky top-0">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full px-2 py-1.5 text-sm rounded-md border border-input bg-card"
          >
            <option value="pending">Chờ duyệt</option>
            <option value="accepted">Đã duyệt</option>
            <option value="in_progress">Đang xử lý</option>
            <option value="pending_review">Chờ xác nhận</option>
            <option value="resolved">Đã giải quyết</option>
          </select>
          <p className="mt-2 text-xs text-muted-foreground">
            {pending.length} báo cáo
          </p>
        </div>
        <div className="divide-y divide-border">
          {pending.map((r) => {
            const overdueSoon =
              r.sla_due_at &&
              new Date(r.sla_due_at).getTime() - Date.now() < 1000 * 60 * 60 * 2;
            return (
              <button
                key={r.id}
                onClick={() => setSelected(r)}
                className={
                  "w-full p-3 text-left hover:bg-accent " +
                  (selected?.id === r.id ? "bg-accent" : "")
                }
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-muted-foreground">
                    {r.code}
                  </span>
                  <span
                    className="text-xs px-2 rounded-full"
                    style={{
                      background:
                        SEVERITY_COLORS[
                          r.severity as keyof typeof SEVERITY_COLORS
                        ] + "30",
                      color:
                        SEVERITY_COLORS[
                          r.severity as keyof typeof SEVERITY_COLORS
                        ],
                    }}
                  >
                    {r.severity}
                  </span>
                </div>
                <div className="mt-1 text-sm font-medium">
                  {INCIDENT_LABELS[r.incident_type ?? ""] ?? "Sự cố"}
                </div>
                <div className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                  <span>{relativeTime(r.created_at)}</span>
                  {overdueSoon && (
                    <span className="text-danger flex items-center gap-1">
                      <AlertTriangle className="size-3" />
                      sắp quá hạn
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      <section className="relative">
        <MapLibreCanvas
          reports={pending.map((r) => ({
            id: r.id,
            code: r.code,
            status: r.status,
            severity: r.severity,
            incident_type: r.incident_type,
            lng: r.lng,
            lat: r.lat,
          }))}
          onClickReport={(r) => {
            const found = pending.find((p) => p.id === r.id);
            if (found) setSelected(found);
          }}
        />
      </section>

      <aside className="border-l border-border bg-card overflow-y-auto p-5">
        {!selected && (
          <p className="text-sm text-muted-foreground">
            Chọn một báo cáo từ danh sách bên trái để xem chi tiết.
          </p>
        )}
        {selected && (
          <>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-mono text-muted-foreground">
                  {selected.code}
                </p>
                <h2 className="text-lg font-semibold">
                  {INCIDENT_LABELS[selected.incident_type ?? ""] ??
                    selected.incident_type}
                </h2>
                <p className="text-xs text-muted-foreground mt-1">
                  {formatDate(selected.created_at)}
                </p>
              </div>
            </div>
            {selected.images?.[0] && (
              <div className="mt-3">
                <img
                  src={selected.images[0]}
                  alt="evidence"
                  className="rounded-md w-full max-h-56 object-cover"
                />
                {selected.ai_class && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    AI Verification:{" "}
                    <strong>{INCIDENT_LABELS[selected.ai_class] ?? selected.ai_class}</strong>
                    {" "}({Math.round((selected.ai_confidence ?? 0) * 100)}%)
                  </div>
                )}
              </div>
            )}
            {selected.description && (
              <p className="mt-3 text-sm">{selected.description}</p>
            )}
            <div className="mt-3 text-xs text-muted-foreground">
              SLA: {formatDate(selected.sla_due_at)}
            </div>
            {selected.status === "pending" && (
              <div className="mt-5 grid grid-cols-2 gap-2">
                <button
                  onClick={() => accept(selected)}
                  disabled={busy}
                  className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-success text-white"
                >
                  {busy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <UserCheck className="size-4" />
                  )}
                  Điều phối
                </button>
                <button
                  onClick={() => reject(selected)}
                  disabled={busy}
                  className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md border border-border"
                >
                  <X className="size-4" /> Từ chối
                </button>
              </div>
            )}
            {selected.status === "pending_review" && (
              <button
                onClick={async () => {
                  // Approve completion via task endpoint requires task_id; use timeline lookup omitted
                  alert("Mở chi tiết task để duyệt hoàn thành.");
                }}
                className="mt-5 w-full px-3 py-2 rounded-md bg-primary text-primary-foreground"
              >
                <CheckCircle2 className="size-4 inline mr-1" /> Duyệt hoàn thành
              </button>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
