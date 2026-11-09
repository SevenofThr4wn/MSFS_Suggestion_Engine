import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const base = (
    process.env.FASTAPI_BASE_URL || "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
  try {
    const payload = await request.json();
    const response = await fetch(`${base}/api/v1/recommendations/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(90000),
    });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") || "application/json",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? `Backend unavailable: ${error.message}`
            : "Backend unavailable",
      },
      { status: 502 },
    );
  }
}
