import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "BrandVideo",
  description: "品牌合作视频脚本编辑系统"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

