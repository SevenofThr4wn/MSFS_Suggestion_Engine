
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  const url = new URL(
    "/api/v1/route-finder/scenery",
    BACKEND_URL,
  );

  // Critical: forward ALL query parameters to FastAPI.
  url.search = request.nextUrl.search;

  try {
    const response = await fetch(url.toString(), {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
      signal: request.signal,
    });

    const body = await response.text();

    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ??
          "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error(
      "[Scenery API] Backend request failed:",
      error,
    );

    return NextResponse.json(
      {
        detail: "Unable to reach the scenery backend.",
      },
      { status: 502 },
    );
  }
}
