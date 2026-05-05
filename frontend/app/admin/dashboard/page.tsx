"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AppShell } from "@/components/AppShell";
import { apiClient } from "@/lib/api/client";
import { ASSET_TYPE_MAP, INCIDENT_LABELS } from "@/lib/config";

export default function AdminDashboard() {
  return (
    <AppShell role="admin">
      <Dashboard />
    </AppShell>
  );
}

function Dashboard() {
  const [assetStats, setAssetStats] = useState<any>(null);
  const [reportStats, setReportStats] = useState<any>(null);
  const [kpi, setKpi] = useState<any>(null);
  const [trend, setTrend] = useState<any[]>([]);

  useEffect(() => {
    apiClient.get("/assets/stats").then(setAssetStats);
    apiClient.get("/reports/stats").then(setReportStats);
    apiClient.get("/analytics/kpi", { searchParams: { period: "month" } }).then(setKpi);
    apiClient.get("/analytics/trend", { searchParams: { days: 30 } }).then(setTrend);
  }, []);

  const assetByType = assetStats
    ? Object.entries(assetStats.by_type).map(([k, v]) => ({
        name: ASSET_TYPE_MAP[k]?.label ?? k,
        value: v,
        color: ASSET_TYPE_MAP[k]?.color ?? "#94a3b8",
      }))
    : [];

  const reportByType = reportStats
    ? Object.entries(reportStats.by_type).map(([k, v]) => ({
        name: INCIDENT_LABELS[k] ?? k,
        value: v as number,
      }))
    : [];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Tổng quan hệ thống</h1>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat
          label="Tài sản hạ tầng"
          value={assetStats?.total ?? "—"}
          sub={`${Object.keys(assetStats?.by_area ?? {}).length} quận/huyện`}
        />
        <Stat
          label="Báo cáo sự cố (30 ngày)"
          value={kpi?.total_reports ?? "—"}
          sub={`${kpi?.resolution_rate ?? 0}% giải quyết`}
        />
        <Stat
          label="Đã giải quyết"
          value={kpi?.resolved ?? "—"}
          sub={`TB ${kpi?.avg_resolve_hours ?? 0}h`}
        />
        <Stat
          label="SLA Compliance"
          value={`${kpi?.sla_compliance_pct ?? 0}%`}
          sub="Tháng hiện tại"
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title="Phân bổ tài sản theo loại">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={assetByType}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={2}
                  label={({ name, percent }) =>
                    `${name} ${(percent * 100).toFixed(0)}%`
                  }
                >
                  {assetByType.map((d) => (
                    <Cell key={d.name} fill={d.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Sự cố theo loại">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={reportByType}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" fill="var(--primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <Panel title="Số sự cố theo ngày (30 ngày gần nhất)">
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" tick={{ fontSize: 10 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="count"
                stroke="var(--primary)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="font-semibold text-sm mb-3">{title}</h3>
      {children}
    </div>
  );
}
