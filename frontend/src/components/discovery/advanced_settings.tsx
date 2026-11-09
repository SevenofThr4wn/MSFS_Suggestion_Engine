"use client";

import { Controller, useFormContext } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { RecommendationRequest } from "@/lib/types/recommendation";

interface AdvancedSettingsProps {
  aircraftPhotographyEnabled: boolean;
  onAircraftPhotographyChange: (enabled: boolean) => void;
}

type BooleanSetting =
  | "airport_filter.require_paved_runway"
  | "airport_filter.require_known_runway_data"
  | "airport_filter.require_scheduled_service"
  | "include_indeterminate"
  | "strict_aircraft_category"
  | "require_real_world_route"
  | "require_real_world_service"
  | "live_weather"
  | "scenarios_enabled"
  | "departure_gate_enabled"
  | "include_decision_trace"
  | "include_rejected_examples";

type NumberSetting = "max_candidates" | "max_airports";

interface SwitchSettingProps {
  name: BooleanSetting;
  label: string;
  hint?: string;
}

function SwitchSetting({ name, label, hint }: SwitchSettingProps) {
  const { control } = useFormContext<RecommendationRequest>();

  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <div className="flex items-center justify-between gap-4 py-3">
          <div className="min-w-0 flex-1">
            <label
              htmlFor={name}
              className="block cursor-pointer text-xs font-semibold text-foreground"
            >
              {label}
            </label>

            {hint && (
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {hint}
              </p>
            )}
          </div>

          <Switch
            id={name}
            name={field.name}
            checked={Boolean(field.value)}
            onCheckedChange={field.onChange}
            ref={field.ref}
          />
        </div>
      )}
    />
  );
}

interface NumberSettingProps {
  name: NumberSetting;
  label: string;
  min: number;
  max: number;
}

function NumberSettingField({ name, label, min, max }: NumberSettingProps) {
  const { control } = useFormContext<RecommendationRequest>();

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel htmlFor={name}>{label}</FieldLabel>

          <Input
            id={name}
            name={field.name}
            ref={field.ref}
            onBlur={field.onBlur}
            type="number"
            min={min}
            max={max}
            step={1}
            value={field.value}
            onChange={(event) =>
              field.onChange(
                event.target.value === "" ? NaN : Number(event.target.value),
              )
            }
            className="flightengine-input"
            aria-invalid={fieldState.invalid}
          />

          {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
        </Field>
      )}
    />
  );
}

export function AdvancedSettings({
  aircraftPhotographyEnabled,
  onAircraftPhotographyChange,
}: AdvancedSettingsProps) {
  const { control } = useFormContext<RecommendationRequest>();

  return (
    <div className="advanced-content space-y-5" id="advanced-engine-settings">
      <div className="space-y-1">
        <h3 className="text-xs font-semibold text-foreground">
          Aircraft selection
        </h3>
        <p className="text-xs text-muted-foreground">
          Optionally target a specific aircraft in your database.
        </p>
      </div>

      <Controller
        name="aircraft_id"
        control={control}
        render={({ field, fieldState }) => (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor="aircraft_id">
              Specific aircraft database ID
            </FieldLabel>

            <Input
              id="aircraft_id"
              name={field.name}
              ref={field.ref}
              onBlur={field.onBlur}
              type="number"
              min={1}
              step={1}
              placeholder="Any aircraft"
              value={field.value ?? ""}
              onChange={(event) =>
                field.onChange(
                  event.target.value === "" ? null : Number(event.target.value),
                )
              }
              className="flightengine-input"
              aria-invalid={fieldState.invalid}
            />

            {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
          </Field>
        )}
      />

      <Separator />

      <div className="space-y-1">
        <h3 className="text-xs font-semibold text-foreground">
          Discovery budgets
        </h3>
        <p className="text-xs text-muted-foreground">
          Control how many airports and candidate routes the engine evaluates.
        </p>
      </div>

      <div className="form-row">
        <NumberSettingField
          name="max_candidates"
          label="Candidate budget"
          min={10}
          max={50000}
        />

        <NumberSettingField
          name="max_airports"
          label="Airport budget"
          min={10}
          max={10000}
        />
      </div>

      <Separator />

      <div className="space-y-1">
        <h3 className="text-xs font-semibold text-foreground">
          Airport filters
        </h3>
      </div>

      <Controller
        name="airport_filter.minimum_airport_size"
        control={control}
        render={({ field, fieldState }) => (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor="minimum_airport_size">
              Minimum airport size
            </FieldLabel>

            <Select
              name={field.name}
              value={field.value ?? "__default__"}
              onValueChange={(value) =>
                field.onChange(value === "__default__" ? null : value)
              }
            >
              <SelectTrigger
                id="minimum_airport_size"
                className="w-full"
                aria-invalid={fieldState.invalid}
              >
                <SelectValue />
              </SelectTrigger>

              <SelectContent>
                <SelectItem value="__default__">Aircraft default</SelectItem>
                <SelectItem value="small_airport">Small</SelectItem>
                <SelectItem value="medium_airport">Medium</SelectItem>
                <SelectItem value="large_airport">Large</SelectItem>
              </SelectContent>
            </Select>

            {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
          </Field>
        )}
      />

      <div className="divide-y divide-border/50">
        <SwitchSetting
          name="airport_filter.require_paved_runway"
          label="Paved runway required"
        />

        <SwitchSetting
          name="airport_filter.require_known_runway_data"
          label="Known runway data required"
        />

        <SwitchSetting
          name="airport_filter.require_scheduled_service"
          label="Scheduled service required"
        />
      </div>

      <Separator />

      <div className="space-y-1">
        <h3 className="text-xs font-semibold text-foreground">
          Recommendation rules
        </h3>
      </div>

      <div className="divide-y divide-border/50">
        <SwitchSetting
          name="include_indeterminate"
          label="Include uncertain assessments"
        />

        <SwitchSetting
          name="strict_aircraft_category"
          label="Strict category matching"
        />

        <SwitchSetting
          name="require_real_world_route"
          label="Require real-world route"
        />

        <SwitchSetting
          name="require_real_world_service"
          label="Require catalogued airline service"
        />
      </div>

      <Separator />

      <div className="space-y-1">
        <h3 className="text-xs font-semibold text-foreground">
          Engine features
        </h3>
      </div>

      <div className="divide-y divide-border/50">
        <SwitchSetting name="live_weather" label="Live METAR weather" />

        <SwitchSetting name="scenarios_enabled" label="Optional scenarios" />

        <SwitchSetting
          name="departure_gate_enabled"
          label="Departure gate candidates"
        />

        <SwitchSetting name="include_decision_trace" label="Decision trace" />

        <SwitchSetting
          name="include_rejected_examples"
          label="Rejected examples"
        />
      </div>

      <Separator />

      <div className="space-y-3">
        <div className="space-y-1">
          <h3 className="text-xs font-semibold text-foreground">
            Display preferences
          </h3>

          <p className="text-xs leading-relaxed text-muted-foreground">
            Customise how flight recommendations are displayed.
          </p>
        </div>

        <div className="flex items-center justify-between gap-4 py-3">
          <div className="min-w-0 flex-1">
            <label
              htmlFor="aircraft-photography"
              className="block cursor-pointer text-xs font-semibold text-foreground"
            >
              Aircraft photography
            </label>

            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Show aircraft photographs on recommendation cards. If unavailable,
              use destination airport imagery. Disabled by default.
            </p>
          </div>

          <Switch
            id="aircraft-photography"
            checked={aircraftPhotographyEnabled}
            onCheckedChange={onAircraftPhotographyChange}
          />
        </div>
      </div>
    </div>
  );
}
