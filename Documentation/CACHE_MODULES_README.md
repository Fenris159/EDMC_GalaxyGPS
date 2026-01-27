<!-- markdownlint-disable MD060 -->
# Cache Modules - Column Index Reference

This document describes the CSV cache files and their column structures for easy indexing.

## fleet_carrier_ships.csv

Stores ships located at fleet carriers.

### fleet_carrier_ships.csv - Column Index Structure

| Index | Column Name | Always Populated | Description |
| ----- | ----------- | ---------------- | ----------- |
| 0 | Callsign | ✅ Yes | Fleet carrier callsign (e.g., "N4W-T0Z") |
| 1 | Ship Type | ✅ Yes | Ship type identifier (e.g., "python", "cutter") |
| 2 | Ship ID | ✅ Yes | Unique ship identifier (game-assigned) |
| 3 | Ship Name | ⚠️ Optional | Custom ship name (empty if unnamed) |
| 4 | Star System | ✅ Yes | Current system location |
| 5 | Ship Market ID | ✅ Yes | Carrier's market ID |
| 6 | Location Type | ✅ Yes | Location type (currently always "Here") |
| 7 | Last Updated | ✅ Yes | Timestamp of last update |

### Example Row

```csv
N4W-T0Z,anaconda,19,Xenobane,Hyades Sector AF-Z b4,3710879232,Here,2026-01-24 05:20:43 UTC
```

### Example Python Access

```python
import csv

with open('fleet_carrier_ships.csv', 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    for row in reader:
        callsign = row[0]
        ship_type = row[1]
        ship_id = row[2]
        ship_name = row[3] if row[3] else "Unnamed"  # Handle empty names
        star_system = row[4]
        ship_market_id = row[5]
        location_type = row[6]
        last_updated = row[7]
```

---

## fleet_carrier_cargo.csv

Stores cargo/commodities on fleet carriers.

### fleet_carrier_cargo.csv - Column Index Structure

| Index | Column Name | Always Populated | Description |
| ----- | ----------- | ---------------- | ----------- |
| 0 | Callsign | ✅ Yes | Fleet carrier callsign |
| 1 | Commodity | ✅ Yes | Commodity internal name (lowercase) |
| 2 | Localized Name | ✅ Yes | Display name for commodity |
| 3 | Quantity | ✅ Yes | Amount of commodity stored |
| 4 | Value Per Unit | ⚠️ Optional | Credits per unit (0 from journal events) |
| 5 | Total Value | ⚠️ Optional | Total value in credits (0 from journal) |
| 6 | Last Updated | ✅ Yes | Timestamp of last update |
| 7 | Source Galaxy | ✅ Yes | Live/Beta/Legacy server indicator |

---

## fleet_carrier_modules.csv

Stores outfitting modules available on fleet carriers.

### fleet_carrier_modules.csv - Column Index Structure

| Index | Column Name | Always Populated | Description |
| ----- | ----------- | ---------------- | ----------- |
| 0 | Callsign | ✅ Yes | Fleet carrier callsign |
| 1 | Module | ✅ Yes | Module internal name |
| 2 | Localized Name | ✅ Yes | Display name for module |
| 3 | Quantity | ✅ Yes | Stock quantity (999999999 = unlimited) |
| 4 | Buy Price | ✅ Yes | Purchase price in credits |
| 5 | Last Updated | ✅ Yes | Timestamp of last update |
| 6 | Source Galaxy | ✅ Yes | Live/Beta/Legacy server indicator |

---

## fleet_carriers.csv

Stores fleet carrier information.

### fleet_carriers.csv - Column Index Structure

| Index | Column Name | Always Populated | Description |
| ----- | ----------- | ---------------- | ----------- |
| 0 | Callsign | ✅ Yes | Fleet carrier callsign |
| 1 | Name | ✅ Yes | Carrier custom name |
| 2 | Current System | ✅ Yes | Current star system |
| 3 | Current Body | ⚠️ Optional | Current celestial body |
| 4 | Fuel | ✅ Yes | Current fuel level |
| 5 | Jump Cooldown Expiry | ⚠️ Optional | When jump cooldown expires |
| 6 | Bank Balance | ✅ Yes | Carrier credits balance |
| 7 | Bank Reserve Balance | ✅ Yes | Reserved credits |
| 8 | Market ID | ✅ Yes | Unique market identifier |
| 9 | Services Crew | ✅ Yes | Active crew count |
| 10 | Total Capacity | ✅ Yes | Total cargo capacity |
| 11 | Used Capacity | ✅ Yes | Used cargo space |
| 12 | Free Capacity | ✅ Yes | Available cargo space |
| 13 | Allow Notorious | ✅ Yes | Allows notorious commanders (true/false) |
| 14 | Docking Access | ✅ Yes | Docking permission setting |
| 15 | Notorious Access | ✅ Yes | Notorious access setting |
| 16 | Last Updated | ✅ Yes | Timestamp of last update |
| 17 | Source Galaxy | ✅ Yes | Live/Beta/Legacy server indicator |

---

## Notes

- **File Location (Runtime)**: `%LOCALAPPDATA%\EDMarketConnector\plugins\EDMC_GalaxyGPS\` (Windows) or `~/.local/share/EDMarketConnector/plugins/EDMC_GalaxyGPS/` (Linux/Mac)
- **File Location (Development)**: These CSVs are NOT in the source directory
- **Encoding**: UTF-8 with BOM (utf-8-sig)
- **Persistence**: All data persists between EDMC restarts
- **Data Structure**: Single consolidated CSV per data type (not per carrier)
- **Primary Keys**:
  - Ships: Callsign + Ship ID
  - Cargo: Callsign + Commodity
  - Modules: Callsign + Module
  - Carriers: Callsign

---

Last Updated: 2026-01-25
