"use client";

import { useEffect, useState } from "react";
import { Camera, MapPin, Navigation } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { apiClient } from "@/lib/api/client";
import { formatDate, relativeTime } from "@/lib/utils";

export default function MyTasksPage() {
  return (
    <AppShell role="taskforce">
      <MyTasks />
    </AppShell>
  );
}

const COLUMNS = [
  { key: "assigned", label: "Chưa bắt đầu" },
  { key: "in_progress", label: "Đang xử lý" },
  { key: "pending_review", label: "Chờ duyệt" },
  { key: "completed", label: "Hoàn thành" },
];

function MyTasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [active, setActive] = useState<any | null>(null);

  async function refresh() {
    const data = await apiClient.get<{ items: any[] }>("/tasks", {
      searchParams: { assigned_to: "me", page_size: 100 },
    });
    setTasks(data.items);
  }
  useEffect(() => {
    refresh();
  }, []);

  async function checkIn(task: any) {
    if (!navigator.geolocation) return alert("Trình duyệt không hỗ trợ GPS");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          await apiClient.post(`/tasks/${task.id}/check-in`, {
            lng: pos.coords.longitude,
            lat: pos.coords.latitude,
          });
          await refresh();
        } catch (e: any) {
          alert(e.message);
        }
      },
      (err) => alert("Không lấy được vị trí: " + err.message)
    );
  }

  async function uploadPhoto(task: any, role: "before" | "after") {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.capture = "environment" as any;
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("role", role);
      fd.append("image", file);
      await apiClient.postForm(`/tasks/${task.id}/photos`, fd);
      await refresh();
    };
    input.click();
  }

  async function complete(task: any) {
    const notes = prompt("Ghi chú hoàn thành:");
    if (notes === null) return;
    try {
      await apiClient.post(`/tasks/${task.id}/complete`, { notes });
      await refresh();
    } catch (e: any) {
      alert(e.message);
    }
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">Tác vụ của tôi</h1>
      <p className="text-sm text-muted-foreground">
        Kanban — kéo task qua các trạng thái khi xử lý hiện trường.
      </p>
      <div className="mt-6 grid lg:grid-cols-4 gap-4">
        {COLUMNS.map((c) => {
          const list = tasks.filter((t) => t.status === c.key);
          return (
            <div key={c.key} className="rounded-xl border border-border bg-card p-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-sm">{c.label}</h3>
                <span className="text-xs text-muted-foreground">
                  {list.length}
                </span>
              </div>
              <div className="space-y-2">
                {list.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setActive(t)}
                    className="w-full text-left p-3 rounded-lg border border-border hover:bg-accent"
                  >
                    <div className="text-xs font-mono text-muted-foreground">
                      {t.code}
                    </div>
                    <div className="font-medium text-sm">{t.title}</div>
                    <div className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                      <span
                        className="px-1.5 rounded"
                        style={{
                          background:
                            t.priority === "urgent"
                              ? "rgb(239 68 68 / 0.15)"
                              : t.priority === "high"
                              ? "rgb(249 115 22 / 0.15)"
                              : "var(--accent)",
                        }}
                      >
                        {t.priority}
                      </span>
                      {t.due_at && (
                        <span>· hạn {relativeTime(t.due_at)}</span>
                      )}
                    </div>
                  </button>
                ))}
                {list.length === 0 && (
                  <p className="text-xs text-muted-foreground text-center py-4">
                    Trống
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {active && (
        <div
          className="fixed inset-0 z-50 bg-black/50 grid place-items-center p-4 animate-fade-in"
          onClick={() => setActive(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg rounded-xl bg-card border border-border p-5 max-h-[80vh] overflow-y-auto"
          >
            <p className="text-xs font-mono text-muted-foreground">
              {active.code}
            </p>
            <h2 className="text-lg font-semibold">{active.title}</h2>
            {active.description && (
              <p className="text-sm mt-2">{active.description}</p>
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              Hạn: {formatDate(active.due_at)}
            </p>

            <div className="mt-4 grid grid-cols-2 gap-2">
              {active.before_images?.map((u: string) => (
                <img
                  key={u}
                  src={u}
                  alt="before"
                  className="rounded-md object-cover h-24"
                />
              ))}
              {active.after_images?.map((u: string) => (
                <img
                  key={u}
                  src={u}
                  alt="after"
                  className="rounded-md object-cover h-24"
                />
              ))}
            </div>

            <div className="mt-4 flex flex-col gap-2">
              {active.status === "assigned" && (
                <button
                  onClick={() => checkIn(active)}
                  className="px-3 py-2 rounded-md bg-primary text-primary-foreground inline-flex items-center justify-center gap-2"
                >
                  <MapPin className="size-4" /> Check-in tại hiện trường
                </button>
              )}
              {active.status === "in_progress" && (
                <>
                  <button
                    onClick={() => uploadPhoto(active, "before")}
                    className="px-3 py-2 rounded-md border border-border inline-flex items-center justify-center gap-2"
                  >
                    <Camera className="size-4" /> Upload ảnh BEFORE
                  </button>
                  <button
                    onClick={() => uploadPhoto(active, "after")}
                    className="px-3 py-2 rounded-md border border-border inline-flex items-center justify-center gap-2"
                  >
                    <Camera className="size-4" /> Upload ảnh AFTER
                  </button>
                  <button
                    onClick={() => complete(active)}
                    className="px-3 py-2 rounded-md bg-success text-white inline-flex items-center justify-center gap-2"
                  >
                    Hoàn thành tác vụ
                  </button>
                </>
              )}
              <button
                onClick={() => setActive(null)}
                className="px-3 py-2 rounded-md border border-border"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
