export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  wsUrl: process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000",
  mapStyle:
    process.env.NEXT_PUBLIC_MAP_STYLE ?? "https://demotiles.maplibre.org/style.json",
  maptilerKey: process.env.NEXT_PUBLIC_MAPTILER_KEY,
  defaultCenter: {
    lng: parseFloat(process.env.NEXT_PUBLIC_MAP_CENTER_LNG ?? "108.2022"),
    lat: parseFloat(process.env.NEXT_PUBLIC_MAP_CENTER_LAT ?? "16.0544"),
  },
  defaultZoom: parseFloat(process.env.NEXT_PUBLIC_MAP_DEFAULT_ZOOM ?? "12"),
} as const;

export const ASSET_TYPES = [
  { value: "bench", label: "Ghế đá", color: "#8b5a3c" },
  { value: "trash_can", label: "Thùng rác", color: "#475569" },
  { value: "lamp", label: "Cột đèn", color: "#facc15" },
  { value: "toilet", label: "Nhà vệ sinh", color: "#06b6d4" },
  { value: "tree", label: "Cây xanh", color: "#16a34a" },
  { value: "sign", label: "Biển báo", color: "#9333ea" },
  { value: "ev_charging", label: "Trạm sạc", color: "#22d3ee" },
  { value: "smart_bin", label: "Thùng rác thông minh", color: "#7c3aed" },
] as const;

export const ASSET_TYPE_MAP = Object.fromEntries(
  ASSET_TYPES.map((t) => [t.value, t])
) as Record<string, (typeof ASSET_TYPES)[number]>;

export const SEVERITY_COLORS = {
  low: "#22c55e",
  medium: "#eab308",
  high: "#f97316",
  urgent: "#ef4444",
} as const;

export const STATUS_COLORS: Record<string, string> = {
  pending: "#94a3b8",
  accepted: "#3b82f6",
  in_progress: "#eab308",
  pending_review: "#a855f7",
  resolved: "#22c55e",
  rejected: "#94a3b8",
  reopened: "#f97316",
};

export const STATUS_LABELS: Record<string, string> = {
  pending: "Chờ duyệt",
  accepted: "Đã duyệt",
  rejected: "Từ chối",
  in_progress: "Đang xử lý",
  pending_review: "Chờ xác nhận",
  resolved: "Đã giải quyết",
  reopened: "Mở lại",
};

export const INCIDENT_LABELS: Record<string, string> = {
  littering: "Xả rác",
  pothole: "Ổ gà",
  broken_lamp: "Đèn hỏng",
  vandalism: "Phá hoại",
  flooding: "Ngập nước",
  crowd: "Tụ tập đông",
  fallen_tree: "Cây đổ",
};
