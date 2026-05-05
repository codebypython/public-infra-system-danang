"use client";

import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { apiClient } from "@/lib/api/client";
import { config } from "@/lib/config";
import { useAuthStore } from "@/lib/store/auth";
import { relativeTime } from "@/lib/utils";

type Notif = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  is_read: boolean;
  created_at: string;
};

export function NotificationBell() {
  const token = useAuthStore((s) => s.accessToken);
  const [items, setItems] = useState<Notif[]>([]);
  const [open, setOpen] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;
    apiClient
      .get<{ items: Notif[] }>("/notifications", { searchParams: { page_size: 20 } })
      .then((r) => setItems(r.items))
      .catch(() => {});

    const wsUrl = `${config.wsUrl}/api/v1/notifications/ws?token=${token}`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.event === "notification.created" && msg.data) {
          setItems((arr) => [
            {
              id: msg.data.id,
              type: msg.data.type,
              title: msg.data.title,
              body: msg.data.body,
              is_read: false,
              created_at: new Date().toISOString(),
            },
            ...arr,
          ]);
        }
      } catch {
        /* ignore */
      }
    };
    ws.onerror = () => {};
    wsRef.current = ws;

    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 30_000);

    return () => {
      clearInterval(ping);
      ws.close();
    };
  }, [token]);

  const unread = items.filter((n) => !n.is_read).length;

  async function markAll() {
    await apiClient.post("/notifications/mark-all-read");
    setItems((arr) => arr.map((n) => ({ ...n, is_read: true })));
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative size-9 rounded-md border border-border hover:bg-accent grid place-items-center"
        aria-label="Notifications"
      >
        <Bell className="size-4" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 size-4 rounded-full bg-danger text-white text-[10px] grid place-items-center font-bold">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 max-h-96 overflow-y-auto rounded-xl border border-border bg-card shadow-xl z-50 scrollbar-thin">
          <div className="p-3 border-b border-border flex items-center justify-between">
            <span className="font-semibold">Thông báo</span>
            {unread > 0 && (
              <button
                onClick={markAll}
                className="text-xs text-primary hover:underline"
              >
                Đánh dấu tất cả đã đọc
              </button>
            )}
          </div>
          {items.length === 0 && (
            <p className="p-4 text-sm text-muted-foreground text-center">
              Chưa có thông báo.
            </p>
          )}
          {items.map((n) => (
            <div
              key={n.id}
              className={
                "p-3 border-b border-border last:border-0 " +
                (n.is_read ? "" : "bg-primary/5")
              }
            >
              <p className="text-sm font-medium">{n.title}</p>
              {n.body && (
                <p className="text-xs text-muted-foreground">{n.body}</p>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                {relativeTime(n.created_at)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
