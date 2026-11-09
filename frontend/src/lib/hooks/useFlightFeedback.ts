
"use client";

import { useEffect, useState } from "react";

export type RepeatPreference =
  | "yes"
  | "maybe"
  | "no";

export interface FlightFeedback {
  enjoyment_rating: number;
  scenery_rating: number;
  approach_rating: number;
  airport_experience_rating: number;
  aircraft_enjoyment_rating: number;
  would_fly_again: RepeatPreference;
  notes: string;
  updated_at: string;
}

export type EditableFeedback = Omit<
  FlightFeedback,
  "updated_at"
>;

export const DEFAULT_FEEDBACK: EditableFeedback = {
  enjoyment_rating: 4,
  scenery_rating: 4,
  approach_rating: 4,
  airport_experience_rating: 4,
  aircraft_enjoyment_rating: 4,
  would_fly_again: "yes",
  notes: "",
};

export function feedbackStorageKey(
  departure: string,
  arrival: string,
  aircraftId: number,
) {
  return [
    "flightdeck-feedback-v1",
    departure,
    arrival,
    aircraftId,
  ].join(":");
}

export function useFlightFeedback(
  departure: string,
  arrival: string,
  aircraftId: number,
) {
  const storageKey = feedbackStorageKey(
    departure,
    arrival,
    aircraftId,
  );

  const [feedback, setFeedback] =
    useState<FlightFeedback | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // Storage is browser-only.
    try {
      const stored = localStorage.getItem(storageKey);
      setFeedback(
        stored ? JSON.parse(stored) as FlightFeedback : null,
      );
    } catch {
      setFeedback(null);
    } finally {
      setLoaded(true);
    }
  }, [storageKey]);

  function save(
    values: EditableFeedback,
  ): boolean {
    const saved: FlightFeedback = {
      ...values,
      updated_at: new Date().toISOString(),
    };

    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify(saved),
      );
      setFeedback(saved);
      return true;
    } catch {
      return false;
    }
  }

  return {
    feedback,
    loaded,
    save,
  };
}
