import Link from "next/link";
import { ArrowRight, Bot, Camera, Map as MapIcon, Shield } from "lucide-react";

export default function Home() {
  return (
    <main className="min-h-screen">
      <header className="border-b border-border">
        <div className="container flex items-center justify-between py-4">
          <div className="flex items-center gap-2">
            <div className="size-9 rounded-xl bg-primary text-primary-foreground grid place-items-center font-bold">
              ĐN
            </div>
            <div>
              <p className="font-semibold leading-tight">
                Đà Nẵng Smart Infrastructure
              </p>
              <p className="text-xs text-muted-foreground">
                Public Infrastructure Operations Platform
              </p>
            </div>
          </div>
          <nav className="flex items-center gap-3 text-sm">
            <Link
              href="/map"
              className="px-3 py-2 rounded-md hover:bg-accent"
            >
              Bản đồ công cộng
            </Link>
            <Link
              href="/login"
              className="px-3 py-2 rounded-md bg-primary text-primary-foreground"
            >
              Đăng nhập
            </Link>
          </nav>
        </div>
      </header>

      <section className="container py-16">
        <div className="grid md:grid-cols-2 gap-10 items-center">
          <div>
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent text-xs font-medium">
              <span className="size-1.5 rounded-full bg-success" /> Production-grade
            </span>
            <h1 className="mt-4 text-4xl md:text-5xl font-bold tracking-tight">
              Quản lý hạ tầng công cộng
              <br />
              <span className="text-primary">thành phố Đà Nẵng</span>
            </h1>
            <p className="mt-4 text-lg text-muted-foreground max-w-xl">
              Một nền tảng tích hợp 3D GIS, AI YOLOv8, và command center điều phối
              cho 8 quận/huyện — từ Hải Châu, Sơn Trà đến Hòa Vang.
            </p>
            <div className="mt-8 flex gap-3">
              <Link
                href="/map"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:opacity-90"
              >
                Khám phá bản đồ <ArrowRight className="size-4" />
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-lg border border-border hover:bg-accent"
              >
                Đăng nhập hệ thống
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FeatureCard
              icon={<MapIcon className="size-6 text-primary" />}
              title="3D GIS Smart Navigation"
              desc="MapLibre 3D, cluster, popup, lớp cảnh báo (thi công, ngập, AQI)."
            />
            <FeatureCard
              icon={<Bot className="size-6 text-primary" />}
              title="AI Reporting"
              desc="YOLOv8 phân loại sự cố trong &lt;3s, duplicate detection, EXIF GPS."
            />
            <FeatureCard
              icon={<Shield className="size-6 text-primary" />}
              title="Command Center"
              desc="Điều phối thông minh theo proximity + load + SLA matrix."
            />
            <FeatureCard
              icon={<Camera className="size-6 text-primary" />}
              title="Camera AI Surveillance"
              desc="RTSP/HLS analysis, debounce, auto-create ticket, blur faces."
            />
          </div>
        </div>
      </section>

      <footer className="border-t border-border mt-16 py-8">
        <div className="container text-sm text-muted-foreground">
          © 2026 — Đà Nẵng Smart City. Internal pilot project.
        </div>
      </footer>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="rounded-xl border border-border p-5 bg-card hover:shadow-lg transition-shadow">
      <div className="size-10 rounded-lg bg-accent grid place-items-center mb-3">
        {icon}
      </div>
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{desc}</p>
    </div>
  );
}
