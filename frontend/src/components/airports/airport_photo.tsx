"use client";

import { useEffect, useState } from "react";
import { ImageOff, MapPin } from "lucide-react";

interface AirportPhotoData {
  airport_code: string;
  image_url: string | null;
  source_url?: string;
  title?: string;
  license?: string;
  credit?: string;
}

interface AirportPhotoProps {
  icao: string;
  name: string;
  mode?: "airport" | "aircraft";
  airline?: string | null;
  aircraftCode?: string | null;
}

export function AirportPhoto({
  icao,
  name,
  mode = "airport",
  airline,
  aircraftCode,
}: AirportPhotoProps) {
  const [photo, setPhoto] = useState<AirportPhotoData | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      setPhoto(null);
      setFailed(false);
      setLoading(true);

      try {
        const params = new URLSearchParams({
          code: icao,
          name,
          mode,
        });

        if (mode === "aircraft" && airline && aircraftCode) {
          params.set("airline", airline);
          params.set("aircraft", aircraftCode);
        }

        const response = await fetch(`/api/airports/photos?${params}`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Image lookup failed");
        }

        const data = (await response.json()) as AirportPhotoData;

        if (!controller.signal.aborted) {
          setPhoto(data);
        }
      } catch {
        if (!controller.signal.aborted) {
          setPhoto(null);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => controller.abort();
  }, [icao, name, mode, airline, aircraftCode]);

  const hasImage = !!photo?.image_url && !failed;

  return (
    <div className="airport-photo">
      {hasImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photo.image_url!}
          alt={`${name} airport`}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="airport-photo-fallback">
          {loading ? (
            <span>Loading airport imagery…</span>
          ) : (
            <>
              <ImageOff size={23} />
              <span>Airport photo unavailable</span>
            </>
          )}
        </div>
      )}

      <div className="airport-photo-label">
        <MapPin size={14} />
        <span>
          {icao} · {name}
        </span>
      </div>

      {hasImage && photo?.source_url && (
        <a
          className="airport-photo-credit"
          href={photo.source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {photo.license} · {photo.credit || "Source"}
        </a>
      )}
    </div>
  );
}
