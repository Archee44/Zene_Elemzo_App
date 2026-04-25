import React, { useMemo } from "react";
import { useMantineColorScheme } from "@mantine/core";

function polarToCartesian(cx, cy, r, angle) {
  const a = ((angle - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function arcPath(cx, cy, r, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? 0 : 1;
  return [
    "M",
    start.x,
    start.y,
    "A",
    r,
    r,
    0,
    largeArcFlag,
    0,
    end.x,
    end.y,
  ].join(" ");
}

export default function DonutChart({
  data = [],
  size = 180,
  thickness = 20,
  centerLabel,
  colors,
}) {
  const { colorScheme } = useMantineColorScheme();
  const dark = colorScheme === "dark";

  const palette = useMemo(() => {
    const light = [
      "#5B8FF9",
      "#61DDAA",
      "#65789B",
      "#F6BD16",
      "#7262FD",
      "#78D3F8",
      "#9661BC",
      "#F6903D",
    ];
    const darkP = [
      "#8AB4F8",
      "#34D399",
      "#9AA5B1",
      "#FBBF24",
      "#A78BFA",
      "#67E8F9",
      "#C084FC",
      "#F59E0B",
    ];
    return colors && colors.length ? colors : dark ? darkP : light;
  }, [colors, colorScheme, dark]);

  const total = Math.max(
    0.000001,
    data.reduce((s, d) => s + (Number(d.value) || 0), 0)
  );
  const radius = (size - thickness) / 2;
  const cx = size / 2;
  const cy = size / 2;

  let acc = 0;
  const segments = data.map((d, i) => {
    const v = Math.max(0, Number(d.value) || 0);
    const angle = (v / total) * 360;
    const start = acc;
    const end = acc + angle;
    acc += angle;
    return {
      label: d.label,
      value: v,
      start,
      end,
      color: palette[i % palette.length],
    };
  });

  const textColor = dark ? "#E5E7EB" : "#111827";
  const bgTrack = dark ? "#1F2937" : "#F3F4F6";

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img">
      {}
      <circle
        cx={cx}
        cy={cy}
        r={radius}
        fill="none"
        stroke={bgTrack}
        strokeWidth={thickness}
      />
      {}
      <g transform={`translate(0,0)`}>
        {segments.map((s, idx) => (
          <path
            key={idx}
            d={arcPath(cx, cy, radius, s.start, s.end)}
            stroke={s.color}
            strokeWidth={thickness}
            fill="none"
            strokeLinecap="butt"
          />
        ))}
      </g>
      {}
      {centerLabel && (
        <g>
          <text
            x={cx}
            y={cy}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={14}
            fontWeight={600}
            fill={textColor}
          >
            {centerLabel}
          </text>
        </g>
      )}
    </svg>
  );
}
