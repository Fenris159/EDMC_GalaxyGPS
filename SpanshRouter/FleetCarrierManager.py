import csv
import logging
import os
import re
import traceback
from datetime import datetime
from typing import Dict, List, Optional

from config import appname  # type: ignore

# We need a name of plugin dir, not FleetCarrierManager.py dir
plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
logger = logging.getLogger(f'{appname}.{plugin_name}')


class FleetCarrierManager:
    """
    Manages fleet carrier data from CAPI, storing it in CSV format.
    """
    
    # CSV column headers
    CSV_HEADERS = [
        'Callsign',
        'Name',
        'Current System',
        'System Address',
        'Fuel (Tritium)',
        'Balance',
        'State',
        'Theme',
        'Docking Access',
        'Notorious Access',
        'Cargo Count',
        'Cargo Total Value',
        'Tritium in Cargo',
        'Icy Rings',
        'Pristine',
        'Last Updated',
        'Source Galaxy'
    ]
    
    def __init__(self, plugin_dir: str):
        """
        Initialize the FleetCarrierManager.
        
        Args:
            plugin_dir: Directory where the plugin is installed
        """
        self.plugin_dir = plugin_dir
        self.carriers_file = os.path.join(plugin_dir, 'fleet_carriers.csv')
        self.carriers: Dict[str, Dict] = {}  # Keyed by callsign
        
        # Load existing carrier data
        self.load_carriers()
    
    def load_carriers(self) -> None:
        """
        Load fleet carrier data from CSV file.
        """
        if not os.path.exists(self.carriers_file):
            logger.info("No existing fleet carriers file found")
            return
        
        try:
            with open(self.carriers_file, 'r', encoding='utf-8-sig', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Create case-insensitive fieldname mapping
                if reader.fieldnames:
                    fieldname_map = {name.lower(): name for name in reader.fieldnames}
                else:
                    fieldname_map = {}
                
                def get_field(row, field_name, default=""):
                    """Get field value from row using case-insensitive lookup"""
                    key = fieldname_map.get(field_name.lower(), field_name)
                    return row.get(key, default)
                
                for row in reader:
                    callsign = get_field(row, 'Callsign', '').strip()
                    if callsign:
                        self.carriers[callsign] = {
                            'callsign': callsign,
                            'name': get_field(row, 'Name', ''),
                            'current_system': get_field(row, 'Current System', ''),
                            'system_address': get_field(row, 'System Address', ''),
                            'fuel': get_field(row, 'Fuel (Tritium)', '0'),
                            'balance': get_field(row, 'Balance', '0'),
                            'state': get_field(row, 'State', ''),
                            'theme': get_field(row, 'Theme', ''),
                            'docking_access': get_field(row, 'Docking Access', ''),
                            'notorious_access': get_field(row, 'Notorious Access', ''),
                            'cargo_count': get_field(row, 'Cargo Count', '0'),
                            'cargo_total_value': get_field(row, 'Cargo Total Value', '0'),
                            'tritium_in_cargo': get_field(row, 'Tritium in Cargo', '0'),
                            'icy_rings': get_field(row, 'Icy Rings', ''),
                            'pristine': get_field(row, 'Pristine', ''),
                            'last_updated': get_field(row, 'Last Updated', ''),
                            'source_galaxy': get_field(row, 'Source Galaxy', '')
                        }
            
            logger.info(f"Loaded {len(self.carriers)} fleet carrier(s) from CSV")
        
        except Exception:
            logger.warning('!! Error loading fleet carriers: ' + traceback.format_exc(), exc_info=False)
    
    def save_carriers(self) -> None:
        """
        Save fleet carrier data to CSV file.
        """
        try:
            with open(self.carriers_file, 'w', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                
                for carrier in sorted(self.carriers.values(), key=lambda x: x.get('callsign', '')):
                    writer.writerow({
                        'Callsign': carrier.get('callsign', ''),
                        'Name': carrier.get('name', ''),
                        'Current System': carrier.get('current_system', ''),
                        'System Address': carrier.get('system_address', ''),
                        'Fuel (Tritium)': carrier.get('fuel', '0'),
                        'Balance': carrier.get('balance', '0'),
                        'State': carrier.get('state', ''),
                        'Theme': carrier.get('theme', ''),
                        'Docking Access': carrier.get('docking_access', ''),
                        'Notorious Access': carrier.get('notorious_access', ''),
                        'Cargo Count': carrier.get('cargo_count', '0'),
                        'Cargo Total Value': carrier.get('cargo_total_value', '0'),
                        'Tritium in Cargo': carrier.get('tritium_in_cargo', '0'),
                        'Icy Rings': carrier.get('icy_rings', ''),
                        'Pristine': carrier.get('pristine', ''),
                        'Last Updated': carrier.get('last_updated', ''),
                        'Source Galaxy': carrier.get('source_galaxy', '')
                    })
            
            logger.debug(f"Saved {len(self.carriers)} fleet carrier(s) to CSV")
        
        except Exception:
            logger.warning('!! Error saving fleet carriers: ' + traceback.format_exc(), exc_info=False)
    
    def update_carrier_from_capi(self, data, source_galaxy: str) -> None:
        """
        Update fleet carrier data from CAPI response.
        
        Args:
            data: CAPIData object containing fleet carrier information
            source_galaxy: Source galaxy (SERVER_LIVE, SERVER_BETA, SERVER_LEGACY)
        """
        try:
            # Extract carrier information from CAPI data
            # CAPIData is a UserDict subclass, so we can access it directly like a dict
            # The data is already the fleet carrier data, not nested under 'data'
            carrier_data = data
            
            # Get callsign (required identifier)
            name_info = carrier_data.get('name', {})
            if isinstance(name_info, dict):
                callsign = name_info.get('callsign', '')
            else:
                callsign = ''
            
            if not callsign:
                logger.warning("CAPI fleet carrier data missing callsign")
                return
            
            # Get current system - can be a string or dict
            current_star_system = carrier_data.get('currentStarSystem', '')
            current_system = ''
            system_address = ''
            
            if isinstance(current_star_system, dict):
                current_system = current_star_system.get('name', '')
                system_address = str(current_star_system.get('id', ''))
            elif isinstance(current_star_system, str):
                current_system = current_star_system
            
            # Get fuel (Tritium)
            fuel = str(carrier_data.get('fuel', 0))
            
            # Get balance
            balance = str(carrier_data.get('balance', 0))
            
            # Get state
            state = carrier_data.get('state', '')
            
            # Get theme
            theme = carrier_data.get('theme', '')
            
            # Get docking access
            docking_access = carrier_data.get('dockingAccess', '')
            
            # Get notorious access
            notorious_access = str(carrier_data.get('notoriousAccess', False))
            
            # Calculate cargo information
            cargo = carrier_data.get('cargo', [])
            cargo_count = len(cargo) if isinstance(cargo, list) else 0
            cargo_total_value = 0
            tritium_in_cargo = 0
            if isinstance(cargo, list):
                try:
                    cargo_total_value = sum(
                        int(item.get('value', 0)) * int(item.get('qty', 0))
                        for item in cargo
                        if isinstance(item, dict) and item.get('value') and item.get('qty')
                    )
                    # Count Tritium in cargo
                    for item in cargo:
                        if isinstance(item, dict):
                            commodity_name = item.get('commodity', '').lower()
                            # Check both 'commodity' field and 'locName' field for Tritium
                            if commodity_name == 'tritium' or item.get('locName', '').lower() == 'tritium':
                                qty = item.get('qty', 0)
                                try:
                                    tritium_in_cargo = int(qty)
                                    break  # Found Tritium, no need to continue
                                except (ValueError, TypeError):
                                    pass
                except (ValueError, TypeError):
                    logger.warning("Error calculating cargo total value")
                    cargo_total_value = 0
            
            # Get carrier name (filtered vanity name)
            carrier_name = ''
            if isinstance(name_info, dict):
                # Try filtered name first, then unfiltered
                carrier_name = name_info.get('filteredVanityName', '') or name_info.get('vanityName', '')
                # Decode hex-encoded name if needed
                if carrier_name:
                    # Remove '0x' prefix if present
                    hex_str = carrier_name[2:] if carrier_name.startswith('0x') else carrier_name
                    try:
                        # Try to decode as hex
                        decoded = bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
                        if decoded:
                            carrier_name = decoded
                    except (ValueError, TypeError):
                        # If not hex, use as-is
                        pass
            
            # Preserve existing rings status if carrier already exists (don't overwrite on CAPI update)
            existing_carrier = self.carriers.get(callsign, {})
            icy_rings = existing_carrier.get('icy_rings', '')
            pristine = existing_carrier.get('pristine', '')
            
            # Update carrier record
            self.carriers[callsign] = {
                'callsign': callsign,
                'name': carrier_name,
                'current_system': current_system,
                'system_address': system_address,
                'fuel': fuel,
                'balance': balance,
                'state': state,
                'theme': theme,
                'docking_access': docking_access,
                'notorious_access': notorious_access,
                'cargo_count': str(cargo_count),
                'cargo_total_value': str(cargo_total_value),
                'tritium_in_cargo': str(tritium_in_cargo),
                'icy_rings': icy_rings,  # Preserve existing or empty string
                'pristine': pristine,  # Preserve existing or empty string
                'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                'source_galaxy': source_galaxy
            }
            
            logger.info(f"Updated fleet carrier {callsign} ({carrier_name}) in {current_system}")
            
            # Save to CSV
            self.save_carriers()
        
        except Exception:
            logger.warning('!! Error updating fleet carrier from CAPI: ' + traceback.format_exc(), exc_info=False)
    
    def get_carrier(self, callsign: str) -> Optional[Dict]:
        """
        Get fleet carrier information by callsign.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            Dictionary with carrier information or None if not found
        """
        return self.carriers.get(callsign)
    
    def get_all_carriers(self) -> List[Dict]:
        """
        Get all fleet carriers.
        
        Returns:
            List of carrier dictionaries
        """
        return list(self.carriers.values())
    
    def get_carrier_by_system(self, system_name: str) -> List[Dict]:
        """
        Get all fleet carriers in a specific system.
        
        Args:
            system_name: System name to search for
            
        Returns:
            List of carrier dictionaries in that system
        """
        return [
            carrier for carrier in self.carriers.values()
            if carrier.get('current_system', '').lower() == system_name.lower()
        ]
    
    def get_carrier_cargo_details(self, callsign: str) -> List[Dict]:
        """
        Get detailed cargo information for a carrier.
        Note: This requires the full CAPI data, so we'll need to store it separately
        or retrieve it when needed. For now, this is a placeholder.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            List of cargo items (empty for now, as we only store summary)
        """
        # TODO: Implement if detailed cargo storage is needed
        return []
    
    def remove_carrier(self, callsign: str) -> bool:
        """
        Remove a fleet carrier from the list.
        
        Args:
            callsign: Fleet carrier callsign to remove
            
        Returns:
            True if removed, False if not found
        """
        if callsign in self.carriers:
            del self.carriers[callsign]
            self.save_carriers()
            logger.info(f"Removed fleet carrier {callsign}")
            return True
        return False
    
    def format_carrier_info(self, callsign: str) -> str:
        """
        Format carrier information as a readable string.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            Formatted string with carrier information
        """
        carrier = self.get_carrier(callsign)
        if not carrier:
            return f"Carrier {callsign} not found"
        
        info_lines = [
            f"Fleet Carrier: {carrier.get('name', 'Unknown')} ({callsign})",
            f"Location: {carrier.get('current_system', 'Unknown')}",
            f"Fuel (Tritium): {carrier.get('fuel', '0')}",
            f"Balance: {carrier.get('balance', '0')} credits",
            f"State: {carrier.get('state', 'Unknown')}",
            f"Cargo: {carrier.get('cargo_count', '0')} items (Value: {carrier.get('cargo_total_value', '0')} credits)",
            f"Last Updated: {carrier.get('last_updated', 'Unknown')}",
            f"Galaxy: {carrier.get('source_galaxy', 'Unknown')}"
        ]
        
        return "\n".join(info_lines)
    
    def find_carrier_for_journal_event(self, event_data: Dict, state: Optional[Dict] = None) -> Optional[str]:
        """
        Try to identify which carrier a journal event belongs to.
        
        Args:
            event_data: Journal event data
            state: Current game state (optional, for Location events)
            
        Returns:
            Carrier callsign if found, None otherwise
        """
        # Method 1: Check if event has MarketID and match by station name pattern
        # Fleet carrier station names often contain the callsign
        
        # Method 2: If Location event and docked at fleet carrier
        # Method 3: Use CarrierID if stored from CAPI
        
        # For now, use most recently updated carrier as fallback
        # This works well if you only have one carrier
        
        # Check if we can extract callsign from station name
        station_name = event_data.get('StationName', '')
        if station_name and 'FC' in station_name.upper():
            # Try to extract callsign pattern (e.g., "A1A-A1A" or "FC A1A-A1A")
            callsign_match = re.search(r'([A-Z0-9]+-[A-Z0-9]+)', station_name.upper())
            if callsign_match:
                potential_callsign = callsign_match.group(1)
                if potential_callsign in self.carriers:
                    return potential_callsign
        
        # Check CarrierID if available
        carrier_id = event_data.get('CarrierID')
        if carrier_id:
            # We'd need to store CarrierID from CAPI to match this
            # For now, skip this method
        
        # Use state data if available (Location/Cargo events)
        if state:
            station_name_from_state = state.get('StationName', '')
            station_type = state.get('StationType', '')
            if station_type and 'fleetcarrier' in station_type.lower():
                # Try to extract callsign from station name
                if station_name_from_state:
                    callsign_match = re.search(r'([A-Z0-9]+-[A-Z0-9]+)', station_name_from_state.upper())
                    if callsign_match:
                        potential_callsign = callsign_match.group(1)
                        if potential_callsign in self.carriers:
                            return potential_callsign
                # Also check event_data for station name
                if station_name:
                    callsign_match = re.search(r'([A-Z0-9]+-[A-Z0-9]+)', station_name.upper())
                    if callsign_match:
                        potential_callsign = callsign_match.group(1)
                        if potential_callsign in self.carriers:
                            return potential_callsign
        
        # Fallback: return most recently updated carrier
        if self.carriers:
            sorted_carriers = sorted(
                self.carriers.values(),
                key=lambda x: x.get('last_updated', ''),
                reverse=True
            )
            return sorted_carriers[0].get('callsign', '')
        
        return None
    
    def update_carrier_from_journal(self, event_name: str, event_data: Dict, state: Optional[Dict] = None, source_galaxy: str = 'Live') -> bool:
        """
        Update fleet carrier data from journal events (fallback to CAPI data).
        Only updates if carrier already exists in our records (from CAPI).
        
        Args:
            event_name: Name of the journal event
            event_data: Dictionary containing journal event data
            state: Current game state (optional, for additional context)
            source_galaxy: Source galaxy (Live/Beta/Legacy)
            
        Returns:
            True if carrier was updated, False if not found or event not supported
        """
        # Find which carrier this event belongs to
        callsign = self.find_carrier_for_journal_event(event_data, state)
        
        if not callsign or callsign not in self.carriers:
            return False
        
        updated = False
        
        try:
            if event_name == 'CarrierJump':
                # Update location from jump event
                new_system = event_data.get('StarSystem', '').strip()
                new_system_address = str(event_data.get('SystemAddress', ''))
                
                if new_system:
                    old_system = self.carriers[callsign].get('current_system', '')
                    self.carriers[callsign]['current_system'] = new_system
                    if new_system_address:
                        self.carriers[callsign]['system_address'] = new_system_address
                    # Clear rings status when system changes (will need to be re-queried)
                    self.carriers[callsign]['icy_rings'] = ''
                    self.carriers[callsign]['pristine'] = ''
                    self.carriers[callsign]['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                    updated = True
                    logger.info(f"Updated carrier {callsign} location from CarrierJump: {old_system} -> {new_system} (rings status cleared)")
            
            elif event_name == 'CarrierDepositFuel':
                # Update fuel level
                total_fuel = event_data.get('Total')
                if total_fuel is not None:
                    old_fuel = self.carriers[callsign].get('fuel', '0')
                    self.carriers[callsign]['fuel'] = str(total_fuel)
                    self.carriers[callsign]['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                    updated = True
                    logger.info(f"Updated carrier {callsign} fuel from CarrierDepositFuel: {old_fuel} -> {total_fuel}")
            
            elif event_name == 'CarrierStats':
                # Comprehensive stats update
                fuel_level = event_data.get('FuelLevel')
                carrier_balance = event_data.get('CarrierBalance')
                
                if fuel_level is not None:
                    self.carriers[callsign]['fuel'] = str(fuel_level)
                    updated = True
                
                if carrier_balance is not None:
                    self.carriers[callsign]['balance'] = str(carrier_balance)
                    updated = True
                
                # Update cargo from SpaceUsage
                space_usage = event_data.get('SpaceUsage', {})
                if isinstance(space_usage, dict):
                    cargo_for_sale = space_usage.get('CargoForSale', 0)
                    cargo_not_for_sale = space_usage.get('CargoNotForSale', 0)
                    # This gives us total cargo items, but not value
                    total_cargo = cargo_for_sale + cargo_not_for_sale
                    if total_cargo >= 0:
                        self.carriers[callsign]['cargo_count'] = str(total_cargo)
                        updated = True
                
                if updated:
                    self.carriers[callsign]['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                    logger.info(f"Updated carrier {callsign} stats from CarrierStats")
            
            elif event_name == 'Cargo':
                # Cargo event - update cargo count and value
                # Only update if we're at a fleet carrier station
                inventory = event_data.get('Inventory', [])
                if isinstance(inventory, list):
                    cargo_count = len(inventory)
                    # Calculate total value if possible
                    cargo_value = 0
                    tritium_in_cargo = 0
                    try:
                        cargo_value = sum(
                            int(item.get('Value', 0)) * int(item.get('Count', 0))
                            for item in inventory
                            if isinstance(item, dict) and item.get('Value') and item.get('Count')
                        )
                        # Count Tritium in cargo
                        for item in inventory:
                            if isinstance(item, dict):
                                name = item.get('Name', '').lower()
                                if name == 'tritium':
                                    count = item.get('Count', 0)
                                    try:
                                        tritium_in_cargo = int(count)
                                        break  # Found Tritium, no need to continue
                                    except (ValueError, TypeError):
                                        pass
                    except (ValueError, TypeError):
                        pass
                    
                    self.carriers[callsign]['cargo_count'] = str(cargo_count)
                    self.carriers[callsign]['cargo_total_value'] = str(cargo_value)
                    self.carriers[callsign]['tritium_in_cargo'] = str(tritium_in_cargo)
                    self.carriers[callsign]['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                    updated = True
                    logger.info(f"Updated carrier {callsign} cargo from Cargo event: {cargo_count} items, {cargo_value} cr, Tritium: {tritium_in_cargo}")
            
            # Save to CSV if updated
            if updated:
                self.save_carriers()
                return True
            
        except Exception:
            logger.warning(f'!! Error updating carrier from journal event {event_name}: ' + traceback.format_exc(), exc_info=False)
        
        return False
    
    def update_rings_status(self, callsign: str, has_icy_rings: bool, has_pristine: bool) -> bool:
        """
        Update the Icy Rings and Pristine status for a carrier.
        
        Args:
            callsign: Fleet carrier callsign
            has_icy_rings: True if system has Icy rings
            has_pristine: True if system has Pristine Icy rings
            
        Returns:
            True if updated, False if carrier not found
        """
        if callsign not in self.carriers:
            return False
        
        try:
            # Store as 'Yes' or 'No' strings
            self.carriers[callsign]['icy_rings'] = 'Yes' if has_icy_rings else 'No'
            self.carriers[callsign]['pristine'] = 'Yes' if has_pristine else 'No'
            self.carriers[callsign]['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            
            # Save to CSV
            self.save_carriers()
            
            logger.info(f"Updated carrier {callsign} rings status: Icy Rings={has_icy_rings}, Pristine={has_pristine}")
            return True
        
        except Exception:
            logger.warning(f'!! Error updating rings status for carrier {callsign}: ' + traceback.format_exc(), exc_info=False)
            return False
    
    def get_carrier_by_id(self, carrier_id: int) -> Optional[Dict]:
        """
        Get fleet carrier by carrier ID (stored from CAPI data).
        Note: This requires storing CarrierID from CAPI.
        
        Args:
            carrier_id: Fleet carrier ID
            
        Returns:
            Carrier dictionary or None if not found
        """
        # We'd need to store carrier ID from CAPI to use this
        # For now, return None - this can be enhanced later
        return None
