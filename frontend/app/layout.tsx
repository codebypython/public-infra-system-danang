import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Providers } from "@/components/providers";

import "./globals.css";

const inter = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Đà Nẵng Public Infrastructure System",
    template: "%s · Đà Nẵng Infra",
  },
  description:
    "Hệ thống quản lý hạ tầng công cộng thành phố Đà Nẵng — bản đồ 3D, báo cáo sự cố tích hợp AI, command center điều phối thông minh.",
  applicationName: "Đà Nẵng Infra",
  keywords: [
    "Đà Nẵng",
    "smart city",
    "GIS",
    "infrastructure",
    "incident reporting",
    "YOLOv8",
  ],
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0e14" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <body className={`${inter.variable} antialiased min-h-screen`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
