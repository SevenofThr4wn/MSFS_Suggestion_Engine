import { NextRequest, NextResponse } from "next/server";
import type { AirportCoordinateResponse } from "@/lib/types/route_finder";

const BACKEND_URL = (
  process.env.FASTAPI_BASE_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

export async function GET(request: NextRequest) {
  const rawCodes = request.nextUrl.searchParams.get("codes") ?? "";

  const codes = [
    ...new Set(
      rawCodes
        .split(",")
        .map((code) => code.trim().toUpperCase())
        .filter(Boolean),
    ),
  ];

  if (
    codes.length === 0 ||
    codes.length > 100 ||
    codes.some((code) => !/^[A-Z]{4}$/.test(code))
  ) {
    return NextResponse.json(
      {
        detail: "Provide between 1 and 100 valid ICAO codes.",
      },
      { status: 400 },
    );
  }

  try {
    const params = new URLSearchParams({
      codes: codes.join(","),
    });

    const response = await fetch(
      `${BACKEND_URL}/airports/coordinates?${params}`,
      {
        headers: {
          Accept: "application/json",
        },
        next: {
          revalidate: 300,
        },
      },
    );

    if (!response.ok) {
      return NextResponse.json(
        {
          detail: "Unable to retrieve airport coordinates.",
        },
        { status: response.status },
      );
    }

    const data = (await response.json()) as AirportCoordinateResponse;

    if (!Array.isArray(data.airports)) {
      return NextResponse.json(
        {
          detail: "Invalid airport coordinate response.",
        },
        { status: 502 },
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error("AIRPORT COORDINATE ERROR |", error);

    return NextResponse.json(
      {
        detail: "Airport coordinate service is unavailable.",
      },
      { status: 502 },
    );
  }
}
