"use client";

import type { ValidationController } from "@/lib/hooks/useFlightValidation";
import { ValidationForm } from "./validation_form";
import { ValidationResult } from "./validation_result";

interface FlightValidatorProps {
  controller: ValidationController;
}

export function FlightValidator({ controller }: FlightValidatorProps) {
  return (
    <div className="validator-layout items-start gap-6">
      <ValidationForm controller={controller} />

      <ValidationResult
        result={controller.result}
        loading={controller.loading}
      />
    </div>
  );
}
