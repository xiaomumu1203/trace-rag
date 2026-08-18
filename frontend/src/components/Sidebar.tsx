"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

const navItems = [
  { href: "/knowledge-bases", label: "知识库", icon: "📚" },
  { href: "/chat", label: "聊天", icon: "💬" },
  { href: "/retrieval", label: "检索测试", icon: "🔍" },
  { href: "/api-keys", label: "API Keys", icon: "🔑" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { username, logout } = useAuth();

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex h-16 items-center border-b border-slate-200 px-6">
        <span className="text-lg font-bold text-brand-600">TraceRAG</span>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {navItems.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                active
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-200 p-4">
        <div className="mb-2 truncate text-sm font-medium text-slate-700">
          {username || "未登录"}
        </div>
        <button
          onClick={logout}
          className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-100"
        >
          退出登录
        </button>
      </div>
    </aside>
  );
}
