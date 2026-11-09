"use client";

import { Shuffle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface SurpriseMeButtonProps {
  onClick: () => void;
  disabled?: boolean;
}

export default function SurpriseMeButton({
  onClick,
  disabled = false,
}: SurpriseMeButtonProps) {
  return (
    <Button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="h-9 gap-2 rounded-full bg-amber-400 px-5 font-semibold text-zinc-950 hover:bg-amber-300"
    >
      <Shuffle className="size-4" />
      Surprise me
    </Button>
  );
}
