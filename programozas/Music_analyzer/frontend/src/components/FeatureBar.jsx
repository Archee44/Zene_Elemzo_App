import React from "react";
import { Text, Progress, Tooltip } from "@mantine/core";

export default function FeatureBar({
  label,
  value,
  precision = 1,
  tooltip,
  mt = 8,
}) {
  const v = Number(value);
  const clamped = Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0;
  const pct = (clamped * 100).toFixed(precision);
  const content = (
    <div style={{ marginTop: mt }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <Text size="sm" fw={600}>{label}</Text>
        <Text size="sm" c="dimmed">{pct}%</Text>
      </div>
      <Progress value={clamped * 100} radius="sm" />
    </div>
  );
  return tooltip ? (
    <Tooltip label={tooltip} withArrow>
      <div>{content}</div>
    </Tooltip>
  ) : content;
}

