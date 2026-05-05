"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, CircleDot, Clock, Star } from "lucide-react";

import { apiClient } from "@/lib/api/client";
import { INCIDENT_LABELS, STATUS_LABELS } from "@/lib/config";
import { useAuthStore } from "@/lib/store/auth";
import { formatDate, relativeTime } from "@/lib/utils";

const TIMELINE_STEPS = [
  { key: "created", label: "Đã gửi", icon: CircleDot },
  { key: "accepted", label: "Đã duyệt", icon: CheckCircle2 },
  { key: "in_progress", label: "Đang xử lý", icon: Clock },
  { key: "resolved", label: "Hoàn thành", icon: CheckCircle2 },
];

export default function MyTicketsPage() {
  const router = useRouter();
  const isAuthed = useAuthStore((s) => s.isAuthenticated());
  useEffect(() => {
    if (!isAuthed) router.replace("/login");
  }, [isAuthed, router]);

  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<any | null>(null);
  const [timeline, setTimeline] = useState<any[]>([]);

  useEffect(() => {
    apiClient
      .get<{ items: any[] }>("/reports/me", { searchParams: { page_size: 50 } })
      .then((data) => setItems(data.items))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!active) {
      setTimeline([]);
      return;
    }
    apiClient
      .get<any[]>(`/reports/${active.id}/timeline`)
      .then(setTimeline)
      .catch(() => setTimeline([]));
  }, [active]);

  return (
    <main className="min-h-screen container py-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Về trang chủ
      </Link>
      <h1 className="mt-3 text-2xl font-bold">Báo cáo của tôi</h1>
      <p className="text-sm text-muted-foreground">
        Theo dõi tiến độ xử lý các sự cố bạn đã gửi.
      </p>

      <div className="mt-6 grid lg:grid-cols-[1fr_420px] gap-6">
        <div className="space-y-3">
          {loading && <div className="text-muted-foreground">Đang tải…</div>}
          {!loading && items.length === 0 && (
            <div className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
              Bạn chưa gửi báo cáo nào.
              <Link
                href="/report"
                className="ml-2 text-primary underline-offset-4 hover:underline"
              >
                Tạo báo cáo →
              </Link>
            </div>
          )}
          {items.map((r) => (
            <button
              key={r.id}
              onClick={() => setActive(r)}
              className={
                "w-full text-left rounded-xl border p-4 transition-colors " +
                (active?.id === r.id
                  ? "border-primary bg-accent"
                  : "border-border hover:bg-accent")
              }
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-muted-foreground">
                  {r.code}
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    background: "var(--accent)",
                  }}
                >
                  {STATUS_LABELS[r.status] ?? r.status}
                </span>
              </div>
              <div className="mt-1 font-semibold">
                {INCIDENT_LABELS[r.incident_type ?? ""] ?? r.incident_type ?? "Sự cố"}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {relativeTime(r.created_at)} · {r.severity}
              </div>
            </button>
          ))}
        </div>
        <aside className="rounded-xl border border-border p-5 sticky top-6 self-start">
          {!active && (
            <p className="text-sm text-muted-foreground">
              Chọn một báo cáo để xem tiến độ.
            </p>
          )}
          {active && (
            <>
              <div>
                <p className="text-xs font-mono text-muted-foreground">
                  {active.code}
                </p>
                <h3 className="font-semibold">
                  {INCIDENT_LABELS[active.incident_type ?? ""] ?? "Sự cố"}
                </h3>
                <p className="text-xs text-muted-foreground mt-1">
                  Ngày gửi: {formatDate(active.created_at)}
                </p>
              </div>
              {active.images?.[0] && (
                <img
                  src={active.images[0]}
                  alt="evidence"
                  className="mt-3 rounded-md max-h-48 w-full object-cover"
                />
              )}
              <div className="mt-4 space-y-3">
                {TIMELINE_STEPS.map((step, idx) => {
                  const events = timeline.filter((t) =>
                    t.action.includes(step.key)
                  );
                  const done = events.length > 0;
                  const Icon = step.icon;
                  return (
                    <div key={step.key} className="flex gap-3">
                      <div
                        className={
                          "size-7 rounded-full grid place-items-center shrink-0 " +
                          (done
                            ? "bg-success text-white"
                            : "bg-muted text-muted-foreground")
                        }
                      >
                        <Icon className="size-4" />
                      </div>
                      <div className="flex-1 pt-0.5">
                        <div className="text-sm font-medium">{step.label}</div>
                        {events.map((e, i) => (
                          <div
                            key={i}
                            className="text-xs text-muted-foreground"
                          >
                            {formatDate(e.at)}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
              {active.status === "resolved" && !active.rating && (
                <RatingForm
                  reportId={active.id}
                  onDone={() => setActive({ ...active, rating: 5 })}
                />
              )}
            </>
          )}
        </aside>
      </div>
    </main>
  );
}

function RatingForm({ reportId, onDone }: { reportId: string; onDone: () => void }) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="mt-4 pt-4 border-t border-border">
      <div className="text-sm font-medium">Đánh giá kết quả xử lý</div>
      <div className="mt-2 flex gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            onClick={() => setRating(n)}
            className={n <= rating ? "text-yellow-500" : "text-muted-foreground"}
          >
            <Star className="size-5 fill-current" />
          </button>
        ))}
      </div>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={2}
        placeholder="Nhận xét (tùy chọn)"
        className="mt-2 w-full px-3 py-2 rounded-md border border-input bg-card text-sm"
      />
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await apiClient.post(`/reports/${reportId}/rating`, {
              rating,
              comment: comment || null,
            });
            onDone();
          } finally {
            setBusy(false);
          }
        }}
        className="mt-2 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground"
      >
        Gửi đánh giá
      </button>
    </div>
  );
}
