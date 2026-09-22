"use client";

import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { ImageMetadata } from "./upload-panel";
import { Layers, Map as MapIcon, BoxSelect } from "lucide-react";

interface EvidenceViewerProps {
  metadata: ImageMetadata | null;
  jobId: string | null;
  trace: any | null;
}

export function EvidenceViewer({ metadata, jobId, trace }: EvidenceViewerProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const imageSourceAdded = useRef(false);

  const getSafeBounds = (bounds: number[]) => {
    let [minLon, minLat, maxLon, maxLat] = bounds;
    if (maxLon > 180 || minLon < -180 || maxLat > 90 || minLat < -90) {
      // Mock to a real area if un-georeferenced
      return [-122.5194, 37.6749, -122.3194, 37.8749]; 
    }
    return [minLon, minLat, maxLon, maxLat];
  };

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    // Initialize MapLibre
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json", // Dark basemap
      center: [0, 0],
      zoom: 1,
      attributionControl: false,
    });

    map.current.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

    map.current.on('load', () => {
      setMapLoaded(true);
    });

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Effect to handle bounds zooming when metadata changes
  useEffect(() => {
    if (!mapLoaded || !map.current || !metadata?.bounds) return;

    const [minLon, minLat, maxLon, maxLat] = getSafeBounds(metadata.bounds);
    
    // Fit bounds with animation
    map.current.fitBounds(
      [[minLon, minLat], [maxLon, maxLat]],
      { padding: 50, duration: 1000 }
    );
    
    const sourceId = "image-bounds";
    if (map.current.getSource(sourceId)) {
      (map.current.getSource(sourceId) as maplibregl.GeoJSONSource).setData({
        type: "Feature",
        geometry: {
          type: "Polygon",
          coordinates: [[
            [minLon, minLat],
            [maxLon, minLat],
            [maxLon, maxLat],
            [minLon, maxLat],
            [minLon, minLat]
          ]]
        },
        properties: {}
      });
    } else {
      map.current.addSource(sourceId, {
        type: "geojson",
        data: {
          type: "Feature",
          geometry: {
            type: "Polygon",
            coordinates: [[
              [minLon, minLat],
              [maxLon, minLat],
              [maxLon, maxLat],
              [minLon, maxLat],
              [minLon, minLat]
            ]]
          },
          properties: {}
        }
      });
      
      map.current.addLayer({
        id: "image-bounds-line",
        type: "line",
        source: sourceId,
        paint: {
          "line-color": "#06b6d4",
          "line-width": 2,
          "line-dasharray": [2, 2]
        }
      });
    }
    
  }, [mapLoaded, metadata]);

  // Effect to overlay preview image when trace gives us a url
  useEffect(() => {
    if (!mapLoaded || !map.current || !metadata?.bounds || !trace) return;
    
    const previewStep = trace.steps?.find((s: any) => s.tool_name === "preview" && s.status === "SUCCESS");
    if (!previewStep || !previewStep.outputs?.preview_url) return;
    
    const url = "http://localhost:8000" + previewStep.outputs.preview_url;
    const [minLon, minLat, maxLon, maxLat] = getSafeBounds(metadata.bounds);
    const coordinates = [
      [minLon, maxLat], // top left
      [maxLon, maxLat], // top right
      [maxLon, minLat], // bottom right
      [minLon, minLat]  // bottom left
    ];
    
    const sourceId = "preview-image";
    if (!map.current.getSource(sourceId)) {
      map.current.addSource(sourceId, {
        type: "image",
        url: url,
        coordinates: coordinates
      });
      
      map.current.addLayer({
        id: "preview-image-layer",
        type: "raster",
        source: sourceId,
        paint: {
          "raster-opacity": 0.85
        }
      }, "image-bounds-line"); // Insert below the bounds line
      
      imageSourceAdded.current = true;
    } else {
      (map.current.getSource(sourceId) as maplibregl.ImageSource).updateImage({
        url: url,
        coordinates: coordinates
      });
    }

    // Add Mask Overlays
    const addMaskLayer = (stepName: string, urlKey: string, sourcePrefix: string) => {
      const step = trace.steps?.find((s: any) => s.tool_name === stepName && s.status === "SUCCESS");
      if (step && step.outputs?.[urlKey]) {
        const maskUrl = "http://localhost:8000" + step.outputs[urlKey];
        const maskSourceId = `${sourcePrefix}-mask`;
        if (!map.current!.getSource(maskSourceId)) {
          map.current!.addSource(maskSourceId, {
            type: "image",
            url: maskUrl,
            coordinates: coordinates
          });
          map.current!.addLayer({
            id: `${maskSourceId}-layer`,
            type: "raster",
            source: maskSourceId,
            paint: { "raster-opacity": 0.8 }
          });
        } else {
          (map.current!.getSource(maskSourceId) as maplibregl.ImageSource).updateImage({
            url: maskUrl,
            coordinates: coordinates
          });
        }
      }
    };
    
    addMaskLayer("spectral_index", "mask_url", "index");
    addMaskLayer("changeformer", "change_mask_url", "change");

    // Add Grounding Boxes
    const groundStep = trace.steps?.find((s: any) => s.tool_name === "geochat_grounding" && s.status === "SUCCESS");
    if (groundStep && groundStep.outputs?.grounding_boxes) {
      const boxes = groundStep.outputs.grounding_boxes;
      const features = boxes.map((box: any, i: number) => {
        const xMinLon = minLon + box.x_min * (maxLon - minLon);
        const yMinLat = maxLat - box.y_min * (maxLat - minLat); // y_min is from top
        const xMaxLon = minLon + box.x_max * (maxLon - minLon);
        const yMaxLat = maxLat - box.y_max * (maxLat - minLat);

        return {
          type: "Feature",
          geometry: {
            type: "Polygon",
            coordinates: [[
              [xMinLon, yMinLat],
              [xMaxLon, yMinLat],
              [xMaxLon, yMaxLat],
              [xMinLon, yMaxLat],
              [xMinLon, yMinLat]
            ]]
          },
          properties: { label: box.label, confidence: box.confidence }
        };
      });

      const groundSourceId = "grounding-boxes";
      if (!map.current.getSource(groundSourceId)) {
        map.current.addSource(groundSourceId, {
          type: "geojson",
          data: { type: "FeatureCollection", features }
        });
        
        map.current.addLayer({
          id: `${groundSourceId}-fill`,
          type: "fill",
          source: groundSourceId,
          paint: {
            "fill-color": "#00ffff",
            "fill-opacity": 0.2
          }
        });

        map.current.addLayer({
          id: `${groundSourceId}-line`,
          type: "line",
          source: groundSourceId,
          paint: {
            "line-color": "#00ffff",
            "line-width": 2
          }
        });

        map.current.addLayer({
          id: `${groundSourceId}-label`,
          type: "symbol",
          source: groundSourceId,
          layout: {
            "text-field": ["get", "label"],
            "text-size": 12,
            "text-anchor": "top"
          },
          paint: {
            "text-color": "#00ffff",
            "text-halo-color": "#000",
            "text-halo-width": 1
          }
        });
      } else {
        (map.current.getSource(groundSourceId) as maplibregl.GeoJSONSource).setData({
          type: "FeatureCollection", features
        });
      }
    }
  }, [mapLoaded, metadata, trace]);

  return (
    <div className="relative w-full h-[600px] border border-border bg-card flex flex-col">
      {/* Top Header Bar */}
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-3 bg-card/80 backdrop-blur border-b border-border">
        <div className="flex items-center gap-2">
          <MapIcon className="w-4 h-4 text-primary" />
          <span className="text-sm font-mono text-muted-foreground uppercase tracking-wider">
            Spatial Evidence Viewer
          </span>
        </div>
        <div className="flex gap-2">
          {jobId && (
            <div className="flex items-center gap-1.5 px-2 py-1 bg-primary/10 border border-primary/20 rounded-none text-xs font-mono text-primary">
              <Layers className="w-3 h-3" />
              <span>Job Active</span>
            </div>
          )}
        </div>
      </div>

      {/* Map Container */}
      <div ref={mapContainer} className="w-full h-full" />
      
      {/* Overlay Status (Empty state) */}
      {!metadata && (
        <div className="absolute inset-0 z-0 flex items-center justify-center pointer-events-none">
          <div className="flex flex-col items-center gap-3 text-muted-foreground opacity-50">
            <BoxSelect className="w-12 h-12" />
            <p className="font-mono text-sm tracking-widest uppercase">Awaiting Raster Source</p>
          </div>
        </div>
      )}
    </div>
  );
}
