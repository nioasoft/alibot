"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

export function PageView() {
  const pathname = usePathname();

  useEffect(() => {
    fetch("/api/view", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: pathname }),
    }).catch(() => {});
  }, [pathname]);

  return null;
}
