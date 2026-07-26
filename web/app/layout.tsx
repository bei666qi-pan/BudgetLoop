import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import AppShell from "@/components/AppShell";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-inter", display: "swap" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-jetbrains-mono", display: "swap" });

export const metadata: Metadata = {
  title: "BudgetLoop — 预算感知编码智能体",
  description: "在明确的 Token、时间、调用与费用预算内，规划、执行、验证并修正代码任务。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className={`${inter.variable} ${jetbrainsMono.variable} min-h-screen font-sans`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
