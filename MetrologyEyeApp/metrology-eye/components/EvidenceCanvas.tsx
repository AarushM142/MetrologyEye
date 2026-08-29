"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BBox, Finding, Severity } from "@/lib/types";

interface CanvasItem {
  id: string;
  field: string;
  severity: Severity;
  bbox: BBox;
  rule_id: string;
  message?: string;
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
  const [hoveredItem, setHoveredItem] = useState<CanvasItem | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  const items: CanvasItem[] = findings
    .filter((f): f is Finding & { bbox: BBox } => f.bbox !== null)
    .map((f, idx) => ({
      id: f.field || f.rule_id || `box-${idx}`,
      field: f.field || f.rule_id,
      severity: f.severity,
      bbox: f.bbox,
      rule_id: f.rule_id,
      message: f.message,
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

    // Clear canvas
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw background image
    ctx.drawImage(imageObj, 0, 0, imageWidth, imageHeight);

    // Helper: Draw BBox item
    const drawItem = (item: CanvasItem, isSelectedOrHovered: boolean) => {
      const [x, y, w, h] = item.bbox;
      const { severity } = item;

      ctx.save();
      ctx.setLineDash([]);

      if (isSelectedOrHovered) {
        // Highlighting effect
        if (severity === "VIOLATION") {
          ctx.fillStyle = "rgba(225, 29, 72, 0.22)";
          ctx.strokeStyle = "#e11d48";
        } else if (severity === "WARNING") {
          ctx.fillStyle = "rgba(217, 119, 6, 0.22)";
          ctx.strokeStyle = "#d97706";
        } else if (severity === "MANUAL_REQUIRED") {
          ctx.fillStyle = "rgba(100, 116, 139, 0.22)";
          ctx.strokeStyle = "#475569";
          ctx.setLineDash([6, 4]);
        } else {
          ctx.fillStyle = "rgba(16, 185, 129, 0.20)";
          ctx.strokeStyle = "#059669";
        }

        ctx.fillRect(x, y, w, h);
        ctx.lineWidth = 3.5;
        ctx.strokeRect(x - 2, y - 2, w + 4, h + 4);
      } else {
        // Normal item drawing
        if (severity === "VIOLATION") {
          ctx.fillStyle = "rgba(225, 29, 72, 0.10)";
          ctx.strokeStyle = "#e11d48";
          ctx.lineWidth = 2.5;
        } else if (severity === "WARNING") {
          ctx.fillStyle = "rgba(217, 119, 6, 0.10)";
          ctx.strokeStyle = "#d97706";
          ctx.lineWidth = 2.2;
        } else if (severity === "MANUAL_REQUIRED") {
          ctx.fillStyle = "rgba(100, 116, 139, 0.08)";
          ctx.strokeStyle = "#64748b";
          ctx.lineWidth = 2.0;
          ctx.setLineDash([5, 4]);
        } else {
          ctx.fillStyle = "rgba(16, 185, 129, 0.05)";
          ctx.strokeStyle = "rgba(16, 185, 129, 0.6)";
          ctx.lineWidth = 1.5;
        }

        ctx.fillRect(x, y, w, h);
        ctx.strokeRect(x, y, w, h);
      }

      ctx.restore();
    };

    // 1. Draw inactive items
    items.forEach((item) => {
      const isTarget =
        (selectedField && item.field === selectedField) ||
        (hoveredItem && item.field === hoveredItem.field);
      if (!isTarget) {
        drawItem(item, false);
      }
    });

    // 2. Draw selected/hovered item on top
    items.forEach((item) => {
      const isTarget =
        (selectedField && item.field === selectedField) ||
        (hoveredItem && item.field === hoveredItem.field);
      if (isTarget) {
        drawItem(item, true);
      }
    });
  }, [imageObj, imageWidth, imageHeight, items, selectedField, hoveredItem]);

  useEffect(() => {
    render();
  }, [render]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    // Translate mouse coordinates accounting for canvas element scaling
    const scaleX = imageWidth / rect.width;
    const scaleY = imageHeight / rect.height;

    const mouseX = (e.clientX - rect.left) * scaleX;
    const mouseY = (e.clientY - rect.top) * scaleY;

    setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });

    const match = items.slice().reverse().find((item) => {
      const [x, y, w, h] = item.bbox;
      return mouseX >= x && mouseX <= x + w && mouseY >= y && mouseY <= y + h;
    });

    setHoveredItem(match || null);
  };

  const handleMouseLeave = () => {
    setHoveredItem(null);
    setMousePos(null);
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
        className="max-h-full flex items-center justify-center relative"
      >
        <canvas
          ref={canvasRef}
          width={imageWidth}
          height={imageHeight}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onClick={() => onSelectField(hoveredItem ? hoveredItem.field : null)}
          className="max-h-[60vh] w-auto h-auto cursor-pointer block rounded-lg shadow-sm border border-zinc-300 dark:border-zinc-700"
        />

        {/* Hover Tooltip Overlay */}
        {hoveredItem && mousePos && (
          <div
            style={{
              left: `${mousePos.x + 12}px`,
              top: `${mousePos.y - 12}px`,
            }}
            className="absolute z-20 pointer-events-none bg-zinc-900/95 text-white dark:bg-zinc-100/95 dark:text-zinc-950 px-3 py-2 rounded-md shadow-lg text-xs backdrop-blur-xs max-w-xs space-y-1"
          >
            <div className="flex items-center justify-between gap-2 font-semibold">
              <span className="capitalize">{hoveredItem.field.replace("_", " ")}</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                  hoveredItem.severity === "VIOLATION"
                    ? "bg-rose-500 text-white"
                    : hoveredItem.severity === "WARNING"
                    ? "bg-amber-500 text-white"
                    : hoveredItem.severity === "MANUAL_REQUIRED"
                    ? "bg-slate-600 text-white"
                    : "bg-emerald-500 text-white"
                }`}
              >
                {hoveredItem.severity}
              </span>
            </div>
            {hoveredItem.message && (
              <p className="text-[11px] text-zinc-300 dark:text-zinc-700">
                {hoveredItem.message}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Floating Canvas Controls */}
      <div className="absolute bottom-3 right-3 flex items-center bg-white/90 dark:bg-zinc-900/90 backdrop-blur-xs border border-zinc-200 dark:border-zinc-800 rounded-lg p-1 shadow-xs text-xs font-mono space-x-1">
        <button
          type="button"
          onClick={() => setScale((s) => Math.max(0.5, s - 0.15))}
          title="Zoom out"
          className="w-7 h-7 flex items-center justify-center text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
        >
          −
        </button>
        <span className="px-2 text-zinc-600 dark:text-zinc-300 text-[11px]">
          {Math.round(scale * 100)}%
        </span>
        <button
          type="button"
          onClick={() => setScale((s) => Math.min(2.5, s + 0.15))}
          title="Zoom in"
          className="w-7 h-7 flex items-center justify-center text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
        >
          +
        </button>
        <button
          type="button"
          onClick={() => setScale(1.0)}
          title="Reset Zoom"
          className="px-2 h-7 flex items-center justify-center text-[10px] text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
        >
          Reset
        </button>
      </div>

      {/* Legend overlay */}
      <div className="absolute top-3 left-3 flex items-center space-x-3 bg-white/90 dark:bg-zinc-900/90 backdrop-blur-xs border border-zinc-200 dark:border-zinc-800 rounded-lg px-2.5 py-1.5 shadow-xs text-[11px]">
        <div className="flex items-center space-x-1">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />
          <span className="text-zinc-600 dark:text-zinc-400">Violation</span>
        </div>
        <div className="flex items-center space-x-1">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />
          <span className="text-zinc-600 dark:text-zinc-400">Warning</span>
        </div>
        <div className="flex items-center space-x-1">
          <span className="w-2.5 h-2.5 rounded-full bg-slate-500 inline-block" />
          <span className="text-zinc-600 dark:text-zinc-400">Manual</span>
        </div>
        <div className="flex items-center space-x-1">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
          <span className="text-zinc-600 dark:text-zinc-400">Compliant</span>
        </div>
      </div>
    </div>
  );
}
