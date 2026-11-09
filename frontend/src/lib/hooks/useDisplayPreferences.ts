"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "flightdeck.display.aircraftPhotography";

export function useDisplayPreferences() {
  const [aircraftPhotographyEnabled, setAircraftPhotographyEnabled] =
    useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);

      if (saved !== null) {
        setAircraftPhotographyEnabled(saved === "true");
      }
    } catch {
      // Storage may be unavailable in private browsing.
    }
  }, []);

  const updateAircraftPhotography = useCallback((enabled: boolean) => {
    setAircraftPhotographyEnabled(enabled);

    try {
      window.localStorage.setItem(STORAGE_KEY, String(enabled));
    } catch {
      // Keep the current session preference.
    }
  }, []);

  return {
    aircraftPhotographyEnabled,
    setAircraftPhotographyEnabled: updateAircraftPhotography,
  };
}
