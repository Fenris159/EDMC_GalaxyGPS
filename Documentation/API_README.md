# GalaxyGPS API Example Plugin

This is a complete example plugin that demonstrates how to use the GalaxyGPS Public API in your own EDMC plugins.

## What This Example Shows

- ✅ How to import and check for GalaxyGPS API availability
- ✅ How to access route information
- ✅ How to access fleet carrier data
- ✅ How to respond to journal events
- ✅ How to create a simple UI displaying API data
- ✅ Proper error handling and logging
- ✅ Best practices for API usage

## Installation

1. Copy the entire `galaxygps_api_example` folder to your EDMC plugins directory:
   - Windows: `%LOCALAPPDATA%\EDMarketConnector\plugins\`
   - Mac: `~/Library/Application Support/EDMarketConnector/plugins/`
   - Linux: `~/.local/share/EDMarketConnector/plugins/`

2. Restart EDMC

3. The example plugin will appear in the main EDMC window showing:
   - API status and version
   - Current route information (if a route is loaded in GalaxyGPS)
   - Fleet carrier information (if carriers are tracked)

## What It Does

### Display Updates

The plugin displays three pieces of information:

1. **Status**: Shows whether the GalaxyGPS API is available and its version
2. **Route**: Shows current waypoint, jumps remaining, and progress
3. **Carrier**: Shows selected carrier or total number of tracked carriers

### Event Handling

The plugin updates its display when:

- Player jumps to a new system (FSDJump)
- Player docks or undocks
- A fleet carrier jumps
- EDMC preferences change

### Logging

The plugin logs interesting events to the EDMC log file:

- Route progress percentages on jumps
- Fleet carrier jump notifications
- API availability status

## Code Structure

```python
# 1. Import the API
import GalaxyGPS.api as galaxygps_api

# 2. Check availability
if galaxygps_api.is_available():
    # 3. Use API functions
    route = galaxygps_api.get_route_info()
    carriers = galaxygps_api.get_fleet_carriers()
```

## Key Functions Demonstrated

### Route API

- `get_route_info()` - Get current route details
- `get_route_waypoints()` - Get list of all waypoints
- `get_route_progress()` - Get detailed progress information`

### Fleet Carrier API

- `get_fleet_carriers()` - Get all tracked carriers
- `get_selected_fleet_carrier()` - Get currently selected carrier
- `get_fleet_carrier_cargo()` - Get carrier cargo details
- `get_fleet_carrier_ships()` - Get stored ships

### Utility Functions

- `is_available()` - Check if API is ready
- `get_version()` - Get API version
- `get_api_info()` - Get comprehensive API information

## Advanced Examples

The plugin includes two advanced example functions (not called by default):

### `example_route_analysis()`

Shows how to combine multiple API calls to perform detailed route analysis:

- Route type detection
- Progress calculation
- Fuel tracking
- Waypoint analysis

### `example_carrier_analysis()`

Shows how to analyze all tracked fleet carriers:

- Iterate through all carriers
- Get detailed cargo information
- Get stored ships information
- Calculate totals and statistics

To use these functions, you can call them from `journal_entry()` or create UI buttons to trigger them.

## Customization Ideas

Use this example as a starting point for your own plugins:

1. **Route Notifications**: Send desktop notifications when approaching waypoints
2. **Carrier Tracker**: Create a detailed fleet carrier management UI
3. **Route Statistics**: Calculate and display route efficiency metrics
4. **Integration**: Combine GalaxyGPS data with other EDMC plugins
5. **Export**: Export route and carrier data to external tools

## API Documentation

For complete API documentation, see `Documentation/API_DOCUMENTATION.md` in the main GalaxyGPS plugin folder.

## Requirements

- EDMC 5.0.0 or later
- GalaxyGPS plugin installed
- Python 3.9+

## Support

For questions or issues:

1. Check the API documentation
2. Review this example code
3. Create an issue on the GalaxyGPS GitHub repository

## License

This example is provided as-is for educational purposes. Feel free to use and modify it for your own plugins.
