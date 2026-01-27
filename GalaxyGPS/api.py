"""
GalaxyGPS Public API

This module provides a safe, stable API for other EDMC plugins to access
GalaxyGPS data and functionality.

Usage from other plugins:
    try:
        import GalaxyGPS.api as galaxygps_api
        
        # Check if API is available
        if galaxygps_api.is_available():
            # Get current route information
            route_info = galaxygps_api.get_route_info()
            
            # Get fleet carrier data
            carriers = galaxygps_api.get_fleet_carriers()
    except ImportError:
        # GalaxyGPS plugin not installed
        pass

API Version: 1.0.0
Stability: Stable - Breaking changes will increment major version
"""

import logging
from typing import Dict, List, Optional, Any
from copy import deepcopy

from config import appname  # type: ignore

# Module-level reference to the GalaxyGPS instance
_galaxy_gps_instance = None

# API version following semantic versioning
API_VERSION = "1.0.0"

logger = logging.getLogger(f'{appname}.EDMC_GalaxyGPS.api')


def _get_instance():
    """
    Internal function to get the GalaxyGPS instance.
    
    Returns:
        GalaxyGPS instance or None if not initialized
    """
    return _galaxy_gps_instance


def register_instance(instance):
    """
    Register the GalaxyGPS instance for API access.
    
    This is called internally by load.py during plugin initialization.
    Other plugins should NOT call this function.
    
    Args:
        instance: The GalaxyGPS instance
    """
    global _galaxy_gps_instance
    _galaxy_gps_instance = instance
    logger.info(f"[GalaxyGPS API] Registered instance, API version {API_VERSION}")


def is_available() -> bool:
    """
    Check if the GalaxyGPS API is available.
    
    Returns:
        True if GalaxyGPS is loaded and API is ready, False otherwise
        
    Example:
        if galaxygps_api.is_available():
            # Safe to use API
            pass
    """
    return _galaxy_gps_instance is not None


def get_version() -> str:
    """
    Get the API version.
    
    Returns:
        API version string in semantic versioning format (e.g., "1.0.0")
    """
    return API_VERSION


def get_plugin_version() -> Optional[str]:
    """
    Get the GalaxyGPS plugin version.
    
    Returns:
        Plugin version string or None if not available
    """
    instance = _get_instance()
    if instance and hasattr(instance, 'plugin_version'):
        return instance.plugin_version
    return None


# =============================================================================
# ROUTE API
# =============================================================================

def get_route_info() -> Optional[Dict[str, Any]]:
    """
    Get current route information.
    
    Returns:
        Dictionary containing route information, or None if no route loaded:
        {
            'next_stop': str,              # Next waypoint system name
            'jumps_left': int,             # Estimated jumps remaining
            'offset': int,                 # Current position in route (0-based)
            'total_waypoints': int,        # Total number of waypoints
            'route_type': str,             # 'roadtoriches', 'fleetcarrier', 'neutron', or 'galaxy'
            'is_loaded': bool,             # True if route is loaded
            'distance_remaining': str,     # Distance remaining (formatted string)
            'fuel_remaining': float,       # Fuel remaining (if applicable)
            'fuel_used': float             # Fuel used so far (if applicable)
        }
        
    Example:
        route = galaxygps_api.get_route_info()
        if route and route['is_loaded']:
            print(f"Next stop: {route['next_stop']}")
            print(f"Jumps left: {route['jumps_left']}")
    """
    instance = _get_instance()
    if not instance:
        return None
    
    try:
        route_type = 'galaxy'
        if instance.roadtoriches:
            route_type = 'roadtoriches'
        elif instance.fleetcarrier:
            route_type = 'fleetcarrier'
        elif instance.neutron:
            route_type = 'neutron'
        
        return {
            'next_stop': instance.next_stop if hasattr(instance, 'next_stop') else "No route planned",
            'jumps_left': instance.jumps_left if hasattr(instance, 'jumps_left') else 0,
            'offset': instance.offset if hasattr(instance, 'offset') else 0,
            'total_waypoints': len(instance.route) if hasattr(instance, 'route') and instance.route else 0,
            'route_type': route_type,
            'is_loaded': bool(instance.route) if hasattr(instance, 'route') else False,
            'distance_remaining': instance.dist_remaining if hasattr(instance, 'dist_remaining') else "",
            'fuel_remaining': instance.fuel_remaining if hasattr(instance, 'fuel_remaining') else 0.0,
            'fuel_used': instance.fuel_used if hasattr(instance, 'fuel_used') else 0.0
        }
    except Exception as e:
        logger.error(f"[GalaxyGPS API] Error getting route info: {e}")
        return None


def get_route_waypoints() -> Optional[List[str]]:
    """
    Get list of system names in the current route.
    
    Returns:
        List of system names (strings) or None if no route loaded.
        Returns a copy to prevent external modification.
        
    Example:
        waypoints = galaxygps_api.get_route_waypoints()
        if waypoints:
            print(f"Route has {len(waypoints)} waypoints")
            print(f"First waypoint: {waypoints[0]}")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'route') or not instance.route:
        return None
    
    try:
        # Return a copy to prevent external modification
        return deepcopy(instance.route)
    except Exception as e:
        logger.error(f"[GalaxyGPS API] Error getting route waypoints: {e}")
        return None


def get_current_waypoint() -> Optional[str]:
    """
    Get the current/next waypoint system name.
    
    Returns:
        System name (string) or None if no route loaded
        
    Example:
        current = galaxygps_api.get_current_waypoint()
        if current:
            print(f"Current waypoint: {current}")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'next_stop'):
        return None
    
    return instance.next_stop if instance.next_stop != "No route planned" else None


def get_route_progress() -> Optional[Dict[str, Any]]:
    """
    Get detailed route progress information.
    
    Returns:
        Dictionary with progress details or None if no route loaded:
        {
            'current_index': int,          # Current position (0-based)
            'total_waypoints': int,        # Total waypoints
            'percent_complete': float,     # Percentage complete (0-100)
            'waypoints_remaining': int,    # Waypoints left
            'current_waypoint': str,       # Current system name
            'next_waypoint': str or None   # Next system name (None if at end)
        }
        
    Example:
        progress = galaxygps_api.get_route_progress()
        if progress:
            print(f"{progress['percent_complete']:.1f}% complete")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'route') or not instance.route:
        return None
    
    try:
        offset = instance.offset if hasattr(instance, 'offset') else 0
        total = len(instance.route)
        
        current_waypoint = instance.route[offset] if 0 <= offset < total else None
        next_waypoint = instance.route[offset + 1] if offset + 1 < total else None
        
        return {
            'current_index': offset,
            'total_waypoints': total,
            'percent_complete': (offset / total * 100) if total > 0 else 0.0,
            'waypoints_remaining': max(0, total - offset),
            'current_waypoint': current_waypoint,
            'next_waypoint': next_waypoint
        }
    except Exception as e:
        logger.error(f"[GalaxyGPS API] Error getting route progress: {e}")
        return None


# =============================================================================
# FLEET CARRIER API
# =============================================================================

def get_fleet_carriers() -> Optional[List[Dict[str, Any]]]:
    """
    Get list of all tracked fleet carriers.
    
    Returns:
        List of dictionaries containing carrier information, or None if error.
        Returns a deep copy to prevent external modification.
        
        Each carrier dictionary contains:
        {
            'callsign': str,               # Carrier callsign (e.g., "ABC-123")
            'name': str,                   # Carrier name
            'current_system': str,         # Current system name
            'system_address': str,         # System address
            'fuel': int,                   # Tritium fuel amount
            'balance': int,                # Credit balance
            'state': str,                  # Carrier state
            'theme': str,                  # Carrier theme
            'docking_access': str,         # Docking access level
            'notorious_access': str,       # Notorious access setting
            'cargo_count': int,            # Number of cargo items
            'cargo_value': int,            # Total cargo value
            'tritium_in_cargo': int,       # Tritium in cargo hold
            'icy_rings': bool,             # Has icy rings nearby
            'pristine': bool,              # Has pristine reserves nearby
            'last_updated': str,           # Last update timestamp
            'source_galaxy': str           # Galaxy (Live/Legacy/Beta)
        }
        
    Example:
        carriers = galaxygps_api.get_fleet_carriers()
        if carriers:
            for carrier in carriers:
                print(f"{carrier['callsign']}: {carrier['name']}")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'fleet_carrier_manager'):
        return None
    
    try:
        carriers_dict = instance.fleet_carrier_manager.get_all_carriers()
        if not carriers_dict:
            return []
        
        # Convert dict to list and return deep copy
        carriers_list = list(carriers_dict.values())
        return deepcopy(carriers_list)
    except Exception as e:
        logger.error(f"[GalaxyGPS API] Error getting fleet carriers: {e}")
        return None


def get_fleet_carrier(callsign: str) -> Optional[Dict[str, Any]]:
    """
    Get information for a specific fleet carrier.
    
    Args:
        callsign: Fleet carrier callsign (e.g., "ABC-123")
        
    Returns:
        Dictionary containing carrier information (see get_fleet_carriers for format),
        or None if carrier not found or error.
        Returns a deep copy to prevent external modification.
        
    Example:
        carrier = galaxygps_api.get_fleet_carrier("ABC-123")
        if carrier:
            print(f"Carrier location: {carrier['current_system']}")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'fleet_carrier_manager'):
        return None
    
    try:
        carrier = instance.fleet_carrier_manager.get_carrier(callsign)
        return deepcopy(carrier) if carrier else None
    except Exception as e:
        logger.error(f"[GalaxyGPS API] Error getting fleet carrier {callsign}: {e}")
        return None


def get_selected_fleet_carrier() -> Optional[Dict[str, Any]]:
    """
    Get the currently selected fleet carrier in the GalaxyGPS UI.
    
    Returns:
        Dictionary containing carrier information (see get_fleet_carriers for format),
        or None if no carrier selected or error.
        Returns a deep copy to prevent external modification.
        
    Example:
        carrier = galaxygps_api.get_selected_fleet_carrier()
        if carrier:
            print(f"Selected: {carrier['callsign']}")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'selected_fleet_carrier'):
        return None
    
    try:
        callsign = instance.selected_fleet_carrier
        if not callsign:
            return None
        
        carrier = instance.fleet_carrier_manager.get_carrier(callsign)
        return deepcopy(carrier) if carrier else None
    except Exception as e:
        logger.error(f"[GalaxyGPS API] Error getting selected fleet carrier: {e}")
        return None


def get_fleet_carrier_cargo(callsign: str) -> Optional[List[Dict[str, Any]]]:
    """
    Get cargo details for a specific fleet carrier.
    
    Args:
        callsign: Fleet carrier callsign (e.g., "ABC-123")
        
    Returns:
        List of dictionaries containing cargo information, or None if error.
        Returns a deep copy to prevent external modification.
        
        Each cargo dictionary contains:
        {
            'commodity': str,              # Commodity name
            'localized_name': str,         # Localized commodity name
            'quantity': int,               # Quantity in cargo
            'value': int                   # Total value
        }
        
    Example:
        cargo = galaxygps_api.get_fleet_carrier_cargo("ABC-123")
        if cargo:
            for item in cargo:
                print(f"{item['localized_name']}: {item['quantity']}")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'cargo_manager'):
        return None
    
    try:
        cargo = instance.cargo_manager.get_cargo_for_carrier(callsign)
        return deepcopy(cargo) if cargo else []
    except Exception as e:
        logger.error(f"[GalaxyGPS API] Error getting cargo for {callsign}: {e}")
        return None


def get_fleet_carrier_ships(callsign: str) -> Optional[List[Dict[str, Any]]]:
    """
    Get stored ships for a specific fleet carrier.
    
    Args:
        callsign: Fleet carrier callsign (e.g., "ABC-123")
        
    Returns:
        List of dictionaries containing ship information, or None if error.
        Returns a deep copy to prevent external modification.
        
        Each ship dictionary contains:
        {
            'ship_type': str,              # Ship type (e.g., "Anaconda")
            'ship_name': str,              # Custom ship name
            'ship_id': str,                # Unique ship ID
            'last_updated': str            # Last update timestamp
        }
        
    Example:
        ships = galaxygps_api.get_fleet_carrier_ships("ABC-123")
        if ships:
            print(f"Carrier has {len(ships)} ships stored")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'ships_manager'):
        return None
    
    try:
        ships = instance.ships_manager.get_ships_for_carrier(callsign)
        return deepcopy(ships) if ships else []
    except Exception as e:
        logger.error(f"[GalaxyGPS API] Error getting ships for {callsign}: {e}")
        return None


# =============================================================================
# PLAYER STATE API
# =============================================================================

def get_current_system() -> Optional[str]:
    """
    Get the player's current system name.
    
    Returns:
        System name (string) or None if not available
        
    Example:
        system = galaxygps_api.get_current_system()
        if system:
            print(f"Current system: {system}")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'system'):
        return None
    
    return instance.system if instance.system else None


def get_current_station() -> Optional[str]:
    """
    Get the player's current station name.
    
    Returns:
        Station name (string) or None if not docked
        
    Example:
        station = galaxygps_api.get_current_station()
        if station:
            print(f"Docked at: {station}")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'station'):
        return None
    
    return instance.station if instance.station else None


def is_docked() -> bool:
    """
    Check if the player is currently docked.
    
    Returns:
        True if docked, False otherwise
        
    Example:
        if galaxygps_api.is_docked():
            print("Player is docked")
    """
    instance = _get_instance()
    if not instance or not hasattr(instance, 'station'):
        return False
    
    return bool(instance.station)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_api_info() -> Dict[str, str]:
    """
    Get information about the GalaxyGPS API.
    
    Returns:
        Dictionary containing API metadata:
        {
            'api_version': str,            # API version
            'plugin_version': str,         # Plugin version
            'available': bool,             # Whether API is available
            'description': str             # API description
        }
        
    Example:
        info = galaxygps_api.get_api_info()
        print(f"GalaxyGPS API v{info['api_version']}")
    """
    return {
        'api_version': API_VERSION,
        'plugin_version': get_plugin_version() or "Unknown",
        'available': is_available(),
        'description': 'GalaxyGPS Public API for EDMC plugins'
    }


# =============================================================================
# DEPRECATED / INTERNAL - DO NOT USE
# =============================================================================

def _get_raw_instance():
    """
    INTERNAL USE ONLY - Get raw GalaxyGPS instance.
    
    This function is for internal use only and may be removed in future versions.
    Other plugins should use the public API functions instead.
    
    Returns:
        GalaxyGPS instance or None
    """
    logger.warning("[GalaxyGPS API] _get_raw_instance() called - this is for internal use only")
    return _get_instance()
