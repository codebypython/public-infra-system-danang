"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { apiClient } from "@/lib/api/client";
import { config } from "@/lib/config";
import { useAuthStore } from "@/lib/store/auth";

export default function AdminAnalyticsPage() {
  return (
    <AppShell role="admin">
      <Analytics />
    </AppShell>
  );
}

function Analytics() {
  const [predict, setPredict] = useState<any[]>([]);
  const [period, setPeriod] = useState("month");
  const [kpi, setKpi] = useState<any>(null);
  const token = useAuthStore((s) => s.accessToken);

  useEffect(() => {
    apiClient.get<any[]>("/analytics/predictive-maintenance").then(setPredict);
  }, []);

  useEffect(() => {
    apiClient.get<any>("/analytics/kpi", { searchParams: { period } }).then(setKpi);
  }, [period]);

  const exportUrl = (dataset: string) =>
    `${config.apiUrl}/api/v1/analytics/export.xlsx?dataset=${dataset}`;

  async function downloadExport(dataset: string) {
    const res = await fetch(exportUrl(dataset), {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      alert("Không thể export");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${dataset}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Phân tích & BI</h1>

      <section className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">KPI</h2>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="px-2 py-1 text-sm rounded-md border border-input bg-background"
          >
            <option value="week">Tuần</option>
            <option value="month">Tháng</option>
            <option value="quarter">Quý</option>
            <option value="year">Năm</option>
          </select>
        </div>
        {kpi && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Stat label="Tổng báo cáo" value={kpi.total_reports} />
            <Stat label="Đã giải quyết" value={kpi.resolved} />
            <Stat label="Tỉ lệ giải quyết" value={`${kpi.resolution_rate}%`} />
            <Stat label="Tuân thủ SLA" value={`${kpi.sla_compliance_pct}%`} />
            <Stat label="TB giải quyết (giờ)" value={kpi.avg_resolve_hours} />
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="font-semibold mb-3">Predictive maintenance — top 20 risk</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-accent">
              <tr>
                <Th>Mã</Th>
                <Th>Tên</Th>
                <Th>Loại</Th>
                <Th>Ngày từ bảo trì</Th>
                <Th>Số sự cố 180 ngày</Th>
                <Th>Risk score</Th>
              </tr>
            </thead>
            <tbody>
              {predict.map((p) => (
                <tr key={p.id} className="border-t border-border">
                  <Td>
                    <span className="font-mono text-xs">{p.code}</span>
                  </Td>
                  <Td>{p.name}</Td>
                  <Td>{p.asset_type}</Td>
                  <Td>{p.since_maintenance_days}</Td>
                  <Td>{p.recent_reports}</Td>
                  <Td>
                    <span
                      className="px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{
                        background:
                          p.risk_score > 5
                            ? "rgb(239 68 68 / 0.2)"
                            : p.risk_score > 2
                            ? "rgb(234 179 8 / 0.2)"
                            : "rgb(34 197 94 / 0.2)",
                        color:
                          p.risk_score > 5
                            ? "#ef4444"
                            : p.risk_score > 2
                            ? "#ca8a04"
                            : "#16a34a",
                      }}
                    >
                      {p.risk_score}
                    </span>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="font-semibold mb-3">Export dữ liệu</h2>
        <div className="flex flex-wrap gap-2">
          {["reports", "tasks", "assets", "maintenance"].map((d) => (
            <button
              key={d}
              onClick={() => downloadExport(d)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border hover:bg-accent text-sm"
            >
              <Download className="size-4" />
              {d}.xlsx
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-accent p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-bold">{value}</div>
    </div>
  );
}
function Th({ children }: { children: React.ReactNode }) {
  return <th className="text-left px-3 py-2 font-medium">{children}</th>;
}
function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-3 py-2">{children}</td>;
}
