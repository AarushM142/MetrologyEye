"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BBox, Finding, Severity } from "@/lib/types";

interface CanvasItem {
  id: string;
  field: string;
  severity: Severity;
  bbox: BBox;
  rule_id: string;
}

interface EvidenceCanvasProps {
  imageUrl: string;
  imageWidth: number;
  imageHeight: number;
  findings: Finding[];
  selectedField: string | null;
  onSelectField: (field: string | null) => void;
}

export function EvidenceCanvas({
  imageUrl,
  imageWidth,
  imageHeight,
  findings,
  selectedField,
  onSelectField,
}: EvidenceCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [imageObj, setImageObj] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState<number>(1);
  const [hoveredField, setHoveredField] = useState<string | null>(null);

  const items: CanvasItem[] = findings
    .filter((f): f is Finding & { bbox: BBox } => f.bbox !== null)
    .map((f, idx) => ({
      id: f.field || f.rule_id || `box-${idx}`,
      field: f.field || f.rule_id,
      severity: f.severity,
      bbox: f.bbox,
      rule_id: f.rule_id,
    }));

  useEffect(() => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = imageUrl;
    img.onload = () => setImageObj(img);
  }, [imageUrl]);

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imageObj) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(imageObj, 0, 0, imageWidth, imageHeight);

    // 1. Draw inactive boxes
    items.forEach((item) => {
      const isTarget =
        (selectedField && item.field === selectedField) ||
        (hoveredField && item.field === hoveredField);
      if (isTarget) return;

      const [x, y, w, h] = item.bbox;
      const isViolation = item.severity === "VIOLATION";
      const isWarning = item.severity === "WARNING";

      if (isViolation) {
        ctx.fillStyle = "rgba(225, 29, 72, 0.08)";
        ctx.fillRect(x, y, w, h);
        ctx.strokeStyle = "#e11d48";
        ctx.lineWidth = 2.5;
        ctx.strokeRect(x, y, w, h);
      } else if (isWarning) {
        ctx.fillStyle = "rgba(217, 119, 6, 0.08)";
        ctx.fillRect(x, y, w, h);
        ctx.strokeStyle = "#d97706";
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
      } else {
        ctx.fillStyle = "rgba(16, 185, 129, 0.04)";
        ctx.fillRect(x, y, w, h);
        ctx.strokeStyle = "rgba(16, 185, 129, 0.5)";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(x, y, w, h);
      }
    });

    // 2. Draw highlighted/hovered box
    items.forEach((item) => {
      const isTarget =
        (selectedField && item.field === selectedField) ||
        (hoveredField && item.field === hoveredField);
      if (!isTarget) return;

      const [x, y, w, h] = item.bbox;
      const isViolation = item.severity === "VIOLATION";

      ctx.fillStyle = isViolation
        ? "rgba(225, 29, 72, 0.18)"
        : "rgba(16, 185, 129, 0.15)";
      ctx.fillRect(x, y, w, h);

      ctx.strokeStyle = isViolation ? "#e11d48" : "#059669";
      ctx.lineWidth = 3.5;
      ctx.strokeRect(x - 2, y - 2, w + 4, h + 4);
    });
  }, [imageObj, imageWidth, imageHeight, items, selectedField, hoveredField]);

  useEffect(() => {
    render();
  }, [render]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = imageWidth / rect.width;
    const scaleY = imageHeight / rect.height;

    const mouseX = (e.clientX - rect.left) * scaleX;
    const mouseY = (e.clientY - rect.top) * scaleY;

    const match = items.slice().reverse().find((item) => {
      const [x, y, w, h] = item.bbox;
      return mouseX >= x && mouseX <= x + w && mouseY >= y && mouseY <= y + h;
    });

    setHoveredField(match ? match.field : null);
  };

  return (
    <div className="relative w-full h-full min-h-[520px] bg-zinc-100 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden flex items-center justify-center p-4">
      {/* Viewport */}
      <div
        ref={containerRef}
        style={{
          transform: `scale(${scale})`,
          transformOrigin: "center center",
          transition: "transform 0.12s ease-out",
        }}
        className="max-h-full flex items-center justify-center"
      >
        <canvas
          ref={canvasRef}
          width={imageWidth}
          height={imageHeight}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredField(null)}
          onClick={() => onSelectField(hoveredField)}
          className="max-h-[60vh] w-auto h-auto cursor-pointer block rounded-lg shadow-sm border border-zinc-300 dark:border-zinc-700"
        />
      </div>

      {/* Subtle Floating Zoom Controls */}
      <div className="absolute bottom-3 right-3 flex items-center bg-white/90 dark:bg-zinc-900/90 backdrop-blur-xs border border-zinc-200 dark:border-zinc-800 rounded-lg p-1 shadow-xs text-xs font-mono">
        <button
          type="button"
          onClick={() => setScale((s) => Math.max(0.6, s - 0.15))}
          className="w-7 h-7 flex items-center justify-center text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded"
        >
          −
        </button>
        <span className="px-2 text-zinc-500 text-[11px]">
          {Math.round(scale * 100)}%
        </span>
        <button
          type="button"
          onClick={() => setScale((s) => Math.min(2.0, s + 0.15))}
          className="w-7 h-7 flex items-center justify-center text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded"
        >
          +
        </button>
      </div>
    </div>
  );
}
