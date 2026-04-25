import React from "react";
import { Card } from "@mantine/core";
import { useMantineColorScheme } from "@mantine/core";

export default function SectionCard({ children, style, ...rest }) {
  const { colorScheme } = useMantineColorScheme();
  const dark = colorScheme === "dark";
  return (
    <Card
      shadow="sm"
      padding="lg"
      radius="md"
      withBorder
      style={{
        background: dark ? "rgba(3,7,18,0.35)" : "rgba(255,255,255,0.75)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        borderColor: dark ? "#334155" : "#E5E7EB",
        ...style,
      }}
      {...rest}
    >
      {children}
    </Card>
  );
}

