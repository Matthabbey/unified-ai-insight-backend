"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/app/lib/api";

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to dashboard if authenticated, otherwise to login
    if (getToken()) {
      router.replace("/dashboard");
    } else {
      router.replace("/login");
    }
  }, [router]);

  // Brief loading state while redirect resolves
  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#FFCC00] flex items-center justify-center font-black text-black text-lg animate-pulse">
          A
        </div>
        <span className="text-white text-xl font-bold">MTN Atlas</span>
      </div>
    </div>
  );
}
