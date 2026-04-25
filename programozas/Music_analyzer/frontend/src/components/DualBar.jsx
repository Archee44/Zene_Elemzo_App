import React from "react";
import { Text, Progress } from "@mantine/core";

export default function DualBar({ leftLabel, leftValue, rightLabel, rightValue, color, leftColor, rightColor }) {
  const clamp = (x) => {
    const v = Number(x);
    return Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0;
  };
  const l = clamp(leftValue);
  const r = clamp(rightValue);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <Text size="sm" fw={600}>{leftLabel}</Text>
          <Text size="sm" c="dimmed">{(l * 100).toFixed(1)}%</Text>
        </div>
        <Progress value={l * 100} radius="sm" color={leftColor || color} />
      </div>
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <Text size="sm" fw={600}>{rightLabel}</Text>
          <Text size="sm" c="dimmed">{(r * 100).toFixed(1)}%</Text>
        </div>
        <Progress value={r * 100} radius="sm" color={rightColor || color} />
      </div>
    </div>
  );
}
