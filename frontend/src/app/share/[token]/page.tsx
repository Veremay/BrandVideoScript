"use client";

import { useParams } from "next/navigation";

import { ShareScriptView } from "@/components/ShareScriptView";

export default function SharePage() {
  const params = useParams();
  const token = typeof params.token === "string" ? params.token : Array.isArray(params.token) ? params.token[0] : "";

  return <ShareScriptView token={token} />;
}
