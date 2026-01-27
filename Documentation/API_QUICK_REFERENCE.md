# GalaxyGPS API Quick Reference

## Import & Setup

```python
try:
    import GalaxyGPS.api as galaxygps_api
except ImportError:
    galaxygps_api = None

# Always check availability before use
if galaxygps_api and galaxygps_api.is_available():
    # Use API here
    pass
```

## Common Patterns

### Get Current Route Info

```python
route = galaxygps_api.get_route_info()
if route and route['is_loaded']:
    print(f"Next: {route['next_stop']}")
    print(f"Jumps: {route['jumps_left']}")
    print(f"Type: {route['route_type']}")
```

### Get All Waypoints

```python
waypoints = galaxygps_api.get_route_waypoints()
if waypoints:
    for i, system in enumerate(waypoints):
        print(f"{i+1}. {system}")
```

### Get Route Progress

```python
progress = galaxygps_api.get_route_progress()
if progress:
    print(f"{progress['percent_complete']:.1f}% complete")
    print(f"Current: {progress['current_waypoint']}")
    print(f"Next: {progress['next_waypoint']}")
```

### Get All Fleet Carriers

```python
carriers = galaxygps_api.get_fleet_carriers()
if carriers:
    for carrier in carriers:
        print(f"{carrier['callsign']}: {carrier['name']}")
        print(f"  Location: {carrier['current_system']}")
        print(f"  Fuel: {carrier['fuel']} tons")
```

### Get Specific Carrier

```python
carrier = galaxygps_api.get_fleet_carrier("ABC-123")
if carrier:
    print(f"Name: {carrier['name']}")
    print(f"System: {carrier['current_system']}")
    print(f"Balance: {carrier['balance']:,} CR")
```

### Get Selected Carrier

```python
carrier = galaxygps_api.get_selected_fleet_carrier()
if carrier:
    print(f"Selected: {carrier['callsign']}")
```

### Get Carrier Cargo

```python
cargo = galaxygps_api.get_fleet_carrier_cargo("ABC-123")
if cargo:
    for item in cargo:
        print(f"{item['localized_name']}: {item['quantity']}")
```

### Get Carrier Ships

```python
ships = galaxygps_api.get_fleet_carrier_ships("ABC-123")
if ships:
    for ship in ships:
        print(f"{ship['ship_type']}: {ship['ship_name']}")
```

### Get Player Location

```python
system = galaxygps_api.get_current_system()
station = galaxygps_api.get_current_station()
docked = galaxygps_api.is_docked()

if docked:
    print(f"Docked at {station} in {system}")
else:
    print(f"In space at {system}")
```

## All Functions

### Availability

- `is_available()` → bool
- `get_version()` → str
- `get_plugin_version()` → Optional[str]
- `get_api_info()` → Dict

### Route

- `get_route_info()` → Optional[Dict]
- `get_route_waypoints()` → Optional[List[str]]
- `get_current_waypoint()` → Optional[str]
- `get_route_progress()` → Optional[Dict]

### Fleet Carriers

- `get_fleet_carriers()` → Optional[List[Dict]]
- `get_fleet_carrier(callsign)` → Optional[Dict]
- `get_selected_fleet_carrier()` → Optional[Dict]
- `get_fleet_carrier_cargo(callsign)` → Optional[List[Dict]]
- `get_fleet_carrier_ships(callsign)` → Optional[List[Dict]]

### Player State

- `get_current_system()` → Optional[str]
- `get_current_station()` → Optional[str]
- `is_docked()` → bool

## Return Values

### Route Info Dict

```python
{
    'next_stop': str,
    'jumps_left': int,
    'offset': int,
    'total_waypoints': int,
    'route_type': str,  # 'roadtoriches', 'fleetcarrier', 'neutron', 'galaxy'
    'is_loaded': bool,
    'distance_remaining': str,
    'fuel_remaining': float,
    'fuel_used': float
}
```

### Route Progress Dict

```python
{
    'current_index': int,
    'total_waypoints': int,
    'percent_complete': float,
    'waypoints_remaining': int,
    'current_waypoint': str,
    'next_waypoint': str or None
}
```

### Carrier Dict

```python
{
    'callsign': str,
    'name': str,
    'current_system': str,
    'system_address': str,
    'fuel': int,
    'balance': int,
    'state': str,
    'theme': str,
    'docking_access': str,
    'notorious_access': str,
    'cargo_count': int,
    'cargo_value': int,
    'tritium_in_cargo': int,
    'icy_rings': bool,
    'pristine': bool,
    'last_updated': str,
    'source_galaxy': str
}
```

### Cargo Item Dict

```python
{
    'commodity': str,
    'localized_name': str,
    'quantity': int,
    'value': int
}
```

### Ship Dict

```python
{
    'ship_type': str,
    'ship_name': str,
    'ship_id': str,
    'last_updated': str
}
```

## Error Handling

All functions return `None` or empty collections on error:

```python
# These never raise exceptions
route = galaxygps_api.get_route_info()  # None if error
carriers = galaxygps_api.get_fleet_carriers()  # None if error
waypoints = galaxygps_api.get_route_waypoints()  # None if error

# Always check for None
if route is not None:
    # Safe to use
    pass
```

## Best Practices

1. **Always check availability**

   ```python
   if not galaxygps_api.is_available():
       return
   ```

2. **Handle None returns**

   ```python
   route = galaxygps_api.get_route_info()
   if route is None:
       return
   ```

3. **Check is_loaded for routes**

   ```python
   if route and route['is_loaded']:
       # Route is active
       pass
   ```

4. **Don't modify returned data**

   ```python
   # Don't do this
   carriers[0]['name'] = "Modified"
   
   # Data is read-only
   ```

5. **Log API version**

   ```python
   logger.info(f"Using GalaxyGPS API v{galaxygps_api.get_version()}")
   ```

## Full Example

```python
import logging
try:
    import GalaxyGPS.api as galaxygps_api
except ImportError:
    galaxygps_api = None

logger = logging.getLogger(__name__)

def journal_entry(cmdr, is_beta, system, station, entry, state):
    # Check availability
    if not galaxygps_api or not galaxygps_api.is_available():
        return
    
    # Handle FSD jump
    if entry.get('event') == 'FSDJump':
        # Get route progress
        progress = galaxygps_api.get_route_progress()
        if progress:
            logger.info(f"Route: {progress['percent_complete']:.1f}% complete")
            logger.info(f"Next: {progress['next_waypoint']}")
        
        # Get current system
        current = galaxygps_api.get_current_system()
        logger.info(f"Arrived at: {current}")
    
    # Handle carrier jump
    elif entry.get('event') == 'CarrierJump':
        # Check all carriers
        carriers = galaxygps_api.get_fleet_carriers()
        if carriers:
            jumped_system = entry.get('StarSystem', '')
            for carrier in carriers:
                if carrier['current_system'] == jumped_system:
                    logger.info(f"Carrier {carrier['callsign']} jumped")
```

## Documentation

- **Full API Docs**: `API_DOCUMENTATION.md`
- **Example Plugin**: `examples/galaxygps_api_example/`
- **Implementation**: `API_SUMMARY.md`
