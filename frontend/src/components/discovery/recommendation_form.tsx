"use client";

import { useState } from "react";
import { Controller, FormProvider, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowRight,
  ChevronDown,
  RefreshCw,
  Search,
  Settings2,
  SlidersHorizontal,
} from "lucide-react";

import type { RecommendationsController } from "@/lib/hooks/useRecommendations";

import {
  recommendationSchema,
  RECOMMENDATION_DEFAULT_VALUES,
  validateRecommendation,
} from "@/lib/schemas/recommendation.schema";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

import { AdvancedSettings } from "./advanced_settings";
import { RecommendationRequest } from "@/lib/types/recommendation";

const AIRCRAFT_CATEGORY_LABELS: Record<string, string> = {
  __any__: "Any Category",
  narrow_body: "Narrow-Body",
  wide_body: "Wide-Body",
  regional_jet: "Regional Jet",
  turboprop: "Turboprop",
};

const AIRPORT_MODE_LABELS: Record<string, string> = {
  major: "Major Airports",
  main_hubs: "Main Hubs",
  commercial: "Commercial Airports",
  all: "All Airports",
};

const WEATHER_PREFERENCE_LABELS: Record<string, string> = {
  any: "Any Weather",
  fair: "Fair Weather",
  challenging: "Challenging",
};

interface RecommendationFormProps {
  controller: RecommendationsController;
  aircraftPhotographyEnabled: boolean;
  onAircraftPhotographyChange: (enabled: boolean) => void;
}

export function RecommendationForm({
  controller,
  aircraftPhotographyEnabled,
  onAircraftPhotographyChange,
}: RecommendationFormProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const form = useForm<RecommendationRequest>({
    resolver: zodResolver(recommendationSchema),
    defaultValues: RECOMMENDATION_DEFAULT_VALUES,
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  const { control, handleSubmit } = form;

  const onSubmit = (values: RecommendationRequest) => {
    const request = validateRecommendation(values);
    void controller.generate(request);
  };

  return (
    <section
      className="panel config-panel"
      aria-label="Route recommendation settings"
    >
      <div className="panel-head">
        <div className="panel-icon">
          <SlidersHorizontal size={19} />
        </div>

        <div>
          <h2>Flight parameters</h2>
          <p>Fine-tune your recommendation search</p>
        </div>
      </div>

      <FormProvider {...form}>
        <form
          className="form-content space-y-5"
          onSubmit={handleSubmit(onSubmit)}
          noValidate
        >
          <div className="section-label">ROUTE</div>

          <div className="form-row form-row--airports">
            <Controller
              name="departure_code"
              control={control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="departure_code">
                    Departure ICAO
                  </FieldLabel>

                  <Input
                    id="departure_code"
                    name={field.name}
                    ref={field.ref}
                    onBlur={field.onBlur}
                    value={field.value}
                    onChange={(event) =>
                      field.onChange(event.target.value.toUpperCase())
                    }
                    placeholder="OMDB"
                    maxLength={4}
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
              name="arrival_code"
              control={control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="arrival_code">
                    Arrival ICAO · optional
                  </FieldLabel>

                  <Input
                    id="arrival_code"
                    name={field.name}
                    ref={field.ref}
                    onBlur={field.onBlur}
                    value={field.value ?? ""}
                    onChange={(event) =>
                      field.onChange(event.target.value.toUpperCase() || null)
                    }
                    placeholder="Any destination"
                    maxLength={4}
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

          <div className="form-row">
            <Controller
              name="min_duration_hours"
              control={control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="min_duration_hours">
                    Minimum Hours
                  </FieldLabel>

                  <Input
                    id="min_duration_hours"
                    name={field.name}
                    ref={field.ref}
                    onBlur={field.onBlur}
                    type="number"
                    min={0.5}
                    max={24}
                    step={0.5}
                    value={field.value}
                    onChange={(event) =>
                      field.onChange(
                        event.target.value === ""
                          ? NaN
                          : Number(event.target.value),
                      )
                    }
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
              name="max_duration_hours"
              control={control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="max_duration_hours">
                    Maximum Hours
                  </FieldLabel>

                  <Input
                    id="max_duration_hours"
                    name={field.name}
                    ref={field.ref}
                    onBlur={field.onBlur}
                    type="number"
                    min={1}
                    max={30}
                    step={0.5}
                    value={field.value}
                    onChange={(event) =>
                      field.onChange(
                        event.target.value === ""
                          ? NaN
                          : Number(event.target.value),
                      )
                    }
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

          <div className="section-label">AIRCRAFT &amp; DESTINATIONS</div>

          <Controller
            name="preferred_category"
            control={control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="preferred_category">
                  Aircraft Category
                </FieldLabel>

                <Select
                  name={field.name}
                  value={field.value ?? "__any__"}
                  onValueChange={(value) =>
                    field.onChange(value === "__any__" ? null : value)
                  }
                >
                  <SelectTrigger
                    id="preferred_category"
                    aria-invalid={fieldState.invalid}
                    className="w-full"
                  >
                    <SelectValue>
                      {AIRCRAFT_CATEGORY_LABELS[field.value ?? "__any__"] ??
                        "Any category"}
                    </SelectValue>
                  </SelectTrigger>

                  <SelectContent>
                    <SelectItem value="__any__">Any Category</SelectItem>
                    <SelectItem value="narrow_body">Narrow-Body</SelectItem>
                    <SelectItem value="wide_body">Wide-Body</SelectItem>
                    <SelectItem value="regional_jet">Regional Jet</SelectItem>
                    <SelectItem value="turboprop">Turboprop</SelectItem>
                  </SelectContent>
                </Select>

                {fieldState.invalid && (
                  <FieldError errors={[fieldState.error]} />
                )}
              </Field>
            )}
          />

          <Controller
            name="airport_mode"
            control={control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="airport_mode">
                  Airport Discovery Mode
                </FieldLabel>

                <Select
                  name={field.name}
                  value={field.value}
                  onValueChange={field.onChange}
                >
                  <SelectTrigger
                    id="airport_mode"
                    aria-invalid={fieldState.invalid}
                    className="w-full"
                  >
                    <SelectValue>
                      {AIRPORT_MODE_LABELS[field.value] ?? field.value}
                    </SelectValue>
                  </SelectTrigger>

                  <SelectContent>
                    <SelectItem value="major">Major Airports</SelectItem>
                    <SelectItem value="main_hubs">
                      Main Hubs
                    </SelectItem>
                    <SelectItem value="commercial">
                      Commercial Airports
                    </SelectItem>
                    <SelectItem value="all">All Airports</SelectItem>
                  </SelectContent>
                </Select>

                {fieldState.invalid && (
                  <FieldError errors={[fieldState.error]} />
                )}
              </Field>
            )}
          />

          <Controller
            name="min_flyability_score"
            control={control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel>
                  Minimum replayability · {field.value}/100
                </FieldLabel>

                <Slider
                  name={field.name}
                  min={0}
                  max={100}
                  step={5}
                  value={[field.value]}
                  onValueChange={(value) => {
                    const nextValue = Array.isArray(value) ? value[0] : value;

                    field.onChange(nextValue ?? 0);
                  }}
                  aria-label="Minimum replayability score"
                  className="my-3"
                />

                <div className="range-labels">
                  <span>ANY EXPERIENCE</span>
                  <span>HIGH ENJOYMENT</span>
                </div>

                {fieldState.invalid && (
                  <FieldError errors={[fieldState.error]} />
                )}
              </Field>
            )}
          />

          <div className="form-row">
            <Controller
              name="limit"
              control={control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="limit">Results</FieldLabel>

                  <Select
                    name={field.name}
                    value={String(field.value)}
                    onValueChange={(value) => field.onChange(Number(value))}
                  >
                    <SelectTrigger
                      id="limit"
                      className="w-full"
                      aria-invalid={fieldState.invalid}
                    >
                      <SelectValue>{`${field.value} flights`}</SelectValue>
                    </SelectTrigger>

                    <SelectContent>
                      <SelectItem value="5">5 flights</SelectItem>
                      <SelectItem value="10">10 flights</SelectItem>
                      <SelectItem value="20">20 flights</SelectItem>
                      <SelectItem value="50">50 flights</SelectItem>
                    </SelectContent>
                  </Select>

                  {fieldState.invalid && (
                    <FieldError errors={[fieldState.error]} />
                  )}
                </Field>
              )}
            />

            <Controller
              name="weather_preference"
              control={control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="weather_preference">
                    Weather Preference
                  </FieldLabel>

                  <Select
                    name={field.name}
                    value={field.value}
                    onValueChange={field.onChange}
                  >
                    <SelectTrigger
                      id="weather_preference"
                      className="w-full"
                      aria-invalid={fieldState.invalid}
                    >
                      <SelectValue>
                        {WEATHER_PREFERENCE_LABELS[field.value] ?? field.value}
                      </SelectValue>
                    </SelectTrigger>

                    <SelectContent>
                      <SelectItem value="any">Any Weather</SelectItem>
                      <SelectItem value="fair">Fair Weather</SelectItem>
                      <SelectItem value="challenging">Challenging</SelectItem>
                    </SelectContent>
                  </Select>

                  {fieldState.invalid && (
                    <FieldError errors={[fieldState.error]} />
                  )}
                </Field>
              )}
            />
          </div>

          <Controller
            name="owned_only"
            control={control}
            render={({ field }) => (
              <div className="flex items-center justify-between gap-4 py-2">
                <label
                  htmlFor="owned_only"
                  className="cursor-pointer text-xs font-semibold text-foreground"
                >
                  Owned aircraft only
                </label>

                <Switch
                  id="owned_only"
                  name={field.name}
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  ref={field.ref}
                />
              </div>
            )}
          />

          <Controller
            name="prefer_addon_scenery"
            control={control}
            render={({ field }) => (
              <div className="flex items-center justify-between gap-4 py-2">
                <label
                  htmlFor="prefer_addon_scenery"
                  className="cursor-pointer text-xs font-semibold text-foreground"
                >
                  Prioritise installed scenery
                </label>

                <Switch
                  id="prefer_addon_scenery"
                  name={field.name}
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  ref={field.ref}
                />
              </div>
            )}
          />

          <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
            <CollapsibleTrigger
              className="flex w-full items-center justify-between rounded-md border-t border-border px-0 py-3 text-xs font-semibold text-primary transition-colors hover:text-primary/80"
              aria-controls="advanced-engine-settings"
            >
              <span className="flex items-center gap-2">
                <Settings2 size={16} />
                Advanced engine settings
              </span>

              <ChevronDown
                size={16}
                className={`transition-transform duration-200 ${
                  advancedOpen ? "rotate-180" : ""
                }`}
              />
            </CollapsibleTrigger>

            <CollapsibleContent>
              <AdvancedSettings
                aircraftPhotographyEnabled={aircraftPhotographyEnabled}
                onAircraftPhotographyChange={onAircraftPhotographyChange}
              />
            </CollapsibleContent>
          </Collapsible>

          {controller.error && (
            <div
              role="alert"
              className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive"
            >
              {controller.error}
            </div>
          )}

          <Button
            type="submit"
            disabled={controller.loading}
            className="mt-4 h-11 w-full justify-between bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {controller.loading ? (
              <RefreshCw className="size-4 animate-spin" />
            ) : (
              <Search className="size-4" />
            )}

            <span>
              {controller.loading
                ? "Analysing routes…"
                : "Generate recommendations"}
            </span>

            <ArrowRight className="size-4" />
          </Button>
        </form>
      </FormProvider>
    </section>
  );
}
