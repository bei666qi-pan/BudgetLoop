"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Plus, Settings2, UsersRound, Wifi, WifiOff } from "lucide-react";
import { BudgetLoopBrandMark } from "@/components/brand/BudgetLoopBrandMark";
import { checkHealth } from "@/lib/api";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    const ping = async () => {
      const ok = await checkHealth();
      if (active) setApiOnline(ok);
    };
    void ping();
    const timer = window.setInterval(ping, 15_000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const workspaceActive = pathname === "/" || pathname.startsWith("/runs/");
  const newActive = pathname.startsWith("/new");
  const containersActive = pathname.startsWith("/containers");
  const settingsActive = pathname.startsWith("/settings");
  const containerCreate = pathname === "/containers/new";
  const containerDetail = !containerCreate && /^\/containers\/[^/]+$/.test(pathname);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-border bg-white/80 backdrop-blur-2xl">
        <div className="mx-auto flex h-[72px] max-w-[1536px] items-center gap-3 px-4 sm:gap-6 sm:px-8">
          <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="BudgetLoop 首页">
            <BudgetLoopBrandMark className="h-9 w-9 shrink-0 text-accent" />
            <span className="text-lg font-semibold tracking-[-0.035em]">BudgetLoop</span>
          </Link>
          <nav aria-label="主要导航" className="hidden h-full items-center gap-1 sm:ml-4 sm:flex">
            <Link href="/" aria-current={workspaceActive ? "page" : undefined} className={`relative flex h-full items-center px-3 text-sm font-semibold transition-colors ${workspaceActive ? "text-accent" : "text-muted-foreground hover:text-foreground"}`}>
              开始
              {workspaceActive ? <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-accent" /> : null}
            </Link>
            <Link href="/containers" aria-current={containersActive ? "page" : undefined} className={`relative flex h-full items-center px-3 text-sm font-semibold transition-colors ${containersActive ? "text-accent" : "text-muted-foreground hover:text-foreground"}`}>
              Agent Team
              {containersActive ? <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-accent" /> : null}
            </Link>
            <Link href="/new" aria-current={newActive ? "page" : undefined} className={`relative hidden h-full items-center px-3 text-sm font-semibold transition-colors sm:flex ${newActive ? "text-accent" : "text-muted-foreground hover:text-foreground"}`}>
              新建任务
              {newActive ? <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-accent" /> : null}
            </Link>
            <Link href="/settings/ai" aria-current={settingsActive ? "page" : undefined} className={`relative flex h-full items-center px-3 text-sm font-semibold transition-colors ${settingsActive ? "text-accent" : "text-muted-foreground hover:text-foreground"}`}>
              AI 设置
              {settingsActive ? <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-accent" /> : null}
            </Link>
          </nav>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <Link href="/containers" aria-label="Agent Team" className={`rounded-lg p-2 sm:hidden ${containersActive ? "bg-accent/10 text-accent" : "text-muted-foreground"}`}><UsersRound className="h-5 w-5" /></Link>
            <Link href="/settings/ai" aria-label="AI 设置" className={`rounded-lg p-2 sm:hidden ${settingsActive ? "bg-accent/10 text-accent" : "text-muted-foreground"}`}><Settings2 className="h-5 w-5" /></Link>
            <div role="status" className={`hidden min-h-10 items-center gap-2 rounded-lg border px-3 text-xs font-semibold sm:flex ${apiOnline === false ? "border-critical/20 bg-critical/5 text-critical" : "border-border bg-white text-muted-foreground"}`}>
              {apiOnline === false ? <WifiOff className="h-4 w-4" /> : <Wifi className="h-4 w-4 text-success" />}
              {apiOnline === null ? "正在检查 API" : apiOnline ? "API 已连接" : "API 不可用"}
            </div>
            {containerDetail ? <button type="button" onClick={() => window.dispatchEvent(new Event("budgetloop:new-session"))} className="btn btn-primary min-h-10 px-3 sm:px-5"><Plus className="h-4 w-4" /><span className="hidden sm:inline">新建 Session</span><span className="sm:hidden">新建</span></button> : containersActive && !containerCreate ? <Link href="/containers/new" className="btn btn-primary min-h-10 px-3 sm:px-5"><Plus className="h-4 w-4" /><span className="hidden sm:inline">创建工作容器</span><span className="sm:hidden">新建</span></Link> : pathname !== "/" && !containersActive && !settingsActive ? <Link href="/new" className="btn btn-primary min-h-10 px-3 sm:px-5"><Plus className="h-4 w-4" /> <span className="hidden sm:inline">新建任务</span><span className="sm:hidden">新建</span></Link> : null}
          </div>
        </div>
      </header>
      {apiOnline === false ? <div role="alert" className="border-b border-critical/15 bg-critical/5 px-4 py-2 text-center text-xs font-medium text-critical">无法连接 BudgetLoop API。已保留当前页面，系统会每 15 秒自动重试。</div> : null}
      <main>{children}</main>
    </div>
  );
}
