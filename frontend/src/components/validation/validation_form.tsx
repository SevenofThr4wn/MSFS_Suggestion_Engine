"use client";

import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import {
  ArrowRight,
  ClipboardCheck,
  Info,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";

import type { ValidationController } from "@/lib/hooks/useFlightValidation";

import {
  flightValidationSchema,
  type FlightValidationValues,
} from "@/lib/schemas/flight-validation.schema";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface ValidationFormProps {
  controller: ValidationController;
}

export function ValidationForm({ controller }: ValidationFormProps) {
  const form = useForm<FlightValidationValues>({
    resolver: zodResolver(flightValidationSchema),
    defaultValues: {
      aircraftId: 5,
      departure: "KJFK",
      arrival: "TFFJ",
    },
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  const { control, handleSubmit } = form;

  function onSubmit(values: FlightValidationValues) {
    void controller.validate(values);
  }

  return (
    <section
      className="panel overflow-hidden border-border bg-card"
      aria-label="Flight validation settings"
    >
      <div className="panel-head">
        <div className="panel-icon">
          <ClipboardCheck size={19} />
        </div>

        <div>
          <h2>Validate a specific flight</h2>
          <p>
            Check aircraft and airport compatibility independently of discovery.
          </p>
        </div>
      </div>

      <form
        className="form-content space-y-5"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <Controller
          name="aircraftId"
          control={control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="validation-aircraft">
                Aircraft database ID
              </FieldLabel>

              <Input
                id="validation-aircraft"
                name={field.name}
                ref={field.ref}
                onBlur={field.onBlur}
                type="number"
                min={1}
                step={1}
                placeholder="Enter aircraft ID"
                value={Number.isFinite(field.value) ? field.value : ""}
                onChange={(event) => {
                  const raw = event.target.value;

                  field.onChange(raw === "" ? NaN : Number(raw));
                }}
                aria-invalid={fieldState.invalid}
                className="flightengine-input"
              />

              {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
            </Field>
          )}
        />

        <div className="form-row form-row--airports">
          <Controller
            name="departure"
            control={control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="validation-departure">
                  Departure ICAO
                </FieldLabel>

                <Input
                  id="validation-departure"
                  name={field.name}
                  ref={field.ref}
                  onBlur={field.onBlur}
                  value={field.value}
                  onChange={(event) =>
                    field.onChange(event.target.value.toUpperCase())
                  }
                  maxLength={4}
                  placeholder="KJFK"
                  autoComplete="off"
                  aria-invalid={fieldState.invalid}
                  className="flightengine-input"
                />

                {fieldState.invalid && (
                  <FieldError errors={[fieldState.error]} />
                )}
              </Field>
            )}
          />

          <Controller
            name="arrival"
            control={control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="validation-arrival">
                  Arrival ICAO
                </FieldLabel>

                <Input
                  id="validation-arrival"
                  name={field.name}
                  ref={field.ref}
                  onBlur={field.onBlur}
                  value={field.value}
                  onChange={(event) =>
                    field.onChange(event.target.value.toUpperCase())
                  }
                  maxLength={4}
                  placeholder="TFFJ"
                  autoComplete="off"
                  aria-invalid={fieldState.invalid}
                  className="flightengine-input"
                />

                {fieldState.invalid && (
                  <FieldError errors={[fieldState.error]} />
                )}
              </Field>
            )}
          />
        </div>

        <Alert className="border-primary/20 bg-primary/5">
          <Info className="size-4 text-primary" />

          <AlertDescription className="text-xs leading-relaxed text-muted-foreground">
            Enter the actual database ID of the aircraft. IDs can differ between
            FlightEngine installations.
          </AlertDescription>
        </Alert>

        {controller.error && (
          <Alert
            role="alert"
            className="border-destructive/30 bg-destructive/10"
          >
            <Info className="size-4 text-destructive" />

            <AlertDescription className="text-xs text-destructive">
              {controller.error}
            </AlertDescription>
          </Alert>
        )}

        <Button
          type="submit"
          disabled={controller.loading || form.formState.isSubmitting}
          className="h-11 w-full justify-between"
        >
          {controller.loading ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <ShieldCheck className="size-4" />
          )}

          <span>
            {controller.loading ? "Validating flight…" : "Validate flight"}
          </span>

          <ArrowRight className="size-4" />
        </Button>
      </form>
    </section>
  );
}
