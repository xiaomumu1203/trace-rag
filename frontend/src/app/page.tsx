"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/knowledge-bases");
  }, [router]);

  return (
    <div className="flex h-screen items-center justify-center text-slate-400">
      加载中...
    </div>
  );
}
