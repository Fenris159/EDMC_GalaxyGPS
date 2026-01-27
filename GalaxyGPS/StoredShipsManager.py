import csv
import logging
import os
import traceback
from datetime import datetime
from typing import Dict, List, Optional

from config import appname  # type: ignore

# We need a name of plugin dir, not StoredShipsManager.py dir
plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
logger = logging.getLogger(f'{appname}.{plugin_name}')


class StoredShipsManager:
    """
    Manages stored ships information from StoredShips journal events.
    Tracks ships stored at fleet carriers (identified by StationName/MarketID).
    """
    
    # CSV column headers
    CSV_HEADERS = [
        'Callsign',
        'Ship Type',
        'Ship ID',
        'Ship Name',
        'Star System',
        'Ship Market ID',
        'Location Type',
        'Last Updated'
    ]
    
    def __init__(self, plugin_dir: str):
        """
        Initialize the StoredShipsManager.
        
        Args:
            plugin_dir: Directory where the plugin is installed
        """
        self.plugin_dir = plugin_dir
        self.ships_file = os.path.join(plugin_dir, 'fleet_carrier_ships.csv')
        # Keyed by callsign, value is dict of ShipID -> ship data
        self.ships: Dict[str, Dict[str, Dict]] = {}
        
        # Load existing ships data
        self.load_ships()
    
    def load_ships(self) -> None:
        """
        Load stored ships data from CSV file.
        """
        if not os.path.exists(self.ships_file):
            logger.debug("No existing fleet carrier ships file found")
            return
        
        try:
            with open(self.ships_file, 'r', encoding='utf-8-sig', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    callsign = row.get('Callsign', '').strip()
                    ship_id = row.get('Ship ID', '').strip()
                    
                    if callsign and ship_id:
                        if callsign not in self.ships:
                            self.ships[callsign] = {}
                        
                        self.ships[callsign][ship_id] = {
                            'callsign': callsign,
                            'ship_type': row.get('Ship Type', ''),
                            'ship_id': ship_id,
                            'ship_name': row.get('Ship Name', ''),
                            'star_system': row.get('Star System', ''),
                            'ship_market_id': row.get('Ship Market ID', ''),
                            'location_type': row.get('Location Type', ''),
                            'last_updated': row.get('Last Updated', '')
                        }
            
            total_ships = sum(len(ships) for ships in self.ships.values())
            logger.info(f"Loaded stored ships for {len(self.ships)} carrier(s), {total_ships} total ships")
        
        except Exception:
            logger.warning('!! Error loading stored ships: ' + traceback.format_exc(), exc_info=False)
    
    def save_ships(self) -> None:
        """
        Save stored ships data to CSV file.
        """
        try:
            with open(self.ships_file, 'w', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                
                # Flatten nested dict structure for CSV output
                for callsign in sorted(self.ships.keys()):
                    for ship_id in sorted(self.ships[callsign].keys()):
                        ship = self.ships[callsign][ship_id]
                        writer.writerow({
                            'Callsign': ship.get('callsign', ''),
                            'Ship Type': ship.get('ship_type', ''),
                            'Ship ID': ship.get('ship_id', ''),
                            'Ship Name': ship.get('ship_name', ''),
                            'Star System': ship.get('star_system', ''),
                            'Ship Market ID': ship.get('ship_market_id', ''),
                            'Location Type': ship.get('location_type', ''),
                            'Last Updated': ship.get('last_updated', '')
                        })
            
            total_ships = sum(len(ships) for ships in self.ships.values())
            logger.debug(f"Saved stored ships for {len(self.ships)} carrier(s), {total_ships} total ships")
        
        except Exception:
            logger.warning('!! Error saving stored ships: ' + traceback.format_exc(), exc_info=False)
    
    def _extract_callsign_from_station(self, station_name: str) -> Optional[str]:
        """
        Extract fleet carrier callsign from station name.
        
        Args:
            station_name: Station name (e.g., "MY CARRIER V5H-J7W")
            
        Returns:
            Callsign if found (e.g., "V5H-J7W"), None otherwise
        """
        if not station_name:
            return None
        
        # Fleet carrier callsign pattern: XXX-XXX (alphanumeric)
        import re
        match = re.search(r'([A-Z0-9]{3}-[A-Z0-9]{3})', station_name.upper())
        if match:
            return match.group(1)
        
        return None
    
    def update_from_journal_event(self, event_data: Dict, known_carriers: List[str]) -> bool:
        """
        Update stored ships from StoredShips journal event.
        Only processes ships stored at known fleet carriers.
        
        Args:
            event_data: StoredShips journal event data
            known_carriers: List of known carrier callsigns (from FleetCarrierManager)
            
        Returns:
            True if any carrier ships were updated
        """
        try:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            updated = False
            
            # Get current location info from event
            current_system = event_data.get('StarSystem', '')
            current_station = event_data.get('StationName', '')
            current_market_id = str(event_data.get('MarketID', ''))
            
            # Extract callsign from current station if it's a fleet carrier
            current_callsign = self._extract_callsign_from_station(current_station)
            
            # Process ShipsHere (ships at current location)
            ships_here = event_data.get('ShipsHere', [])
            if isinstance(ships_here, list) and current_callsign and current_callsign in known_carriers:
                # Clear existing ships for this carrier (we're replacing with fresh data)
                if current_callsign in self.ships:
                    self.ships[current_callsign] = {}
                else:
                    self.ships[current_callsign] = {}
                
                for ship in ships_here:
                    if not isinstance(ship, dict):
                        continue
                    
                    ship_id = str(ship.get('ShipID', ''))
                    if not ship_id:
                        continue
                    
                    self.ships[current_callsign][ship_id] = {
                        'callsign': current_callsign,
                        'ship_type': ship.get('ShipType', ''),
                        'ship_id': ship_id,
                        'ship_name': ship.get('Name', ''),
                        'star_system': current_system,
                        'ship_market_id': current_market_id,
                        'location_type': 'Here',
                        'last_updated': timestamp
                    }
                    updated = True
            
            # Process ShipsRemote (ships stored elsewhere)
            ships_remote = event_data.get('ShipsRemote', [])
            if isinstance(ships_remote, list):
                for ship in ships_remote:
                    if not isinstance(ship, dict):
                        continue
                    
                    ship_id = str(ship.get('ShipID', ''))
                    if not ship_id:
                        continue
                    
                    # Check if this ship is at a known fleet carrier
                    ship_system = ship.get('StarSystem', '')
                    ship_market_id = str(ship.get('ShipMarketID', ''))
                    
                    # Try to match by MarketID or infer from system name
                    # For now, we skip ShipsRemote unless we can definitively match to a carrier
                    # This prevents us from storing ships at stations we don't own
                    
                    # Note: If a ship is "in transit" or at an unknown location,
                    # the StarSystem and ShipMarketID fields may be absent
                    
                    # We could enhance this later to match MarketIDs from CAPI if needed
                    pass
            
            if updated:
                logger.info(f"Updated stored ships from StoredShips event for carrier {current_callsign}")
                self.save_ships()
            
            return updated
        
        except Exception:
            logger.warning('!! Error updating ships from StoredShips event: ' + traceback.format_exc(), exc_info=False)
            return False
    
    def get_ships_for_carrier(self, callsign: str) -> List[Dict]:
        """
        Get all stored ships for a specific carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            List of ship dictionaries
        """
        if callsign not in self.ships:
            return []
        
        return list(self.ships[callsign].values())
    
    def get_ship_count(self, callsign: str) -> int:
        """
        Get number of ships stored at a carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            Number of ships
        """
        if callsign not in self.ships:
            return 0
        
        return len(self.ships[callsign])
    
    def clear_ships_for_carrier(self, callsign: str) -> bool:
        """
        Clear all ship data for a specific carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            True if cleared, False if carrier not found
        """
        if callsign in self.ships:
            del self.ships[callsign]
            self.save_ships()
            logger.info(f"Cleared stored ships for carrier {callsign}")
            return True
        return False
    
    def get_ship_by_id(self, ship_id: str) -> Optional[Dict]:
        """
        Find a ship by its ShipID across all carriers.
        
        Args:
            ship_id: Ship ID to search for
            
        Returns:
            Ship dictionary if found, None otherwise
        """
        for callsign, ships in self.ships.items():
            if ship_id in ships:
                return ships[ship_id]
        
        return None
