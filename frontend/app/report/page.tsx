"use client";

import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Bot, Camera, Loader2, MapPin, Send } from "lucide-react";

import { ApiError, apiClient } from "@/lib/api/client";
import { INCIDENT_LABELS } from "@/lib/config";
import { useAuthStore } from "@/lib/store/auth";

const MapLibreCanvas = dynamic(() => import("@/components/map/MapLibreCanvas"), {
  ssr: false,
});

const SEVERITIES = [
  { value: "low", label: "Thấp" },
  { value: "medium", label: "Trung bình" },
  { value: "high", label: "Cao" },
  { value: "urgent", label: "Khẩn cấp" },
];

export default function ReportPage() {
  const router = useRouter();
  const params = useSearchParams();
  const isAuthed = useAuthStore((s) => s.isAuthenticated());

  useEffect(() => {
    if (!isAuthed) router.replace("/login");
  }, [isAuthed, router]);

  const [point, setPoint] = useState<{ lng: number; lat: number } | null>(() => {
    const lng = params.get("lng");
    const lat = params.get("lat");
    return lng && lat ? { lng: parseFloat(lng), lat: parseFloat(lat) } : null;
  });
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [aiResult, setAiResult] = useState<any>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [incidentType, setIncidentType] = useState<string>("");
  const [severity, setSeverity] = useState("medium");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<any>(null);

  const tempMarker = useMemo<any[]>(
    () =>
      point
        ? [
            {
              id: "draft",
              code: "DRAFT",
              status: "pending",
              severity,
              incident_type: incidentType || null,
              lng: point.lng,
              lat: point.lat,
            },
          ]
        : [],
    [point, severity, incidentType]
  );

  async function onImage(file: File) {
    setImage(file);
    setPreview(URL.createObjectURL(file));
    setAiLoading(true);
    setAiResult(null);
    try {
      // Direct upload to AI service via backend proxy
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}`.replace(
          /\/$/,
          ""
        ) + "/health"
      );
      // Call AI service directly (CORS allowed by backend proxy in real prod via Next.js rewrite)
      const aiRes = await fetch(
        process.env.NEXT_PUBLIC_AI_URL ?? "http://localhost:8001/classify",
        { method: "POST", body: fd }
      );
      if (aiRes.ok) {
        const data = await aiRes.json();
        setAiResult(data);
        if (data.primary_class && (!incidentType || data.confidence >= 0.7)) {
          setIncidentType(data.primary_class);
        }
        if (data.exif_gps && !point) {
          setPoint({ lng: data.exif_gps.lng, lat: data.exif_gps.lat });
        }
      }
    } catch (e) {
      console.warn("AI not reachable", e);
    } finally {
      setAiLoading(false);
    }
  }

  async function submit() {
    if (!point) {
      setError("Vui lòng chọn vị trí trên bản đồ");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("lng", String(point.lng));
      fd.append("lat", String(point.lat));
      if (incidentType) fd.append("incident_type", incidentType);
      fd.append("severity", severity);
      if (description) fd.append("description", description);
      if (image) fd.append("image", image);
      const data = await apiClient.postForm<any>("/reports", fd);
      setSuccess(data);
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Không thể gửi báo cáo");
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <main className="min-h-screen grid place-items-center p-6">
        <div className="max-w-md w-full bg-card border border-border rounded-xl p-6 text-center shadow-lg">
          <div className="size-14 rounded-full bg-success/20 grid place-items-center mx-auto">
            <Send className="size-7 text-success" />
          </div>
          <h1 className="mt-4 text-xl font-bold">Đã gửi báo cáo</h1>
          <p className="mt-1 text-muted-foreground">
            Mã báo cáo: <span className="font-mono">{success.code}</span>
          </p>
          <div className="mt-5 flex gap-2 justify-center">
            <button
              className="px-4 py-2 rounded-md bg-primary text-primary-foreground"
              onClick={() => router.push("/my-tickets")}
            >
              Theo dõi tiến độ
            </button>
            <button
              className="px-4 py-2 rounded-md border border-border"
              onClick={() => {
                setSuccess(null);
                setImage(null);
                setPreview(null);
                setAiResult(null);
                setDescription("");
              }}
            >
              Báo cáo khác
            </button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen grid lg:grid-cols-[1fr_420px]">
      <section className="relative h-[50vh] lg:h-screen">
        <MapLibreCanvas
          onClickMap={(lng, lat) => setPoint({ lng, lat })}
          reports={tempMarker}
        />
        <div className="absolute top-4 left-4 glass border border-border rounded-md px-3 py-1.5 text-sm">
          <MapPin className="size-3.5 inline mr-1" />
          {point
            ? `${point.lat.toFixed(5)}, ${point.lng.toFixed(5)}`
            : "Click vào vị trí trên bản đồ"}
        </div>
      </section>

      <aside className="border-l border-border p-6 overflow-y-auto bg-card">
        <h1 className="text-xl font-bold">Báo cáo sự cố</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tải ảnh hiện trường, AI sẽ tự gợi ý loại sự cố trong vài giây.
        </p>

        {error && (
          <div className="mt-4 px-3 py-2 rounded-md text-sm bg-danger/10 text-danger border border-danger/30">
            {error}
          </div>
        )}

        <div className="mt-5 space-y-4">
          <div>
            <label className="block text-sm font-medium">Ảnh hiện trường</label>
            <label className="mt-1 flex flex-col items-center justify-center gap-2 px-4 py-6 border-2 border-dashed border-border rounded-lg cursor-pointer hover:bg-accent">
              {preview ? (
                <img
                  src={preview}
                  alt="preview"
                  className="max-h-40 rounded-md object-cover"
                />
              ) : (
                <>
                  <Camera className="size-8 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    Bấm để chụp / tải ảnh
                  </span>
                </>
              )}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="environment"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onImage(f);
                }}
                className="sr-only"
              />
            </label>
            {aiLoading && (
              <p className="mt-2 text-xs text-muted-foreground flex items-center gap-1.5">
                <Loader2 className="size-3 animate-spin" />
                AI đang phân tích…
              </p>
            )}
            {aiResult && (
              <div className="mt-2 px-3 py-2 rounded-md bg-primary/10 border border-primary/20 text-sm flex items-center gap-2">
                <Bot className="size-4 text-primary" />
                AI: <strong>{INCIDENT_LABELS[aiResult.primary_class] ?? aiResult.primary_class}</strong>
                <span className="text-xs text-muted-foreground">
                  ({Math.round((aiResult.confidence ?? 0) * 100)}%)
                </span>
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium">Loại sự cố</label>
            <select
              value={incidentType}
              onChange={(e) => setIncidentType(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-md border border-input bg-card"
            >
              <option value="">— Chọn —</option>
              {Object.entries(INCIDENT_LABELS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium">Mức độ</label>
            <div className="mt-1 grid grid-cols-4 gap-2">
              {SEVERITIES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => setSeverity(s.value)}
                  className={
                    "px-2 py-1.5 rounded-md text-sm border " +
                    (severity === s.value
                      ? "bg-primary text-primary-foreground border-primary"
                      : "border-border hover:bg-accent")
                  }
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium">Mô tả</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              maxLength={2000}
              className="mt-1 w-full px-3 py-2 rounded-md border border-input bg-card"
              placeholder="Mô tả chi tiết hiện trường, ảnh hưởng…"
            />
          </div>

          <button
            onClick={submit}
            disabled={submitting || !point}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground font-medium disabled:opacity-60"
          >
            <Send className="size-4" />
            {submitting ? "Đang gửi…" : "Gửi báo cáo"}
          </button>
        </div>
      </aside>
    </main>
  );
}
