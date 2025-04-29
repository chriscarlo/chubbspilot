# OSM Extractable Data Points (from PBF -> GeoJSON Lines)

This document lists common and relevant data points that can be extracted from an OpenStreetMap (OSM) planet extract (like `california-latest.osm.pbf`) after conversion to a GeoJSON Lines stream format. Data is grouped by GeoJSON geometry type and then by common OSM tags.

## POINT FEATURES (OSM Nodes -> GeoJSON `"type":"Point"`)

-   `highway=traffic_signals` – Mast or pole controlling an intersection (traffic light).
-   `highway=stop` – Physical stop sign position.
-   `highway=speed_camera` – Fixed speed-enforcement camera.
-   `traffic_sign=maxspeed` / `"maxspeed:*"` – Roadside speed-limit sign. Often the primary source for limits on minor roads.
-   `maxspeed=*` – Direct speed limit tag on the node itself.
-   `highway=bus_stop` / `railway=tram_stop` – Passenger boarding points.
-   `highway=crossing` – Pedestrian crossing or cross-walk.
-   `amenity=*` (fuel, school, hospital, etc.) – General points-of-interest (POIs).
-   `shop=*`, `tourism=*`, `leisure=*` – Retail locations, attractions, parks, etc.
-   `barrier=*` (gate, bollard, lift_gate) – Access control devices on roads or paths.
-   `natural=peak` / `ele=*` nodes – Mountain summits with elevation tags.
-   `man_made=survey_point` / `benchmark` – Known survey marks.

## LINESTRING FEATURES (OSM Open Ways -> GeoJSON `"type":"LineString"`)

-   `highway=*` (motorway, trunk, primary, secondary, tertiary, residential, service, etc.) – Road center-lines, essential for routing, curvature, and speed limit association.
-   `railway=*` (rail, light_rail, tram, subway, etc.) – Rail tracks.
-   `waterway=*` (river, stream, canal, drain) – Linear water features.
-   `power=line` / `power=cable` – Overhead transmission lines or undersea/underground cables.
-   `pipeline=*` – Oil, gas, or water pipelines.
-   `aerialway=*` – Gondolas, chairlifts, etc.
-   `boundary=administrative` (when stored as an open way segment).
-   `route=ferry` – Path of a ferry over water.
-   `natural=coastline` – The outline of the land meeting the sea (always a LineString in OSM).
-   `cycleway=lane` / `footway=sidewalk` (sometimes mapped as separate ways parallel to roads).

## POLYGON / MULTIPOLYGON FEATURES (OSM Closed Ways or Relations -> GeoJSON `"type":"Polygon"`/`"MultiPolygon"`)

-   `building=*` – Footprint of a building (may have `building:part`, `levels`, `height` tags).
-   `landuse=*` (residential, commercial, industrial, forest, farmland, meadow, etc.) – Area land use classification.
-   `natural=*` (water, wood, wetland, beach, grassland, scrub, etc.) – Natural land cover areas.
-   `leisure=*` (park, golf_course, stadium, swimming_pool, pitch, garden, etc.) – Recreational areas.
-   `amenity=*` areas (parking, school, university, hospital grounds, etc.) – Areas associated with amenities.
-   `boundary=administrative` – City, county, state borders; maritime limits.
-   `boundary=national_park` / `protected_area` – National/State Parks, Wilderness areas, etc.
-   `place=*` polygons (city, town, suburb, neighborhood, hamlet) – Labeled populated place areas.
-   `highway=services` / `rest_area` – Polygonal outline of roadside service or rest areas.
-   `man_made=pier` / `breakwater` – Coastal or waterfront constructions.

## RELATION-ONLY LAYERS (OSM Relations -> Represent relationships, often complex geometries)

*Note: These often don't map directly to a *single* GeoJSON geometry but describe how members (nodes, ways, other relations) connect.*

-   `type=multipolygon` – Defines complex areas with holes or multiple disjoint parts (e.g., lakes with islands, buildings with courtyards). Members are ways tagged `outer` or `inner`.
-   `type=route` + `route=*` (road, bus, train, tram, bicycle, hiking, etc.) – Defines an ordered sequence of way segments forming a named or numbered route.
-   `type=boundary` + `boundary=administrative` – Defines administrative boundaries composed of multiple way segments.
-   `type=restriction` (e.g., `restriction=no_left_turn`) – Defines turn restrictions at junctions. Members include `from` way, `to` way, and `via` node/way.
-   `type=enforcement` – Groups enforcement devices (like speed cameras) with the road sections they monitor.
-   `type=public_transport` (stop_area, stop_area_group) – Groups related public transport stops and platforms.
-   `type=street` – Logically groups segments of the same named street that might be drawn as separate ways.
-   `type=waterway` + `waterway=river` – Groups multiple way segments forming a complete river.

## SPECIAL-PURPOSE TAGS (Found on various geometries, critical for specific applications)

-   `maxspeed=*` (on Points or LineStrings) – Posted speed limit (numeric value in km/h, or text like "35 mph").
-   `lanes=*`, `lanes:forward=*`, `lanes:backward=*` (on LineStrings) – Number of traffic lanes.
-   `width=*`, `est_width=*` (on LineStrings) – Width of the carriageway.
-   `oneway=yes`/`no`/`-1` (on LineStrings) – Indicates direction of travel allowed (yes=same as way direction, -1=opposite, no=both).
-   `surface=*` (on LineStrings) – Type of road surface (e.g., `asphalt`, `concrete`, `gravel`, `unpaved`).
-   `incline=*`, `ramp=*` (on LineStrings/Points) – Indicates gradient or presence of a ramp.
-   `curvature` (Derived) – Not an OSM tag itself, but calculated from the geometry of LineStrings. Essential for speed prediction.

## OSM Geometry Summary (Typical Volume for California Extract)

| GeoJSON Geometry | OSM Primitive | Est. Count (California) | Description                       |
| :--------------- | :------------ | :---------------------- | :-------------------------------- |
| Point            | Node          | ~60 Million             | POIs, signs, traffic lights, etc. |
| LineString       | Open Way      | ~7 Million              | Roads, rails, rivers, borders     |
| Polygon          | Closed Way/MP | ~4 Million              | Buildings, landuse, lakes         |
| (Relation Data)  | Relation      | ~400 Thousand           | Routes, restrictions, boundaries  |