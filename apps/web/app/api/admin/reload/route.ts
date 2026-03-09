import { NextResponse } from "next/server";

const BACKEND_URL = process.env.FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";
const ADMIN_API_KEY = process.env.FRIDAY_ADMIN_API_KEY ?? "";

export async function POST() {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (ADMIN_API_KEY) {
      headers["x-admin-api-key"] = ADMIN_API_KEY;
    }

    const result = await fetch(`${BACKEND_URL}/admin/runtime/reload`, {
      method: "POST",
      headers
    });

    if (!result.ok) {
      const detail = await result.text();
      return NextResponse.json(
        { error: `Backend reload failed (${result.status})`, detail },
        { status: result.status }
      );
    }

    return NextResponse.json({ status: "ok" });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to reach backend runtime reload endpoint",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 502 }
    );
  }
}
