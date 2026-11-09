"use client";

import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Star } from "lucide-react";

import {
  DEFAULT_FEEDBACK,
  useFlightFeedback,
} from "@/lib/hooks/useFlightFeedback";

import type { EditableFeedback } from "@/lib/hooks/useFlightFeedback";

import {
  flightFeedbackSchema,
  toEditableFeedback,
} from "@/lib/schemas/flight-feedback.schema";

import type { FlightFeedbackValues } from "@/lib/schemas/flight-feedback.schema";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface FlightFeedbackFormProps {
  departure: string;
  arrival: string;
  aircraftId: number;
}

type RatingField =
  | "enjoyment_rating"
  | "scenery_rating"
  | "approach_rating"
  | "airport_experience_rating"
  | "aircraft_enjoyment_rating";

const RATING_FIELDS: {
  key: RatingField;
  label: string;
}[] = [
  {
    key: "enjoyment_rating",
    label: "Overall enjoyment",
  },
  {
    key: "scenery_rating",
    label: "Scenery",
  },
  {
    key: "approach_rating",
    label: "Approach experience",
  },
  {
    key: "airport_experience_rating",
    label: "Airport experience",
  },
  {
    key: "aircraft_enjoyment_rating",
    label: "Aircraft enjoyment",
  },
];

function feedbackDefaults(
  feedback: EditableFeedback | null | undefined,
): FlightFeedbackValues {
  const source = feedback ?? DEFAULT_FEEDBACK;

  return {
    enjoyment_rating: source.enjoyment_rating,
    scenery_rating: source.scenery_rating,
    approach_rating: source.approach_rating,
    airport_experience_rating: source.airport_experience_rating,
    aircraft_enjoyment_rating: source.aircraft_enjoyment_rating,
    would_fly_again: source.would_fly_again,
    notes: source.notes,
  };
}

export function FlightFeedbackForm({
  departure,
  arrival,
  aircraftId,
}: FlightFeedbackFormProps) {
  const { feedback, loaded, save } = useFlightFeedback(
    departure,
    arrival,
    aircraftId,
  );

  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const form = useForm<FlightFeedbackValues>({
    resolver: zodResolver(flightFeedbackSchema),
    defaultValues: feedbackDefaults(null),
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  const { control, handleSubmit, reset } = form;

  useEffect(() => {
    if (!loaded) return;

    reset(feedbackDefaults(feedback));
    setSaved(false);
    setSaveError(null);
  }, [loaded, feedback, reset]);

  function onSubmit(values: FlightFeedbackValues) {
    setSaveError(null);
    setSaved(false);

    const payload = toEditableFeedback(values);

    if (save(payload)) {
      setSaved(true);
    } else {
      setSaveError("Could not save feedback in this browser.");
    }
  }

  return (
    <section className="space-y-5 rounded-lg border border-border bg-secondary/20 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h4 className="text-sm font-semibold text-foreground">
            How was your flight?
          </h4>

          <p className="text-xs leading-relaxed text-muted-foreground">
            Rate your experience flying {departure} to {arrival}.
          </p>
        </div>

        {feedback && (
          <span className="text-[11px] font-medium text-emerald-300">
            Previously rated
          </span>
        )}
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
        <div className="space-y-4">
          {RATING_FIELDS.map(({ key, label }) => (
            <Controller
              key={key}
              name={key}
              control={control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <FieldLabel>{label}</FieldLabel>

                    <div
                      className="flex items-center gap-1"
                      role="group"
                      aria-label={label}
                    >
                      {[1, 2, 3, 4, 5].map((rating) => (
                        <button
                          key={rating}
                          type="button"
                          className={cn(
                            "rounded-md p-1.5 transition-transform",
                            "hover:scale-110 focus-visible:outline-none",
                            "focus-visible:ring-2 focus-visible:ring-ring",
                            rating <= field.value
                              ? "text-amber-400"
                              : "text-muted-foreground/50",
                          )}
                          aria-label={`${label}: ${rating} of 5`}
                          aria-pressed={field.value === rating}
                          onClick={() => {
                            field.onChange(rating);
                            setSaved(false);
                          }}
                        >
                          <Star
                            size={19}
                            fill={
                              rating <= field.value ? "currentColor" : "none"
                            }
                          />
                        </button>
                      ))}
                    </div>
                  </div>

                  {fieldState.invalid && (
                    <FieldError errors={[fieldState.error]} />
                  )}
                </Field>
              )}
            />
          ))}
        </div>

        <Controller
          name="would_fly_again"
          control={control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="would_fly_again">
                Would you fly this route again?
              </FieldLabel>

              <Select
                name={field.name}
                value={field.value}
                onValueChange={(value) => {
                  field.onChange(value);
                  setSaved(false);
                }}
              >
                <SelectTrigger
                  id="would_fly_again"
                  className="w-full"
                  aria-invalid={fieldState.invalid}
                >
                  <SelectValue />
                </SelectTrigger>

                <SelectContent>
                  <SelectItem value="yes">Definitely</SelectItem>
                  <SelectItem value="maybe">Maybe</SelectItem>
                  <SelectItem value="no">Probably not</SelectItem>
                </SelectContent>
              </Select>

              {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
            </Field>
          )}
        />

        <Controller
          name="notes"
          control={control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="feedback_notes">Flight Notes</FieldLabel>

              <Textarea
                id="feedback_notes"
                name={field.name}
                ref={field.ref}
                onBlur={field.onBlur}
                rows={3}
                maxLength={2000}
                placeholder="What made this flight memorable?"
                value={field.value}
                onChange={(event) => {
                  field.onChange(event.target.value);
                  setSaved(false);
                }}
                aria-invalid={fieldState.invalid}
                className="resize-y"
              />

              <p className="text-right text-[10px] text-muted-foreground">
                {field.value.length} / 2000
              </p>

              {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
            </Field>
          )}
        />

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="submit"
            disabled={!loaded || form.formState.isSubmitting}
          >
            Save feedback
          </Button>

          {saved && (
            <span
              role="status"
              className="flex items-center gap-1.5 text-xs text-emerald-300"
            >
              <CheckCircle2 className="size-4" />
              Saved locally
            </span>
          )}
        </div>

        {saveError && (
          <p role="alert" className="text-xs text-destructive">
            {saveError}
          </p>
        )}
      </form>

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        Feedback is currently WIP and temporary, persistent database storage will be added in a future preview.
      </p>
    </section>
  );
}
