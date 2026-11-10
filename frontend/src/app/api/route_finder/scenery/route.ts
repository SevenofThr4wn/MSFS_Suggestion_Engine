import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET() {
    const configured = (process.env.FASTAPI_BASE_URL ?? "http://127.0.0.1:8000").replace(/\$/, "");
    const base = configured.endsWith("/api/v1") ? configured : `${configured}/api/v1`;

    try {
        const response = await fetch(`${base}/route-finder/scenery`, {
            headers: { Accept: "application/json" },
            cache: "no-store",
            signal: AbortSignal.timeout(20000)
        });

        return new NextResponse(await response.text(), {
            status: response.status,
            headers: { "ContentType": response.headers.get("content-type") || "application/json" }
        });
    } catch (error) {
        return NextResponse.json({
            detail: error instanceof Error ? error.message: "Scenery service unavailable",
        }, { status: 502 })
    }
}