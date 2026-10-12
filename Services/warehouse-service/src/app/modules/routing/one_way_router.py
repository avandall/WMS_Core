"""Generate picking route tool — Warehouse Aisle Graph & S-Shape Routing (TASK-046 / ALG-02)"""

import logging
from typing import Dict, Any, List, Optional, Tuple
try:
    from app.tools.base import BaseTool, ToolResult
    from app.clients.database_client import DatabaseClient
    from app.utils.validators import validate_order_id
    from app.utils.error_handlers import handle_tool_error
except ImportError:
    DatabaseClient = None
    class BaseTool:
        def __init__(self, config=None):
            self.config = config
    class ToolResult:
        def __init__(self, success=True, data=None, error=None, error_code=None):
            self.success = success
            self.data = data
            self.error = error
            self.error_code = error_code
    validate_order_id = None
    handle_tool_error = None

logger = logging.getLogger(__name__)


class GeneratePickingRouteInput(BaseModel):
    """Input schema for generate_picking_route"""
    order_id: str = Field(..., description="Order ID")
    max_cart_capacity_kg: float = Field(default=60.0, description="Max cart payload capacity in kg (default 60kg)")
    routing_mode: str = Field(default="aisle_graph", description="Routing mode: 'aisle_graph' (S-Shape & Aisle Manhattan) or 'euclidean'")
    aisle_length_y: float = Field(default=50.0, description="Aisle length in meters along Y axis (default 50m)")
    cross_aisle_front_y: float = Field(default=0.0, description="Front cross-aisle Y coordinate")
    cross_aisle_back_y: float = Field(default=50.0, description="Back cross-aisle Y coordinate")
    enforce_one_way: bool = Field(
        default=True,
        description="Enforce one-way aisle traffic rule (Odd aisles: Y ASC Front->Back, Even aisles: Y DESC Back->Front) (TASK-066 / DOM-01)"
    )
    is_batch_pick: bool = Field(
        default=False,
        description="Flag indicating whether this order is a batch picking wave requiring Put-Wall sortation (TASK-069 / DOM-04)"
    )
    sortation_wall_x: float = Field(
        default=0.0,
        description="X coordinate of Put-Wall sortation station"
    )
    sortation_wall_y: float = Field(
        default=10.0,
        description="Y coordinate of Put-Wall sortation station"
    )


class GeneratePickingRoute(BaseTool):
    """Generate optimized picking route using Warehouse Aisle Graph and S-Shape Heuristic"""
    
    name = "generate_picking_route"
    description = (
        "Warehouse Aisle Graph Routing: avoids walking through steel racks by routing through cross-aisles, "
        "implements S-Shape (Serpentine) heuristic from Cart Depot to Pack Station, and handles multi-trip cart capacity."
    )
    
    def __init__(self, config=None):
        super().__init__(config)
        self.db = DatabaseClient(config) if DatabaseClient else None
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Get input schema"""
        return {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID"
                },
                "max_cart_capacity_kg": {
                    "type": "number",
                    "description": "Maximum cart payload in kg",
                    "default": 60.0
                },
                "routing_mode": {
                    "type": "string",
                    "enum": ["aisle_graph", "euclidean"],
                    "description": "Routing algorithm mode",
                    "default": "aisle_graph"
                },
                "enforce_one_way": {
                    "type": "boolean",
                    "description": "Enforce one-way aisle traffic rule (Odd aisles: Y ASC Front->Back, Even aisles: Y DESC Back->Front)",
                    "default": True
                },
                "is_batch_pick": {
                    "type": "boolean",
                    "description": "Flag indicating whether this order is a batch picking wave requiring Put-Wall sortation",
                    "default": False
                },
                "sortation_wall_x": {
                    "type": "number",
                    "description": "X coordinate of Put-Wall sortation station",
                    "default": 0.0
                },
                "sortation_wall_y": {
                    "type": "number",
                    "description": "Y coordinate of Put-Wall sortation station",
                    "default": 10.0
                }
            },
            "required": ["order_id"]
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute picking route generation"""
        try:
            input_data = GeneratePickingRouteInput(**kwargs)
            validate_order_id(input_data.order_id)
            
            await self.db.connect()
            
            # Fetch order items with location coordinates
            items_with_locations = await self.db.fetch_many("SELECT order_items", input_data.order_id)
            
            if not items_with_locations:
                doc = await self.db._grpc_client.get_document(input_data.order_id)
                locs = await self.db._grpc_client.get_inventory_locations()
                
                if doc and doc.get("items"):
                    items_with_locations = []
                    for idx, item in enumerate(doc["items"]):
                        loc = locs[idx % len(locs)] if locs else {}
                        prod_id = item.get("product_id", 1)
                        prod_info = await self.db._grpc_client.get_product(prod_id)
                        item_weight = prod_info.get("weight", 1.5) if prod_info else 1.5
                        qty = item.get("quantity", 1)
                        
                        # Structured Aisle & Bay coordinates
                        aisle_num = (idx // 4) + 1
                        bay_num = (idx % 4) + 1
                        x_coord = float(loc.get("x_coordinate", aisle_num * 3.0))
                        y_coord = float(loc.get("y_coordinate", bay_num * 10.0))
                        
                        items_with_locations.append({
                            "sku_code": item.get("sku_code", f"SKU-{prod_id}"),
                            "quantity": qty,
                            "weight_kg": item_weight,
                            "total_weight_kg": item_weight * qty,
                            "location_code": loc.get("location_code", f"ZONE-A-AISLE-{aisle_num:02d}-BAY-{bay_num:02d}"),
                            "zone_id": loc.get("zone_id", "ZONE-A"),
                            "aisle": f"AISLE-{aisle_num:02d}",
                            "row_id": loc.get("row_id", f"ROW-{aisle_num:02d}"),
                            "shelf_id": loc.get("shelf_id", f"SHELF-{bay_num:02d}"),
                            "x_coordinate": x_coord,
                            "y_coordinate": y_coord,
                            "z_coordinate": loc.get("z_coordinate", 1.0)
                        })
            
            await self.db.disconnect()
            
            if not items_with_locations:
                return ToolResult(
                    success=False,
                    error=f"No items with available stock found for order: {input_data.order_id}",
                    error_code="NOT_FOUND"
                )
            
            # Ensure total_weight_kg is present on all items
            for it in items_with_locations:
                if "total_weight_kg" not in it:
                    w = it.get("weight_kg", it.get("weight", 1.0))
                    q = it.get("quantity", 1)
                    it["total_weight_kg"] = float(w) * float(q)
            
            # Legacy Euclidean Mode Support
            if input_data.routing_mode == "euclidean":
                return self._execute_legacy_euclidean(input_data.order_id, items_with_locations)
            
            # 1. Check Cart Payload Capacity & Partition Multi-Trip Routes
            trips = self._partition_trips_by_cart_capacity(
                items_with_locations,
                max_capacity_kg=input_data.max_cart_capacity_kg
            )
            
            # 2. Build S-Shape Route for each Trip (Depot -> S-Shape Stops -> Pack Station)
            trip_results = []
            all_stops_flattened = []
            total_route_distance = 0.0
            
            for trip_idx, trip_items in enumerate(trips, 1):
                trip_route, trip_distance = self._build_s_shape_trip(
                    trip_items=trip_items,
                    aisle_length_y=input_data.aisle_length_y,
                    cross_front_y=input_data.cross_aisle_front_y,
                    cross_back_y=input_data.cross_aisle_back_y,
                    enforce_one_way=input_data.enforce_one_way,
                    is_batch_pick=input_data.is_batch_pick,
                    sortation_wall_x=input_data.sortation_wall_x,
                    sortation_wall_y=input_data.sortation_wall_y,
                )
                
                trip_weight = sum(item["total_weight_kg"] for item in trip_items)
                total_route_distance += trip_distance
                
                trip_data = {
                    "trip_number": trip_idx,
                    "total_weight_kg": round(trip_weight, 2),
                    "stops_count": len(trip_route),
                    "trip_distance_m": round(trip_distance, 2),
                    "route": trip_route,
                    "instructions": self._generate_trip_instructions(trip_idx, trip_route, trip_items)
                }
                trip_results.append(trip_data)
                
                # Exclude DEPOT, SORTATION_WALL and PACK-STATION from purely unique item stops in optimized_route
                for st in trip_route:
                    if st.get("type") == "PICK":
                        all_stops_flattened.append(st)
            
            # Aggregate metrics
            unique_locations = self._get_unique_locations(items_with_locations)
            estimated_time_sec = total_route_distance * 1.0  # ~1 m/s walking speed
            
            route_metrics = {
                "total_distance_m": round(total_route_distance, 2),
                "estimated_time_seconds": round(estimated_time_sec, 2),
                "estimated_time_minutes": round(estimated_time_sec / 60.0, 2),
                "location_count": len(unique_locations),
                "total_trips": len(trips),
                "multi_trip_required": len(trips) > 1,
                "cart_capacity_kg": input_data.max_cart_capacity_kg,
                "enforce_one_way": input_data.enforce_one_way,
                "is_batch_pick": input_data.is_batch_pick,
                "has_sortation_wall": input_data.is_batch_pick,
                "routing_algorithm": "S-Shape (Serpentine) Heuristic on Aisle Graph"
            }
            
            return ToolResult(
                success=True,
                data={
                    "order_id": input_data.order_id,
                    "total_items": len(items_with_locations),
                    "unique_locations": len(unique_locations),
                    "multi_trip": len(trips) > 1,
                    "trips": trip_results,
                    "optimized_route": all_stops_flattened,
                    "route_metrics": route_metrics,
                    "picking_instructions": self._flatten_all_instructions(trip_results)
                }
            )
            
        except Exception as e:
            return handle_tool_error(e, self.name)
            
    def _execute_legacy_euclidean(self, order_id: str, items: List[Dict[str, Any]]) -> ToolResult:
        """Fallback for legacy tests expecting Euclidean TSP"""
        unique_locations = self._get_unique_locations(items)
        if not unique_locations:
            return ToolResult(success=True, data={"order_id": order_id, "optimized_route": []})
        
        unvisited = unique_locations.copy()
        route = [unvisited.pop(0)]
        while unvisited:
            curr = route[-1]
            nearest = min(unvisited, key=lambda loc: ((curr["x"] - loc["x"])**2 + (curr["y"] - loc["y"])**2 + (curr["z"] - loc["z"])**2)**0.5)
            route.append(nearest)
            unvisited.remove(nearest)
            
        total_dist = 0.0
        for i in range(len(route) - 1):
            c1, c2 = route[i], route[i+1]
            total_dist += ((c1["x"] - c2["x"])**2 + (c1["y"] - c2["y"])**2 + (c1["z"] - c2["z"])**2)**0.5
            
        return ToolResult(
            success=True,
            data={
                "order_id": order_id,
                "total_items": len(items),
                "unique_locations": len(unique_locations),
                "optimized_route": route,
                "route_metrics": {
                    "total_distance_m": round(total_dist, 2),
                    "estimated_time_seconds": round(total_dist, 2),
                    "estimated_time_minutes": round(total_dist / 60, 2),
                    "location_count": len(route)
                },
                "picking_instructions": self._generate_legacy_instructions(route, items)
            }
        )

    def _partition_trips_by_cart_capacity(
        self,
        items: List[Dict[str, Any]],
        max_capacity_kg: float = 60.0
    ) -> List[List[Dict[str, Any]]]:
        """
        Group order items into trips so that total weight per trip <= max_capacity_kg.
        If an individual item unit > max_capacity_kg, it gets its own single dedicated trip.
        """
        trips: List[List[Dict[str, Any]]] = []
        current_trip: List[Dict[str, Any]] = []
        current_weight = 0.0
        
        for item in items:
            it_weight = item.get("total_weight_kg", 0.0)
            
            # If adding this item exceeds cart capacity and current trip is not empty, start new trip
            if current_weight + it_weight > max_capacity_kg and current_trip:
                trips.append(current_trip)
                current_trip = [item]
                current_weight = it_weight
            else:
                current_trip.append(item)
                current_weight += it_weight
                
        if current_trip:
            trips.append(current_trip)
            
        return trips if trips else [items]
        
    @staticmethod
    def _determine_aisle_number(picks: List[Dict[str, Any]], aisle_idx: int, aisle_x: float) -> int:
        """
        Determines the physical aisle number (1-indexed) for One-Way Aisle Rules (TASK-066 / DOM-01).
        Checks explicit aisle/location code, falls back to spacing or sorted index.
        """
        import re
        for p in picks:
            for field in ["aisle", "row_id", "location_code"]:
                val = str(p.get(field, "") or "")
                m = re.search(r'(?:AISLE|ROW)[_-]?0*(\d+)', val, re.IGNORECASE)
                if m:
                    return int(m.group(1))
                m2 = re.search(r'[-_]A0*(\d+)[-_]', val, re.IGNORECASE)
                if m2:
                    return int(m2.group(1))

        if aisle_x > 0:
            estimated = round(aisle_x / 3.0)
            if abs(aisle_x - estimated * 3.0) < 0.2 and estimated >= 1:
                return int(estimated)

        return aisle_idx + 1

    def _build_s_shape_trip(
        self,
        trip_items: List[Dict[str, Any]],
        aisle_length_y: float = 50.0,
        cross_front_y: float = 0.0,
        cross_back_y: float = 50.0,
        enforce_one_way: bool = True,
        is_batch_pick: bool = False,
        sortation_wall_x: float = 0.0,
        sortation_wall_y: float = 10.0,
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Build an S-Shape (Serpentine) picking route for a trip:
        Depot (0, 0) -> S-Shape traversal of aisles with picks -> Pack Station (0, 0).
        When enforce_one_way=True, strictly enforces:
          - Odd aisles (1, 3, ...): Y ASCENDING (Front -> Back)
          - Even aisles (2, 4, ...): Y DESCENDING (Back -> Front)
        Returns: (route_stops, total_distance)
        """
        # Group unique pick locations by aisle (keyed by X coordinate)
        loc_map: Dict[str, Dict[str, Any]] = {}
        for it in trip_items:
            code = it.get("location_code")
            if code not in loc_map:
                loc_map[code] = {
                    "location_code": code,
                    "zone_id": it.get("zone_id", "ZONE-A"),
                    "aisle": it.get("aisle", ""),
                    "row_id": it.get("row_id", ""),
                    "shelf_id": it.get("shelf_id", ""),
                    "x": float(it.get("x_coordinate", 0.0)),
                    "y": float(it.get("y_coordinate", 0.0)),
                    "z": float(it.get("z_coordinate", 1.0)),
                    "type": "PICK"
                }
        
        # Group by x coordinate (Aisles)
        aisle_dict: Dict[float, List[Dict[str, Any]]] = {}
        for loc in loc_map.values():
            x = loc["x"]
            if x not in aisle_dict:
                aisle_dict[x] = []
            aisle_dict[x].append(loc)
            
        sorted_aisles = sorted(aisle_dict.keys())
        
        # Route starts at Cart Depot
        depot_stop = {
            "stop_number": 1,
            "location_code": "DEPOT",
            "zone_id": "STATION",
            "type": "DEPOT",
            "x": 0.0,
            "y": cross_front_y,
            "z": 0.0,
            "instruction": "Depart from Cart Depot with empty picking cart."
        }
        
        route: List[Dict[str, Any]] = [depot_stop]
        total_distance = 0.0
        
        # Current position
        curr_x = 0.0
        curr_y = cross_front_y
        stop_counter = 2
        
        for i, aisle_x in enumerate(sorted_aisles):
            picks_in_aisle = aisle_dict[aisle_x]
            is_last_aisle = (i == len(sorted_aisles) - 1)
            
            if enforce_one_way:
                aisle_num = self._determine_aisle_number(picks_in_aisle, i, aisle_x)
                is_odd_aisle = (aisle_num % 2 != 0)

                if is_odd_aisle:
                    # Odd Aisle (Dãy lẻ): Traffic MUST flow Front -> Back (Y ASCENDING: Y1 <= Y2 <= ...)
                    sorted_picks = sorted(picks_in_aisle, key=lambda p: p["y"])
                    target_entry_y = cross_front_y
                    target_exit_y = cross_back_y
                else:
                    # Even Aisle (Dãy chẵn): Traffic MUST flow Back -> Front (Y DESCENDING: Y1 >= Y2 >= ...)
                    sorted_picks = sorted(picks_in_aisle, key=lambda p: p["y"], reverse=True)
                    target_entry_y = cross_back_y
                    target_exit_y = cross_front_y

                # Walk along cross-aisle or perimeter to enter at target_entry_y
                if curr_y != target_entry_y:
                    # Transition between different corridor ends (Front <-> Back)
                    # Generate safe perimeter/cross-aisle waypoints so AGV/picker doesn't cut through racks or drive against traffic (DOM-04 / TASK-085)
                    perimeter_x = max(sorted_aisles) + 2.0 if sorted_aisles else aisle_x + 2.0

                    # Waypoint 1: Current corridor exit
                    wp1_loc = "CORRIDOR-FRONT" if curr_y == cross_front_y else "CORRIDOR-BACK"
                    wp1 = {
                        "stop_number": stop_counter,
                        "location_code": wp1_loc,
                        "zone_id": "CORRIDOR",
                        "type": "WAYPOINT",
                        "is_waypoint": True,
                        "x": curr_x,
                        "y": curr_y,
                        "z": 0.0,
                        "instruction": f"Move to {'Front' if curr_y == cross_front_y else 'Back'} cross-aisle corridor."
                    }
                    stop_counter += 1
                    route.append(wp1)

                    # Waypoint 2: Outer perimeter bypass corridor
                    wp2 = {
                        "stop_number": stop_counter,
                        "location_code": "CORRIDOR-PERIMETER",
                        "zone_id": "CORRIDOR",
                        "type": "WAYPOINT",
                        "is_waypoint": True,
                        "x": perimeter_x,
                        "y": target_entry_y,
                        "z": 0.0,
                        "instruction": f"Navigate via outer perimeter corridor to {'Back' if target_entry_y == cross_back_y else 'Front'} entrance."
                    }
                    stop_counter += 1
                    route.append(wp2)

                    # Waypoint 3: Entry point at target aisle
                    wp3 = {
                        "stop_number": stop_counter,
                        "location_code": f"CORRIDOR-ENTRY-AISLE-{aisle_num:02d}",
                        "zone_id": "CORRIDOR",
                        "type": "WAYPOINT",
                        "is_waypoint": True,
                        "x": aisle_x,
                        "y": target_entry_y,
                        "z": 0.0,
                        "instruction": f"Enter Aisle {aisle_num:02d} safely at designated one-way entrance."
                    }
                    stop_counter += 1
                    route.append(wp3)

                    # Travel along perimeter bypass
                    cross_travel = abs(perimeter_x - curr_x) + abs(target_entry_y - curr_y) + abs(aisle_x - perimeter_x)
                    total_distance += cross_travel
                    curr_x = aisle_x
                    curr_y = target_entry_y
                else:
                    cross_travel = abs(aisle_x - curr_x)
                    total_distance += cross_travel
                    curr_x = aisle_x
                    curr_y = target_entry_y

                # Pick items along the mandatory one-way direction
                for p in sorted_picks:
                    dist_to_pick = abs(p["y"] - curr_y)
                    total_distance += dist_to_pick
                    curr_y = p["y"]
                    p_copy = p.copy()
                    p_copy["stop_number"] = stop_counter
                    stop_counter += 1
                    route.append(p_copy)

                # Exit the aisle in the mandatory direction
                if not is_last_aisle:
                    dist_to_exit = abs(target_exit_y - curr_y)
                    total_distance += dist_to_exit
                    curr_y = target_exit_y
                else:
                    # Last aisle: proceed to nearest cross-aisle to reach pack station
                    dist_to_front = abs(curr_y - cross_front_y)
                    dist_to_back = abs(cross_back_y - curr_y)
                    if dist_to_front <= dist_to_back:
                        total_distance += dist_to_front
                        curr_y = cross_front_y
                    else:
                        total_distance += dist_to_back
                        curr_y = cross_back_y
            else:
                # Determine entry cross-aisle: if curr_y near front, enter from front; if near back, enter from back
                at_front = abs(curr_y - cross_front_y) <= abs(curr_y - cross_back_y)
                
                # Walk along cross-aisle to the current aisle
                cross_travel = abs(aisle_x - curr_x)
                total_distance += cross_travel
                curr_x = aisle_x
                
                if at_front:
                    # Moving forward: sort picks by Y ASC
                    sorted_picks = sorted(picks_in_aisle, key=lambda p: p["y"])
                    for p in sorted_picks:
                        dist_to_pick = abs(p["y"] - curr_y)
                        total_distance += dist_to_pick
                        curr_y = p["y"]
                        p_copy = p.copy()
                        p_copy["stop_number"] = stop_counter
                        stop_counter += 1
                        route.append(p_copy)
                    
                    # If not last aisle, traverse through to back cross-aisle
                    if not is_last_aisle:
                        dist_to_exit = abs(cross_back_y - curr_y)
                        total_distance += dist_to_exit
                        curr_y = cross_back_y
                    else:
                        # Last aisle: return to nearest cross-aisle to reach pack station
                        dist_to_front = abs(curr_y - cross_front_y)
                        dist_to_back = abs(cross_back_y - curr_y)
                        if dist_to_front <= dist_to_back:
                            total_distance += dist_to_front
                            curr_y = cross_front_y
                        else:
                            total_distance += dist_to_back
                            curr_y = cross_back_y
                else:
                    # Moving backward: sort picks by Y DESC
                    sorted_picks = sorted(picks_in_aisle, key=lambda p: p["y"], reverse=True)
                    for p in sorted_picks:
                        dist_to_pick = abs(curr_y - p["y"])
                        total_distance += dist_to_pick
                        curr_y = p["y"]
                        p_copy = p.copy()
                        p_copy["stop_number"] = stop_counter
                        stop_counter += 1
                        route.append(p_copy)
                        
                    # If not last aisle, traverse through to front cross-aisle
                    if not is_last_aisle:
                        dist_to_exit = abs(curr_y - cross_front_y)
                        total_distance += dist_to_exit
                        curr_y = cross_front_y
                    else:
                        # Last aisle: return to nearest cross-aisle
                        dist_to_front = abs(curr_y - cross_front_y)
                        dist_to_back = abs(cross_back_y - curr_y)
                        if dist_to_front <= dist_to_back:
                            total_distance += dist_to_front
                            curr_y = cross_front_y
                        else:
                            total_distance += dist_to_back
                            curr_y = cross_back_y
        
        # Conclude at Pack Station (at 0, cross_front_y)
        pack_station_x = 0.0
        pack_station_y = cross_front_y
        
        # If batch picking wave: route via SORTATION_WALL before final PACK-STATION (TASK-069 / DOM-04)
        if is_batch_pick:
            dist_to_sortation = abs(curr_x - sortation_wall_x) + abs(curr_y - sortation_wall_y)
            total_distance += dist_to_sortation
            curr_x = sortation_wall_x
            curr_y = sortation_wall_y
            
            sort_stop = {
                "stop_number": stop_counter,
                "location_code": "SORTATION_WALL",
                "zone_id": "SORTATION",
                "type": "SORTATION_WALL",
                "x": sortation_wall_x,
                "y": sortation_wall_y,
                "z": 0.0,
                "instruction": "Deliver batch-picked cart to Put-Wall for item scan & individual order sorting."
            }
            route.append(sort_stop)
            stop_counter += 1

        final_corridor_dist = abs(curr_x - pack_station_x) + abs(curr_y - pack_station_y)
        total_distance += final_corridor_dist
        
        pack_stop = {
            "stop_number": stop_counter,
            "location_code": "PACK-STATION",
            "zone_id": "STATION",
            "type": "PACK_STATION",
            "x": pack_station_x,
            "y": pack_station_y,
            "z": 0.0,
            "instruction": "Deliver picked items to Packing Station for inspection and cartonization."
        }
        route.append(pack_stop)
        
        return route, total_distance

    def calculate_aisle_distance(
        self,
        loc1: Dict[str, Any],
        loc2: Dict[str, Any],
        cross_front_y: float = 0.0,
        cross_back_y: float = 50.0
    ) -> float:
        """
        Calculate warehouse aisle graph rectilinear distance.
        Prevents walking through steel racks: Changing aisles requires routing via cross-aisles!
        """
        x1, y1 = float(loc1.get("x", loc1.get("x_coordinate", 0.0))), float(loc1.get("y", loc1.get("y_coordinate", 0.0)))
        x2, y2 = float(loc2.get("x", loc2.get("x_coordinate", 0.0))), float(loc2.get("y", loc2.get("y_coordinate", 0.0)))
        
        if abs(x1 - x2) < 1e-4:
            # Same aisle: travel straight along the aisle
            return abs(y1 - y2)
        else:
            # Different aisles: Must walk to front or back cross-aisle to change aisles
            dist_via_front = abs(y1 - cross_front_y) + abs(x1 - x2) + abs(y2 - cross_front_y)
            dist_via_back = abs(cross_back_y - y1) + abs(x1 - x2) + abs(cross_back_y - y2)
            return min(dist_via_front, dist_via_back)

    def _get_unique_locations(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract unique locations"""
        seen = set()
        unique = []
        for it in items:
            code = it.get("location_code")
            if code and code not in seen:
                seen.add(code)
                unique.append({
                    "location_code": code,
                    "zone_id": it.get("zone_id"),
                    "row_id": it.get("row_id"),
                    "shelf_id": it.get("shelf_id"),
                    "x": float(it.get("x_coordinate", 0.0)),
                    "y": float(it.get("y_coordinate", 0.0)),
                    "z": float(it.get("z_coordinate", 1.0))
                })
        return unique

    def _generate_trip_instructions(
        self,
        trip_idx: int,
        route: List[Dict[str, Any]],
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate step-by-step picking instructions for a trip"""
        loc_items: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            c = it.get("location_code")
            if c not in loc_items:
                loc_items[c] = []
            loc_items[c].append(it)
            
        instructions = []
        for st in route:
            code = st.get("location_code")
            st_type = st.get("type", "PICK")
            if st_type == "DEPOT":
                instructions.append({
                    "trip": trip_idx,
                    "stop_number": st["stop_number"],
                    "location_code": "DEPOT",
                    "instruction": f"[Trip {trip_idx}] Start at Cart Depot. Prepare empty cart."
                })
            elif st_type == "PACK_STATION":
                instructions.append({
                    "trip": trip_idx,
                    "stop_number": st["stop_number"],
                    "location_code": "PACK-STATION",
                    "instruction": f"[Trip {trip_idx}] Drop off all picked items at Packing Station."
                })
            elif st_type == "SORTATION_WALL":
                instructions.append({
                    "trip": trip_idx,
                    "stop_number": st["stop_number"],
                    "location_code": "SORTATION_WALL",
                    "instruction": f"[Trip {trip_idx}] Deliver batch-picked cart to Put-Wall for item scan & individual order sorting."
                })
            elif st_type == "WAYPOINT" or st.get("is_waypoint", False):
                instructions.append({
                    "trip": trip_idx,
                    "stop_number": st["stop_number"],
                    "location_code": code,
                    "zone": st.get("zone_id", "CORRIDOR"),
                    "instruction": f"[Trip {trip_idx}] {st.get('instruction', 'Navigate via corridor waypoint.')}",
                    "is_waypoint": True
                })
            else:
                picked = loc_items.get(code, [])
                instructions.append({
                    "trip": trip_idx,
                    "stop_number": st["stop_number"],
                    "location_code": code,
                    "zone": st.get("zone_id"),
                    "row": st.get("row_id"),
                    "shelf": st.get("shelf_id"),
                    "items_to_pick": [
                        {"sku_code": p.get("sku_code"), "quantity": p.get("quantity")}
                        for p in picked
                    ],
                    "total_items_at_stop": len(picked),
                    "instruction": f"[Trip {trip_idx}] Go to {code} and pick {sum(p.get('quantity', 1) for p in picked)} item(s)."
                })
        return instructions

    def _generate_legacy_instructions(self, route: List[Dict[str, Any]], items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Legacy instruction format for backward compatibility"""
        loc_items = {}
        for it in items:
            c = it.get("location_code")
            if c not in loc_items:
                loc_items[c] = []
            loc_items[c].append(it)
        instructions = []
        for i, loc in enumerate(route):
            c = loc.get("location_code")
            if loc.get("is_waypoint") or loc.get("type") == "WAYPOINT":
                instructions.append({
                    "stop_number": i + 1,
                    "location_code": c,
                    "zone": loc.get("zone_id", "CORRIDOR"),
                    "items_to_pick": [],
                    "total_items_at_stop": 0,
                    "instruction": loc.get("instruction", f"Navigate via waypoint {c}")
                })
                continue
            at_loc = loc_items.get(c, [])
            instructions.append({
                "stop_number": i + 1,
                "location_code": c,
                "zone": loc.get("zone_id"),
                "row": loc.get("row_id"),
                "shelf": loc.get("shelf_id"),
                "items_to_pick": [{"sku_code": it.get("sku_code"), "quantity": it.get("quantity")} for it in at_loc],
                "total_items_at_stop": len(at_loc),
                "instruction": f"Go to {c} and pick {len(at_loc)} item(s)"
            })
        return instructions

    def _flatten_all_instructions(self, trip_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flatten instructions across all trips"""
        all_ins = []
        for tr in trip_results:
            all_ins.extend(tr.get("instructions", []))
        return all_ins
