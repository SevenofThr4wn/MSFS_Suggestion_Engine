export async function sendJson<T>(path: string, payload: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  } catch {
    throw new Error(
      "Cannot reach the frontend API. Check that the Next.js server is running.",
    );
  }
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      `Server returned HTTP ${response.status} without valid JSON.`,
    );
  }
  if (!response.ok) {
    const body = data as { detail?: unknown };
    const detail = body?.detail;
    if (Array.isArray(detail))
      throw new Error(
        detail
          .map((item) => {
            const e = item as { loc?: string[]; msg?: string };
            return `${e.loc?.join(".") ?? "request"}: ${e.msg ?? "Invalid value"}`;
          })
          .join(" · "),
      );
    throw new Error(
      typeof detail === "string"
        ? detail
        : `Request failed (HTTP ${response.status}).`,
    );
  }
  return data as T;
}
