# GalaxyGPS Index Reference

This document provides a comprehensive reference for all data structures that use indexed access in the GalaxyGPS plugin.

---

## Table of Contents

- [Route Data Structures](#route-data-structures)
  - [Fleet Carrier Routes](#fleet-carrier-routes)
  - [Neutron Routes](#neutron-routes)
  - [Galaxy Routes](#galaxy-routes)
  - [Road to Riches Routes](#road-to-riches-routes)
  - [Basic Routes](#basic-routes)
- [UI Window Structures](#ui-window-structures)
  - [Fleet Carrier Details Window](#fleet-carrier-details-window)
- [CSV Import/Export Headers](#csv-importexport-headers)
- [Cache File Structures](#cache-file-structures)
  - [Fleet Carrier Ships Cache](#fleet-carrier-ships-cache-fleet_carrier_shipscsv)
  - [Fleet Carrier Cargo Cache](#fleet-carrier-cargo-cache-fleet_carrier_cargocsv)
  - [Fleet Carrier Modules Cache](#fleet-carrier-modules-cache-fleet_carrier_modulescsv)
  - [Fleet Carriers Cache](#fleet-carriers-cache-fleet_carrierscsv)

---

## Route Data Structures

All route data is stored in `self.route` as a list of lists. Each inner list represents one waypoint with indexed values.

### Fleet Carrier Routes

**Internal Format**: 9 elements per waypoint

```text
Index 0: System Name          (str)
Index 1: Distance              (str, formatted to 2 decimals)
Index 2: Distance Remaining    (str, formatted to 2 decimals)
Index 3: Tritium in tank       (str)
Index 4: Tritium in market     (str)
Index 5: Fuel Used             (str)
Index 6: Icy Ring              (str, "Yes" or "No")
Index 7: Pristine              (str, "Yes" or "No")
Index 8: Restock Tritium       (str, "Yes" or "No")
```

**Key Notes**:

- Each row represents one Fleet Carrier jump
- Jump count is calculated as 1 per row
- "Fuel Used" (Index 5) represents tritium consumed for that jump
- "Restock Tritium" (Index 8) triggers warning message when "Yes"

**Code References**:

- Defined in: `GalaxyGPS.py` line 2179-2180
- Used in: `compute_distances()`, `check_fleet_carrier_restock_warning()`
- Jump counting: Explicit `if self.fleetcarrier: self.jumps_left -= 1` logic

---

### Neutron Routes

**Internal Format**: 4 elements per waypoint

```text
Index 0: System Name           (str)
Index 1: Distance To Arrival   (str, formatted to 2 decimals)
Index 2: Distance Remaining    (str, formatted to 2 decimals)
Index 3: Jumps                 (str, number of jumps to reach this waypoint)
```

**Key Notes**:

- "Jumps" (Index 3) represents the number of jumps required to reach that specific waypoint
- Jump count uses Index 3: `jump_idx = 3 if self.neutron else 1`
- "Remaining jumps afterwards" is calculated by summing Index 3 values from next row onwards
- Displays "Finished" when Distance Remaining (Index 2) equals 0

**Code References**:

- Defined in: `GalaxyGPS.py` line 2218-2225
- Used in: `compute_distances()`, `update_route()`, `find_current_waypoint_in_route()`
- Import header: `neutronimportheader` line 2182

---

### Galaxy Routes

**Internal Format**: 6 elements per waypoint

```text
Index 0: System Name           (str)
Index 1: Distance              (str, formatted to 2 decimals)
Index 2: Refuel                (str, "Yes" or "No")
Index 3: Distance Remaining    (str, formatted to 2 decimals)
Index 4: Fuel Left             (str, fuel remaining after jump)
Index 5: Fuel Used             (str, fuel consumed for this jump)
```

**Key Notes**:

- Each row represents 1 jump
- "Distance" (Index 1) = distance to next waypoint
- "Distance Remaining" (Index 3) = total distance left in route
- "Fuel Left" (Index 4) is displayed as "Fuel Remaining" in UI
- "Fuel Used" (Index 5) is fuel consumed to reach this waypoint
- "Next waypoint jumps" label displays Distance Remaining from Index 3 of *next* row

**Code References**:

- Defined in: `GalaxyGPS.py` line 2220-2265
- Used in: `compute_distances()` for fuel and distance calculations
- Import header: `galaxyimportheader` line 2185

---

### Road to Riches Routes

**Internal Format**: 4 elements per waypoint (body)

```text
Index 0: System Name           (str)
Index 1: Jumps                 (str, cumulative jumps to system)
Index 2: Body Name             (str)
Index 3: Body Subtype          (str)
```

**Key Notes**:

- Each row represents one scannable body
- Multiple rows can share the same System Name
- "Bodies to scan at:" counts rows where System Name matches the *current* waypoint's system
- Jump count uses Index 1: treats each unique system as 1 jump

**Code References**:

- Defined in: `GalaxyGPS.py` line 2178
- Used in: `update_bodies_text()` for counting bodies per system
- Import header: `road2richesimportheader` line 2183
- Flag: `self.roadtoriches = True` when detected

---

### Basic Routes

**Format 1 - System Name Only**: 1 element per waypoint

```text
Index 0: System Name           (str)
```

**Format 2 - With Jumps**: 2 elements per waypoint

```text
Index 0: System Name           (str)
Index 1: Jumps                 (str, typically cumulative)
```

**Key Notes**:

- Simplest route format
- Jump count uses Index 1 if available, otherwise 1 per row
- No additional metadata stored

**Code References**:

- Defined in: `GalaxyGPS.py` line 2176-2177
- Used for generic CSV imports without special headers

---

## UI Window Structures

### Fleet Carrier Details Window

**Column Order** (0-indexed):

```text
Index 0:  Select              (Button to select carrier)
Index 1:  Callsign            (Clickable link to Inara)
Index 2:  Name                (Clickable link to Inara)
Index 3:  EDSM                (Button to open system in EDSM)
Index 4:  System              (Clickable link to Inara system)
Index 5:  Tritium             (Fuel / Cargo display)
Index 6:  Balance             (Credits, displayed in GREEN)
Index 7:  Cargo               (Count and value)
Index 8:  State               (Carrier state)
Index 9:  Theme               (Carrier theme name)
Index 10: Icy Rings           (Red/gray indicator)
Index 11: Pristine            (Red/gray indicator)
Index 12: Docking Access      (Red/gray indicator)
Index 13: Notorious Access    (Red/gray indicator)
Index 14: Last Updated        (Local time formatted as "MM/DD/YY h:mm a")
```

**Key Notes**:

- Balance (Index 6) displays in green font
- Last Updated (Index 14) converts UTC timestamp to local time for display only
- Icy Rings, Pristine, Docking Access, Notorious Access use graphical indicators (colored circles)
- Data comes from `fleet_carriers.csv` cache

**Code References**:

- Defined in: `windows.py` line 85
- Used in: `show_carrier_details_window()` for table generation

---

## CSV Import/Export Headers

### Neutron Route Import Header

```csv
"System Name,Distance To Arrival,Distance Remaining,Neutron Star,Jumps"
```

Maps to internal format: `[System Name, Distance To Arrival, Distance Remaining, Jumps]`

---

### Road to Riches Import Header

```csv
"System Name,Body Name,Body Subtype,Is Terraformable,Distance To Arrival,Estimated Scan Value,Estimated Mapping Value,Jumps"
```

Maps to internal format: `[System Name, Jumps, Body Name, Body Subtype]`

---

### Fleet Carrier Import Header

```csv
"System Name,Distance,Distance Remaining,Tritium in tank,Tritium in market,Fuel Used,Icy Ring,Pristine,Restock Tritium"
```

Maps to internal format (9 elements) - direct 1:1 mapping

---

### Galaxy Route Import Header

```csv
"System Name,Distance,Distance Remaining,Fuel Left,Fuel Used,Refuel,Neutron Star"
```

Maps to internal format: `[System Name, Distance, Refuel, Distance Remaining, Fuel Left, Fuel Used]`

Note: "Neutron Star" column is read but not stored in route array (used only during import for routing decisions)

---

## Cache File Structures

### Fleet Carrier Ships Cache (`fleet_carrier_ships.csv`)

**Column Order** (0-indexed):

```text
Index 0: Callsign              (Fleet carrier callsign, e.g., "N4W-T0Z")
Index 1: Ship Type             (Internal ship type, e.g., "python", "cutter")
Index 2: Ship ID               (Unique game-assigned ship identifier)
Index 3: Ship Name             (Custom ship name, empty if unnamed)
Index 4: Star System           (Current system location)
Index 5: Ship Market ID        (Carrier's market ID)
Index 6: Location Type         (Currently always "Here")
Index 7: Last Updated          (Timestamp: "YYYY-MM-DD HH:MM:SS UTC")
```

**Key Notes**:

- Single consolidated CSV for all carriers
- Primary Key: Callsign + Ship ID
- Ship Name (Index 3) is empty string for unnamed ships
- Multiple carriers differentiated by Callsign (Index 0)
- Data persists between EDMC restarts
- Encoding: UTF-8 with BOM (utf-8-sig)

**File Location**: `plugin_dir/fleet_carrier_ships.csv`

**Code References**:

- Managed by: `StoredShipsManager.py`
- Updated from: `StoredShips` journal events
- Headers defined: `StoredShipsManager.CSV_HEADERS` line 22-30

**Example Row**:

```csv
N4W-T0Z,anaconda,19,Xenobane,Hyades Sector AF-Z b4,3710879232,Here,2026-01-24 05:20:43 UTC
```

**Python Access Example**:

```python
import csv

with open('fleet_carrier_ships.csv', 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    for row in reader:
        callsign = row[0]
        ship_type = row[1]
        ship_id = row[2]
        ship_name = row[3] if row[3] else "Unnamed"
        star_system = row[4]
        ship_market_id = row[5]
        location_type = row[6]
        last_updated = row[7]
```

---

### Fleet Carrier Cargo Cache (`fleet_carrier_cargo.csv`)

**Column Order** (0-indexed):

```text
Index 0: Callsign              (Fleet carrier callsign)
Index 1: Commodity             (Internal commodity name, lowercase)
Index 2: Localized Name        (Display name for commodity)
Index 3: Quantity              (Amount of commodity stored)
Index 4: Value Per Unit        (Credits per unit, 0 from journal events)
Index 5: Total Value           (Total value in credits, 0 from journal)
Index 6: Last Updated          (Timestamp: "YYYY-MM-DDTHH:MM:SSZ")
Index 7: Source Galaxy         (Live/Beta/Legacy server indicator)
```

**Key Notes**:

- Single consolidated CSV for all carriers
- Primary Key: Callsign + Commodity
- Value Per Unit and Total Value may be 0 from journal events (fully populated from CAPI)
- Data persists between EDMC restarts

**File Location**: `plugin_dir/fleet_carrier_cargo.csv`

**Code References**:

- Managed by: `CargoDetailsManager.py`
- Updated from: CAPI and `Cargo` journal events

---

### Fleet Carrier Modules Cache (`fleet_carrier_modules.csv`)

**Column Order** (0-indexed):

```text
Index 0: Callsign              (Fleet carrier callsign)
Index 1: Module                (Internal module name)
Index 2: Localized Name        (Display name for module)
Index 3: Quantity              (Stock quantity, 999999999 = unlimited)
Index 4: Buy Price             (Purchase price in credits)
Index 5: Last Updated          (Timestamp: "YYYY-MM-DDTHH:MM:SSZ")
Index 6: Source Galaxy         (Live/Beta/Legacy server indicator)
```

**Key Notes**:

- Single consolidated CSV for all carriers
- Primary Key: Callsign + Module
- Quantity of 999999999 indicates unlimited stock
- Data persists between EDMC restarts

**File Location**: `plugin_dir/fleet_carrier_modules.csv`

**Code References**:

- Managed by: `StoredModulesManager.py`
- Updated from: CAPI data

---

### Fleet Carriers Cache (`fleet_carriers.csv`)

**Column Order** (0-indexed):

```text
Index 0:  Callsign             (Fleet carrier callsign)
Index 1:  Name                 (Carrier custom name)
Index 2:  Current System       (Current star system)
Index 3:  Current Body         (Current celestial body, may be empty)
Index 4:  Fuel                 (Current fuel level)
Index 5:  Jump Cooldown Expiry (When jump cooldown expires, may be empty)
Index 6:  Bank Balance         (Carrier credits balance)
Index 7:  Bank Reserve Balance (Reserved credits)
Index 8:  Market ID            (Unique market identifier)
Index 9:  Services Crew        (Active crew count)
Index 10: Total Capacity       (Total cargo capacity)
Index 11: Used Capacity        (Used cargo space)
Index 12: Free Capacity        (Available cargo space)
Index 13: Allow Notorious      (Allows notorious commanders, true/false)
Index 14: Docking Access       (Docking permission setting)
Index 15: Notorious Access     (Notorious access setting)
Index 16: Last Updated         (Timestamp: "YYYY-MM-DDTHH:MM:SSZ")
Index 17: Source Galaxy        (Live/Beta/Legacy server indicator)
```

**Key Notes**:

- Single consolidated CSV for all carriers
- Primary Key: Callsign
- Current Body and Jump Cooldown Expiry may be empty
- Data persists between EDMC restarts

**File Location**: `plugin_dir/fleet_carriers.csv`

**Code References**:

- Managed by: `FleetCarrierManager.py`
- Updated from: CAPI data and journal events

---

## Important Implementation Notes

### Jump Counting Logic

Different route types use different methods for calculating jumps:

1. **Fleet Carrier**: Each row = 1 jump (explicit logic in code)
2. **Neutron**: Uses Index 3 for per-leg jumps
3. **Galaxy**: Each row = 1 jump (falls through to generic logic)
4. **Road to Riches**: Uses Index 1, treats unique systems as jumps
5. **Basic**: Uses Index 1 if available, otherwise 1 per row

### Distance Rounding

All distance values are rounded UP to the nearest hundredth (2 decimal places) during import using `math.ceil(val * 100) / 100`.

### Full Row Data Storage

The original CSV data for each row is preserved in `self.route_full_data` as a dictionary with lowercase field names as keys. This allows access to columns not stored in the main route array.

---

## Quick Reference Table

| Route Type       | Elements | Jump Index | Special Notes                          |
| ---------------- | -------- | ---------- | -------------------------------------- |
| Fleet Carrier    | 9        | N/A        | 1 jump per row, Index 8 for restock    |
| Neutron          | 4        | 3          | Per-leg jumps at Index 3               |
| Galaxy           | 6        | N/A        | 1 jump per row, fuel data at 4-5       |
| Road to Riches   | 4        | 1          | Multiple bodies per system             |
| Basic (Jumps)    | 2        | 1          | Simple system + jumps                  |
| Basic (No Jumps) | 1        | N/A        | Just system names                      |

---

**Last Updated**: January 2026
**Plugin Version**: See `version.json`
