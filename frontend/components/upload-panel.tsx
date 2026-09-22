"use client";

import { useState } from "react";
import { Upload, FileType, Layers, Map as MapIcon, Satellite } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export interface ImageMetadata {
  filename: string;
  format: string;
  crs: string;
  gsd_m: number | null;
  width: number;
  height: number;
  band_count: number;
  bounds: [number, number, number, number];
  sensor: string | null;
}

interface UploadPanelProps {
  onUploadSuccess: (jobId: string, metadata: ImageMetadata) => void;
  label?: string;
}

export function UploadPanel({ onUploadSuccess, label = "Input Source" }: UploadPanelProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Check size limit (e.g. 50MB)
    if (file.size > 50 * 1024 * 1024) {
      setError("File is too large. Please upload an image under 50MB.");
      return;
    }

    setError(null);
    setIsUploading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/ingest", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail?.message || data.detail || "Upload failed");
      }

      onUploadSuccess(data.image_id, data.metadata);
    } catch (err: any) {
      setError(err.message || "Failed to upload image.");
    } finally {
      setIsUploading(false);
      // Reset input
      e.target.value = '';
    }
  };

  return (
    <Card className="w-full border-border bg-card">
      <CardHeader>
        <CardTitle className="text-lg font-mono">{label}</CardTitle>
        <CardDescription>Upload a GeoTIFF or compatible raster image to begin analysis.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col items-center justify-center border-2 border-dashed border-border rounded-none p-12 text-center bg-muted/20">
          <Upload className="h-10 w-10 text-muted-foreground mb-4" />
          <h3 className="font-semibold text-foreground mb-1">Click to upload or drag and drop</h3>
          <p className="text-sm text-muted-foreground mb-4">GeoTIFF, PNG, JPEG (Max 50MB)</p>
          
          <div className="relative">
            <input 
              type="file" 
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" 
              onChange={handleFileChange}
              disabled={isUploading}
              accept=".tif,.tiff,.jpg,.jpeg,.png"
            />
            <Button disabled={isUploading} variant="secondary" className="pointer-events-none rounded-none border border-border">
              {isUploading ? "Uploading & Parsing..." : "Select File"}
            </Button>
          </div>
          
          {error && (
            <p className="text-destructive text-sm mt-4 font-mono">{error}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function MetadataPanel({ metadata, label = "Raster Metadata" }: { metadata: ImageMetadata, label?: string }) {
  return (
    <Card className="w-full border-border bg-card mt-4">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-mono text-muted-foreground tracking-wider uppercase">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm font-mono">
          <div>
            <span className="text-muted-foreground block text-xs">FILENAME</span>
            <span className="truncate block" title={metadata.filename}>{metadata.filename}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">FORMAT</span>
            <span>{metadata.format} ({metadata.width}x{metadata.height})</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">CRS</span>
            <span className="flex items-center gap-1">
              <MapIcon className="w-3 h-3" /> {metadata.crs}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">GSD (Resolution)</span>
            <span>{metadata.gsd_m ? `${metadata.gsd_m.toFixed(2)}m/px` : "Unknown"}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">BANDS</span>
            <span className="flex items-center gap-1">
              <Layers className="w-3 h-3" /> {metadata.band_count}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">SENSOR</span>
            <span className="flex items-center gap-1 text-primary">
              <Satellite className="w-3 h-3" /> {metadata.sensor || "Uncalibrated"}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
