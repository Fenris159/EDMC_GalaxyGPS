# GalaxyGPS Public API Documentation

## Overview

The GalaxyGPS plugin provides a stable, public API that allows other EDMC plugins to access route planning data, fleet carrier information, and player state. This API follows EDMC plugin development guidelines and provides safe, read-only access to GalaxyGPS data.

**API Version:** 1.0.0  
**Stability:** Stable - Breaking changes will increment major version

## Installation

The API is automatically available when the GalaxyGPS plugin is installed. No additional installation is required.

## Basic Usage

```python
# In your plugin's load.py
import logging

# Try to import GalaxyGPS API
try:
    import GalaxyGPS.api as galaxygps_api
    GALAXYGPS_AVAILABLE = True
except ImportError:
    GALAXYGPS_AVAILABLE = False
    galaxygps_api = None

logger = logging.getLogger(__name__)

def plugin_start3(plugin_dir):
    if GALAXYGPS_AVAILABLE:
        logger.info(f"GalaxyGPS API available: v{galaxygps_api.get_version()}")
    return "MyPlugin"

def journal_entry(cmdr, is_beta, system, station, entry, state):
    if not GALAXYGPS_AVAILABLE or not galaxygps_api.is_available():
        return
    
    # Get current route information
    route_info = galaxygps_api.get_route_info()
    if route_info and route_info['is_loaded']:
        logger.info(f"Next waypoint: {route_info['next_stop']}")
        logger.info(f"Jumps remaining: {route_info['jumps_left']}")
```

## API Reference

### Availability Check

#### `is_available() -> bool`

Check if the GalaxyGPS API is available and ready to use.

**Returns:** `True` if API is ready, `False` otherwise

**Example:**

```python
if galaxygps_api.is_available():
    # Safe to use API functions
    route = galaxygps_api.get_route_info()
```

#### `get_version() -> str`

Get the API version string.

**Returns:** API version in semantic versioning format (e.g., "1.0.0")

#### `get_plugin_version() -> Optional[str]`

Get the GalaxyGPS plugin version.

**Returns:** Plugin version string or `None` if not available

#### `get_api_info() -> Dict[str, str]`

Get comprehensive API information.

**Returns:** Dictionary containing:

- `api_version`: API version
- `plugin_version`: Plugin version
- `available`: Whether API is available
- `description`: API description

---

### Route API

#### `get_route_info() -> Optional[Dict[str, Any]]`

Get current route information.

**Returns:** Dictionary or `None` if no route loaded

**Dictionary Keys:**

- `next_stop` (str): Next waypoint system name
- `jumps_left` (int): Estimated jumps remaining
- `offset` (int): Current position in route (0-based)
- `total_waypoints` (int): Total number of waypoints
- `route_type` (str): Route type - 'roadtoriches', 'fleetcarrier', 'neutron', or 'galaxy'
- `is_loaded` (bool): True if route is loaded
- `distance_remaining` (str): Distance remaining (formatted string)
- `fuel_remaining` (float): Fuel remaining (if applicable)
- `fuel_used` (float): Fuel used so far (if applicable)

**Example:**

```python
route = galaxygps_api.get_route_info()
if route and route['is_loaded']:
    print(f"Route type: {route['route_type']}")
    print(f"Next stop: {route['next_stop']}")
    print(f"Progress: {route['offset']}/{route['total_waypoints']}")
```

#### `get_route_waypoints() -> Optional[List[str]]`

Get list of all system names in the current route.

**Returns:** List of system names or `None` if no route loaded

**Note:** Returns a deep copy to prevent external modification

**Example:**

```python
waypoints = galaxygps_api.get_route_waypoints()
if waypoints:
    print(f"Route has {len(waypoints)} waypoints")
    for i, system in enumerate(waypoints):
        print(f"{i+1}. {system}")
```

#### `get_current_waypoint() -> Optional[str]`

Get the current/next waypoint system name.

**Returns:** System name or `None` if no route loaded

**Example:**

```python
current = galaxygps_api.get_current_waypoint()
if current:
    print(f"Current waypoint: {current}")
```

#### `get_route_progress() -> Optional[Dict[str, Any]]`

Get detailed route progress information.

**Returns:** Dictionary or `None` if no route loaded

**Dictionary Keys:**

- `current_index` (int): Current position (0-based)
- `total_waypoints` (int): Total waypoints
- `percent_complete` (float): Percentage complete (0-100)
- `waypoints_remaining` (int): Waypoints left
- `current_waypoint` (str): Current system name
- `next_waypoint` (str or None): Next system name (None if at end)

**Example:**

```python
progress = galaxygps_api.get_route_progress()
if progress:
    percent = progress['percent_complete']
    print(f"Route progress: {percent:.1f}%")
    print(f"Current: {progress['current_waypoint']}")
    print(f"Next: {progress['next_waypoint']}")
```

---

### Fleet Carrier API

#### `get_fleet_carriers() -> Optional[List[Dict[str, Any]]]`

Get list of all tracked fleet carriers.

**Returns:** List of carrier dictionaries or `None` on error

**Carrier Dictionary Keys:**

- `callsign` (str): Carrier callsign (e.g., "ABC-123")
- `name` (str): Carrier name
- `current_system` (str): Current system name
- `system_address` (str): System address
- `fuel` (int): Tritium fuel amount
- `balance` (int): Credit balance
- `state` (str): Carrier state
- `theme` (str): Carrier theme
- `docking_access` (str): Docking access level
- `notorious_access` (str): Notorious access setting
- `cargo_count` (int): Number of cargo items
- `cargo_value` (int): Total cargo value
- `tritium_in_cargo` (int): Tritium in cargo hold
- `icy_rings` (bool): Has icy rings nearby
- `pristine` (bool): Has pristine reserves nearby
- `last_updated` (str): Last update timestamp
- `source_galaxy` (str): Galaxy (Live/Legacy/Beta)

**Example:**

```python
carriers = galaxygps_api.get_fleet_carriers()
if carriers:
    for carrier in carriers:
        print(f"{carrier['callsign']}: {carrier['name']}")
        print(f"  Location: {carrier['current_system']}")
        print(f"  Fuel: {carrier['fuel']} tons")
```

#### `get_fleet_carrier(callsign: str) -> Optional[Dict[str, Any]]`

Get information for a specific fleet carrier.

**Args:**

- `callsign`: Fleet carrier callsign (e.g., "ABC-123")

**Returns:** Carrier dictionary (see `get_fleet_carriers` for format) or `None` if not found

**Example:**

```python
carrier = galaxygps_api.get_fleet_carrier("ABC-123")
if carrier:
    print(f"Carrier: {carrier['name']}")
    print(f"Location: {carrier['current_system']}")
    print(f"Balance: {carrier['balance']:,} CR")
```

#### `get_selected_fleet_carrier() -> Optional[Dict[str, Any]]`

Get the currently selected fleet carrier in the GalaxyGPS UI.

**Returns:** Carrier dictionary or `None` if no carrier selected

**Example:**

```python
carrier = galaxygps_api.get_selected_fleet_carrier()
if carrier:
    print(f"Selected carrier: {carrier['callsign']}")
```

#### `get_fleet_carrier_cargo(callsign: str) -> Optional[List[Dict[str, Any]]]`

Get cargo details for a specific fleet carrier.

**Args:**

- `callsign`: Fleet carrier callsign (e.g., "ABC-123")

**Returns:** List of cargo dictionaries or `None` on error

**Cargo Dictionary Keys:**

- `commodity` (str): Commodity name
- `localized_name` (str): Localized commodity name
- `quantity` (int): Quantity in cargo
- `value` (int): Total value

**Example:**

```python
cargo = galaxygps_api.get_fleet_carrier_cargo("ABC-123")
if cargo:
    print(f"Carrier has {len(cargo)} cargo types:")
    for item in cargo:
        print(f"  {item['localized_name']}: {item['quantity']}")
```

#### `get_fleet_carrier_ships(callsign: str) -> Optional[List[Dict[str, Any]]]`

Get stored ships for a specific fleet carrier.

**Args:**

- `callsign`: Fleet carrier callsign (e.g., "ABC-123")

**Returns:** List of ship dictionaries or `None` on error

**Ship Dictionary Keys:**

- `ship_type` (str): Ship type (e.g., "Anaconda")
- `ship_name` (str): Custom ship name
- `ship_id` (str): Unique ship ID
- `last_updated` (str): Last update timestamp

**Example:**

```python
ships = galaxygps_api.get_fleet_carrier_ships("ABC-123")
if ships:
    print(f"Carrier has {len(ships)} ships stored:")
    for ship in ships:
        print(f"  {ship['ship_type']}: {ship['ship_name']}")
```

---

### Player State API

#### `get_current_system() -> Optional[str]`

Get the player's current system name.

**Returns:** System name or `None` if not available

**Example:**

```python
system = galaxygps_api.get_current_system()
if system:
    print(f"Current system: {system}")
```

#### `get_current_station() -> Optional[str]`

Get the player's current station name.

**Returns:** Station name or `None` if not docked

**Example:**

```python
station = galaxygps_api.get_current_station()
if station:
    print(f"Docked at: {station}")
```

#### `is_docked() -> bool`

Check if the player is currently docked.

**Returns:** `True` if docked, `False` otherwise

**Example:**

```python
if galaxygps_api.is_docked():
    print("Player is docked")
else:
    print("Player is in space")
```

---

## Complete Example Plugin

See `examples/galaxygps_api_example/` for a complete example plugin that demonstrates all API features.

## Best Practices

### 1. Always Check Availability

```python
if not galaxygps_api.is_available():
    return  # GalaxyGPS not loaded yet
```

### 2. Handle None Returns

All API functions may return `None` if data is not available:

```python
route = galaxygps_api.get_route_info()
if route is None:
    return  # No route loaded
```

### 3. Use Try-Except for Import

```python
try:
    import GalaxyGPS.api as galaxygps_api
except ImportError:
    galaxygps_api = None
    # GalaxyGPS plugin not installed
```

### 4. Don't Modify Returned Data

The API returns deep copies of data, but it's still good practice not to modify:

```python
carriers = galaxygps_api.get_fleet_carriers()
# Don't do: carriers[0]['name'] = "Modified"
# Instead: work with the data read-only
```

### 5. Log API Usage

```python
import logging
logger = logging.getLogger(__name__)

if galaxygps_api.is_available():
    logger.info(f"Using GalaxyGPS API v{galaxygps_api.get_version()}")
```

## Error Handling

The API is designed to be safe and never raise exceptions. All functions return `None` or empty collections on error:

```python
# These will never raise exceptions
route = galaxygps_api.get_route_info()  # Returns None on error
carriers = galaxygps_api.get_fleet_carriers()  # Returns None on error
waypoints = galaxygps_api.get_route_waypoints()  # Returns None on error
```

Errors are logged internally by GalaxyGPS for debugging.

## Thread Safety

All API functions are thread-safe and can be called from any thread. However, it's recommended to call them from the main thread when possible, especially in EDMC callbacks like `journal_entry()`.

## Versioning

The API follows [Semantic Versioning](https://semver.org/):

- **Major version** (1.x.x): Breaking changes to API
- **Minor version** (x.1.x): New features, backward compatible
- **Patch version** (x.x.1): Bug fixes, backward compatible

Check the API version to ensure compatibility:

```python
version = galaxygps_api.get_version()
major = int(version.split('.')[0])
if major != 1:
    logger.warning(f"GalaxyGPS API version {version} may not be compatible")
```

## Support

For issues, questions, or feature requests related to the GalaxyGPS API:

1. Check the [GitHub Issues](https://github.com/your-repo/EDMC_GalaxyGPS/issues)
2. Create a new issue with the `API` label
3. Include your plugin code and the API version you're using

## Changelog

### Version 1.0.0 (2026-01-23)

- Initial stable API release
- Route information access
- Fleet carrier data access
- Player state access
- Complete documentation and examples
