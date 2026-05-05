"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Filter, Layers, Loader2, MapPin } from "lucide-react";

import { apiClient } from "@/lib/api/client";
import { ASSET_TYPES, INCIDENT_LABELS, STATUS_LABELS } from "@/lib/config";
import type { MapAsset, MapReport } from "@/components/map/MapLibreCanvas";

const MapLibreCanvas = dynamic(
  () => import("@/components/map/MapLibreCanvas"),
  { ssr: false, loading: () => <MapLoading /> }
);

function MapLoading() {
  return (
    <div className="grid place-items-center w-full h-full bg-muted">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <Loader2 className="size-8 animate-spin" />
        <span>Đang tải bản đồ Đà Nẵng…</span>
      </div>
    </div>
  );
}

type AssetListResponse = { items: any[]; total: number };

export default function MapPage() {
  const [bbox, setBbox] = useState<string | null>(null);
  const [filterTypes, setFilterTypes] = useState<Set<string>>(
    new Set(ASSET_TYPES.map((t) => t.value))
  );
  const [showReports, setShowReports] = useState(true);
  const [assets, setAssets] = useState<MapAsset[]>([]);
  const [reports, setReports] = useState<MapReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<MapAsset | null>(null);

  const fetchAssets = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<AssetListResponse>("/assets", {
        searchParams: {
          bbox: bbox ?? undefined,
          page_size: 200,
        },
        skipAuth: true,
      });
      const filtered = data.items.filter((a) => filterTypes.has(a.asset_type));
      setAssets(
        filtered.map((a: any) => ({
          id: a.id,
          code: a.code,
          name: a.name,
          asset_type: a.asset_type,
          status: a.status,
          lng: a.lng,
          lat: a.lat,
          area_id: a.area_id,
        }))
      );
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [bbox, filterTypes]);

  const fetchReports = useCallback(async () => {
    if (!showReports) {
      setReports([]);
      return;
    }
    try {
      const data = await apiClient.get<{ items: any[] }>("/reports", {
        searchParams: { page_size: 100 },
      });
      setReports(
        data.items.map((r: any) => ({
          id: r.id,
          code: r.code,
          status: r.status,
          severity: r.severity,
          incident_type: r.incident_type,
          lng: r.lng,
          lat: r.lat,
        }))
      );
    } catch (e) {
      // Public users may not be authenticated — silently no reports
      setReports([]);
    }
  }, [showReports]);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const summary = useMemo(() => {
    const byType: Record<string, number> = {};
    for (const a of assets) byType[a.asset_type] = (byType[a.asset_type] ?? 0) + 1;
    return byType;
  }, [assets]);

  return (
    <main className="h-screen w-screen relative overflow-hidden">
      <MapLibreCanvas
        assets={assets}
        reports={reports}
        onBboxChange={(b) => setBbox(b.join(","))}
        onClickAsset={setSelected}
      />

      {/* Top-left brand */}
      <div className="absolute top-4 left-4 glass border border-border rounded-xl px-3 py-2 flex items-center gap-2 shadow-lg">
        <Link href="/" className="font-semibold flex items-center gap-2">
          <div className="size-7 rounded-lg bg-primary text-primary-foreground grid place-items-center font-bold text-sm">
            ĐN
          </div>
          Đà Nẵng Infra
        </Link>
      </div>

      {/* Filters panel */}
      <aside className="absolute top-4 left-1/2 -translate-x-1/2 glass border border-border rounded-xl shadow-lg px-3 py-2 max-w-[90vw] hidden md:flex items-center gap-3 text-sm">
        <Filter className="size-4 text-muted-foreground" />
        {ASSET_TYPES.map((t) => (
          <label key={t.value} className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={filterTypes.has(t.value)}
              onChange={(e) => {
                setFilterTypes((s) => {
                  const next = new Set(s);
                  if (e.target.checked) next.add(t.value);
                  else next.delete(t.value);
                  return next;
                });
              }}
              className="accent-primary"
            />
            <span
              className="size-2.5 rounded-full"
              style={{ background: t.color }}
            />
            {t.label}
            <span className="text-muted-foreground text-xs">
              ({summary[t.value] ?? 0})
            </span>
          </label>
        ))}
        <span className="mx-1 h-4 w-px bg-border" />
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={showReports}
            onChange={(e) => setShowReports(e.target.checked)}
            className="accent-primary"
          />
          Sự cố
        </label>
      </aside>

      {/* Loading badge */}
      {loading && (
        <div className="absolute top-4 right-20 glass border border-border rounded-md px-3 py-1.5 text-xs flex items-center gap-2 shadow-md">
          <Loader2 className="size-3 animate-spin" />
          Đang tải dữ liệu…
        </div>
      )}

      {/* Selected asset popup card */}
      {selected && (
        <div className="absolute bottom-4 left-4 max-w-md glass border border-border rounded-xl shadow-xl p-4 animate-slide-up">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs text-muted-foreground font-mono">
                {selected.code}
              </p>
              <h3 className="font-semibold flex items-center gap-2">
                <MapPin className="size-4 text-primary" />
                {selected.name}
              </h3>
              <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                <span className="px-2 py-0.5 rounded-full bg-accent">
                  {selected.asset_type}
                </span>
                <span
                  className="px-2 py-0.5 rounded-full"
                  style={{
                    background:
                      selected.status === "active"
                        ? "rgb(34 197 94 / 0.15)"
                        : selected.status === "damaged"
                        ? "rgb(239 68 68 / 0.15)"
                        : "rgb(234 179 8 / 0.15)",
                    color:
                      selected.status === "active"
                        ? "#16a34a"
                        : selected.status === "damaged"
                        ? "#ef4444"
                        : "#ca8a04",
                  }}
                >
                  {STATUS_LABELS[selected.status] ?? selected.status}
                </span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {selected.lat.toFixed(5)}, {selected.lng.toFixed(5)}
              </p>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div className="mt-3 flex gap-2">
            <Link
              href={`/report?lng=${selected.lng}&lat=${selected.lat}&asset=${selected.id}`}
              className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:opacity-90"
            >
              Báo cáo sự cố tại đây
            </Link>
          </div>
        </div>
      )}

      <div className="absolute bottom-4 right-4 glass border border-border rounded-md px-3 py-1.5 text-xs flex items-center gap-1 shadow-md">
        <Layers className="size-3" /> {assets.length} tài sản · {reports.length} sự cố
      </div>
    </main>
  );
}
