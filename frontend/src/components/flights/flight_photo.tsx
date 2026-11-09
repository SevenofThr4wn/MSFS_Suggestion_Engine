"use client";

import { useState } from "react";
import { Camera, ExternalLink, Plane } from "lucide-react";

import { AirportPhoto } from "@/components/airports/airport_photo";
import { useFlightPhoto } from "@/lib/hooks/useFlightPhoto";

interface FlightPhotoProps {
  departureIcao: string;
  arrivalIcao: string;
  arrivalName: string;
  airline?: string | null;
  aircraftCode?: string | null;
  registration?: string | null;
  registrationVerified?: boolean;
}

export function FlightPhoto({
  departureIcao,
  arrivalIcao,
  arrivalName,
  airline,
  aircraftCode,
  registration,
  registrationVerified = false,
}: FlightPhotoProps) {
  const {
    data: photo,
    isLoading: loading,
    error,
  } = useFlightPhoto({
    aircraftCode,
    airline,
    registration,
    registrationVerified,
  });

  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);

  const verifiedRegistration = registrationVerified ? registration : null;

  const hasImage =
    Boolean(photo?.image_url) && photo?.image_url !== failedImageUrl;

  const matchLabel = (() => {
    switch (photo?.match_type) {
      case "registration":
        return "Registration match";
      case "airline_aircraft":
        return "Airline & aircraft match";
      case "aircraft_type":
        return "Representative aircraft";
      default:
        return "";
    }
  })();

  const jetPhotosUrl = verifiedRegistration
    ? `https://www.jetphotos.com/registration/${encodeURIComponent(
        verifiedRegistration,
      )}`
    : null;

  if (loading) {
    return (
      <div className="flight-photo-placeholder">
        <Camera size={22} />
        <span>Finding aircraft photography…</span>
      </div>
    );
  }

  if (!hasImage) {
    return (
      <div className="flight-photo-container">
        <AirportPhoto icao={arrivalIcao} name={arrivalName} mode="airport" />

        {process.env.NODE_ENV === "development" && (error || photo?.reason) && (
          <div className="flight-photo-meta">
            <span>
              {photo?.reason ||
                (error instanceof Error
                  ? error.message
                  : "Aircraft photo lookup failed.")}
            </span>
          </div>
        )}
      </div>
    );
  }

  const exact = photo?.match_type === "registration";

  return (
    <div className="flight-photo-container">
      <div className="flight-photo-image">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={photo!.image_url!}
          src={photo!.image_url!}
          alt={
            exact
              ? `Aircraft registration ${photo!.matched_registration}`
              : photo?.match_type === "airline_aircraft"
                ? `${airline} ${aircraftCode}`
                : `Representative ${aircraftCode} aircraft`
          }
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailedImageUrl(photo!.image_url)}
        />

        <div className="flight-photo-overlay">
          <div className="flight-photo-identity">
            <Plane size={15} />

            <span>
              {exact
                ? photo?.matched_registration
                : photo?.match_type === "airline_aircraft"
                  ? `${airline} · ${aircraftCode}`
                  : `${aircraftCode} · Aircraft`}
            </span>
          </div>

          <span className="flight-photo-match">{matchLabel}</span>
        </div>
      </div>

      <div className="flight-photo-meta">
        <span>
          {departureIcao} → {arrivalIcao}
          {" · "}
          {exact
            ? "Airframe photograph, not a flight assignment"
            : photo?.match_type === "airline_aircraft"
              ? "Representative airline aircraft"
              : "Aircraft type only"}
        </span>

        {photo?.source_url && (
          <a
            href={photo.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flight-photo-attribution"
          >
            {photo.credit || "Photographer"}
            {" · "}
            {photo.license || "Licence"}
            <ExternalLink size={12} />
          </a>
        )}

        {photo?.license_url && (
          <a
            href={photo.license_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flight-photo-license"
          >
            Licence details
          </a>
        )}

        {jetPhotosUrl && (
          <a
            href={jetPhotosUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flight-photo-license"
          >
            Search registration on JetPhotos
            <ExternalLink size={12} />
          </a>
        )}
      </div>
    </div>
  );
}
