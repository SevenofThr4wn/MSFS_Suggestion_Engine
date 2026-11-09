import type { Metadata } from "next";

import RouteFinder from "@/components/route_finder/route_finder";
import { RouteFinderProvider } from "@/components/route_finder/route_finder_provider";

export const metadata: Metadata = {
  title: "Route Finder | FlightEngine",
  description:
    "Discover flights based on aircraft, airport, and route preferences.",
};

export default function RouteFinderPage() {
  return (
    <RouteFinderProvider>
      <RouteFinder />
    </RouteFinderProvider>
  );
}
