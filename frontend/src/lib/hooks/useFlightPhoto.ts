
import useSWR from "swr";

import type {
  FlightPhotoResult,
} from "@/lib/photos/types";

interface FlightPhotoOptions {
  aircraftCode?: string | null;
  airline?: string | null;
  registration?: string | null;
  registrationVerified?: boolean;
}

const fetcher = async (
  url: string,
): Promise<FlightPhotoResult> => {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(
      `Photo API returned HTTP ${response.status}`,
    );
  }

  return response.json();
};

export function useFlightPhoto({
  aircraftCode,
  airline,
  registration,
  registrationVerified = false,
}: FlightPhotoOptions) {
  const params = new URLSearchParams();

  if (aircraftCode) {
    params.set("aircraft", aircraftCode);
  }

  if (airline) {
    params.set("airline", airline);
  }

  if (registrationVerified && registration) {
    params.set("registration", registration);
  }

  const key = aircraftCode
    ? `/api/flights/photo?${params.toString()}`
    : null;

  return useSWR<FlightPhotoResult>(
    key,
    fetcher,
    {
      dedupingInterval: 60000,
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      shouldRetryOnError: false,
      keepPreviousData: false,
    },
  );
}
