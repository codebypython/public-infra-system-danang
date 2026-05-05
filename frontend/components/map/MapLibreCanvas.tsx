"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import maplibregl, {
  type Map as MapLibreMap,
  type MapMouseEvent,
  type StyleSpecification,
} from "maplibre-gl";
import {
  type CSSProperties,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { ASSET_TYPE_MAP, ASSET_TYPES, config } from "@/lib/config";

type AssetFeatureProps = {
  id: string;
  code: string | null;
  name: string;
  asset_type: string;
  status: string;
  area_id: string | null;
};

export type MapAsset = {
  id: string;
  code: string | null;
  name: string;
  asset_type: string;
  status: string;
  lng: number;
  lat: number;
  area_id: string | null;
};

export type MapReport = {
  id: string;
  code: string;
  status: string;
  severity: string;
  incident_type: string | null;
  lng: number;
  lat: number;
};

type Props = {
  assets?: MapAsset[];
  reports?: MapReport[];
  onClickMap?: (lng: number, lat: number) => void;
  onClickAsset?: (asset: MapAsset) => void;
  onClickReport?: (report: MapReport) => void;
  onBboxChange?: (bbox: [number, number, number, number]) => void;
  pitch?: number;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
};

const DEFAULT_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
      maxzoom: 19,
    },
  },
  layers: [
    {
      id: "osm",
      type: "raster",
      source: "osm",
      minzoom: 0,
      maxzoom: 22,
    },
  ],
};

export default function MapLibreCanvas({
  assets = [],
  reports = [],
  onClickMap,
  onClickAsset,
  onClickReport,
  onBboxChange,
  pitch = 45,
  className,
  style,
  children,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);

  /* Initialise once */
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const styleSpec = config.maptilerKey
      ? `https://api.maptiler.com/maps/streets-v2/style.json?key=${config.maptilerKey}`
      : (DEFAULT_STYLE as unknown as StyleSpecification);

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: styleSpec as any,
      center: [config.defaultCenter.lng, config.defaultCenter.lat],
      zoom: config.defaultZoom,
      pitch,
      bearing: -10,
      attributionControl: { compact: true },
      maxBounds: [
        [107.85, 15.85],
        [108.55, 16.30],
      ],
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: true,
      }),
      "top-right"
    );
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: "metric" }));

    map.on("load", () => {
      // Sources for assets + reports
      map.addSource("assets", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      });
      map.addSource("reports", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      map.addLayer({
        id: "asset-clusters",
        type: "circle",
        source: "assets",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": "#3b82f6",
          "circle-radius": [
            "step",
            ["get", "point_count"],
            16,
            10,
            20,
            50,
            26,
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
          "circle-opacity": 0.85,
        },
      });
      map.addLayer({
        id: "asset-cluster-count",
        type: "symbol",
        source: "assets",
        filter: ["has", "point_count"],
        layout: {
          "text-field": "{point_count_abbreviated}",
          "text-size": 12,
        },
        paint: { "text-color": "#ffffff" },
      });
      map.addLayer({
        id: "asset-points",
        type: "circle",
        source: "assets",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": [
            "match",
            ["get", "asset_type"],
            ...ASSET_TYPES.flatMap((t) => [t.value, t.color]),
            "#9ca3af",
          ],
          "circle-radius": 7,
          "circle-stroke-width": 2,
          "circle-stroke-color": [
            "case",
            ["==", ["get", "status"], "active"],
            "#16a34a",
            ["==", ["get", "status"], "damaged"],
            "#ef4444",
            ["==", ["get", "status"], "maintenance"],
            "#eab308",
            "#94a3b8",
          ],
        },
      });
      map.addLayer({
        id: "report-points",
        type: "circle",
        source: "reports",
        paint: {
          "circle-color": [
            "match",
            ["get", "severity"],
            "low",
            "#22c55e",
            "medium",
            "#eab308",
            "high",
            "#f97316",
            "urgent",
            "#ef4444",
            "#94a3b8",
          ],
          "circle-radius": 9,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      setReady(true);
    });

    map.on("click", "asset-points", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const props = f.properties as AssetFeatureProps;
      const coords = (f.geometry as any).coordinates as [number, number];
      onClickAsset?.({
        id: props.id,
        code: props.code,
        name: props.name,
        asset_type: props.asset_type,
        status: props.status,
        area_id: props.area_id,
        lng: coords[0],
        lat: coords[1],
      });
    });
    map.on("click", "report-points", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const props: any = f.properties;
      const coords = (f.geometry as any).coordinates as [number, number];
      onClickReport?.({ ...props, lng: coords[0], lat: coords[1] });
    });
    map.on("click", "asset-clusters", (e) => {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ["asset-clusters"],
      });
      if (!features.length) return;
      const cid = (features[0].properties as any).cluster_id;
      const src = map.getSource("assets") as any;
      src.getClusterExpansionZoom(cid).then((zoom: number) => {
        map.easeTo({
          center: (features[0].geometry as any).coordinates,
          zoom,
        });
      });
    });

    map.on("mouseenter", "asset-points", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "asset-points", () => (map.getCanvas().style.cursor = ""));
    map.on("mouseenter", "report-points", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "report-points", () => (map.getCanvas().style.cursor = ""));

    map.on("click", (e: MapMouseEvent) => {
      // Ignore if it hit a feature layer
      const layers = ["asset-points", "report-points", "asset-clusters"];
      const features = map.queryRenderedFeatures(e.point, { layers });
      if (features.length === 0) {
        onClickMap?.(e.lngLat.lng, e.lngLat.lat);
      }
    });

    map.on("moveend", () => {
      const b = map.getBounds();
      onBboxChange?.([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Update assets layer */
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const src = mapRef.current.getSource("assets") as any;
    if (!src) return;
    src.setData({
      type: "FeatureCollection",
      features: assets.map((a) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [a.lng, a.lat] },
        properties: {
          id: a.id,
          code: a.code,
          name: a.name,
          asset_type: a.asset_type,
          status: a.status,
          area_id: a.area_id,
        },
      })),
    });
  }, [assets, ready]);

  /* Update reports layer */
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const src = mapRef.current.getSource("reports") as any;
    if (!src) return;
    src.setData({
      type: "FeatureCollection",
      features: reports.map((r) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [r.lng, r.lat] },
        properties: {
          id: r.id,
          code: r.code,
          status: r.status,
          severity: r.severity,
          incident_type: r.incident_type,
        },
      })),
    });
  }, [reports, ready]);

  return (
    <div
      className={className}
      style={{ position: "relative", width: "100%", height: "100%", ...style }}
    >
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      {children}
    </div>
  );
}
