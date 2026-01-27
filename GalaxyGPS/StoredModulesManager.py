import csv
import logging
import os
import traceback
from datetime import datetime
from typing import Dict, List, Optional

from config import appname  # type: ignore

# We need a name of plugin dir, not StoredModulesManager.py dir
plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
logger = logging.getLogger(f'{appname}.{plugin_name}')


class StoredModulesManager:
    """
    Manages stored modules information from StoredModules journal events.
    Tracks modules stored at fleet carriers (identified by StationName/MarketID).
    """
    
    # CSV column headers
    CSV_HEADERS = [
        'Callsign',
        'Storage Slot',
        'Module Name',
        'Module Name Localized',
        'Buy Price',
        'Hot',
        'Star System',
        'Market ID',
        'Engineered',
        'Engineer',
        'Level',
        'Quality',
        'Last Updated'
    ]
    
    def __init__(self, plugin_dir: str):
        """
        Initialize the StoredModulesManager.
        
        Args:
            plugin_dir: Directory where the plugin is installed
        """
        self.plugin_dir = plugin_dir
        self.modules_file = os.path.join(plugin_dir, 'fleet_carrier_modules.csv')
        # Keyed by callsign, value is dict of StorageSlot -> module data
        self.modules: Dict[str, Dict[str, Dict]] = {}
        
        # Load existing modules data
        self.load_modules()
    
    def load_modules(self) -> None:
        """
        Load stored modules data from CSV file.
        """
        if not os.path.exists(self.modules_file):
            logger.debug("No existing fleet carrier modules file found")
            return
        
        try:
            with open(self.modules_file, 'r', encoding='utf-8-sig', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    callsign = row.get('Callsign', '').strip()
                    storage_slot = row.get('Storage Slot', '').strip()
                    
                    if callsign and storage_slot:
                        if callsign not in self.modules:
                            self.modules[callsign] = {}
                        
                        self.modules[callsign][storage_slot] = {
                            'callsign': callsign,
                            'storage_slot': storage_slot,
                            'module_name': row.get('Module Name', ''),
                            'module_name_localized': row.get('Module Name Localized', ''),
                            'buy_price': row.get('Buy Price', '0'),
                            'hot': row.get('Hot', ''),
                            'star_system': row.get('Star System', ''),
                            'market_id': row.get('Market ID', ''),
                            'engineered': row.get('Engineered', ''),
                            'engineer': row.get('Engineer', ''),
                            'level': row.get('Level', ''),
                            'quality': row.get('Quality', ''),
                            'last_updated': row.get('Last Updated', '')
                        }
            
            total_modules = sum(len(mods) for mods in self.modules.values())
            logger.info(f"Loaded stored modules for {len(self.modules)} carrier(s), {total_modules} total modules")
        
        except Exception:
            logger.warning('!! Error loading stored modules: ' + traceback.format_exc(), exc_info=False)
    
    def save_modules(self) -> None:
        """
        Save stored modules data to CSV file.
        """
        try:
            with open(self.modules_file, 'w', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                
                # Flatten nested dict structure for CSV output
                for callsign in sorted(self.modules.keys()):
                    for storage_slot in sorted(self.modules[callsign].keys(), key=lambda x: int(x) if x.isdigit() else 0):
                        module = self.modules[callsign][storage_slot]
                        writer.writerow({
                            'Callsign': module.get('callsign', ''),
                            'Storage Slot': module.get('storage_slot', ''),
                            'Module Name': module.get('module_name', ''),
                            'Module Name Localized': module.get('module_name_localized', ''),
                            'Buy Price': module.get('buy_price', '0'),
                            'Hot': module.get('hot', ''),
                            'Star System': module.get('star_system', ''),
                            'Market ID': module.get('market_id', ''),
                            'Engineered': module.get('engineered', ''),
                            'Engineer': module.get('engineer', ''),
                            'Level': module.get('level', ''),
                            'Quality': module.get('quality', ''),
                            'Last Updated': module.get('last_updated', '')
                        })
            
            total_modules = sum(len(mods) for mods in self.modules.values())
            logger.debug(f"Saved stored modules for {len(self.modules)} carrier(s), {total_modules} total modules")
        
        except Exception:
            logger.warning('!! Error saving stored modules: ' + traceback.format_exc(), exc_info=False)
    
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
        Update stored modules from StoredModules journal event.
        Only processes modules stored at known fleet carriers.
        
        Args:
            event_data: StoredModules journal event data
            known_carriers: List of known carrier callsigns (from FleetCarrierManager)
            
        Returns:
            True if any carrier modules were updated
        """
        try:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            updated_carriers = set()
            
            # Get current location info from event (if available)
            current_system = event_data.get('StarSystem', '')
            current_station = event_data.get('StationName', '')
            current_market_id = str(event_data.get('MarketID', ''))
            
            # Extract callsign from current station if it's a fleet carrier
            current_callsign = self._extract_callsign_from_station(current_station)
            
            # Process Items array
            items = event_data.get('Items', [])
            if not isinstance(items, list):
                return False
            
            # Group modules by location (MarketID or inferred callsign)
            # Modules can be at different locations
            modules_by_callsign: Dict[str, List[Dict]] = {}
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                storage_slot = str(item.get('StorageSlot', ''))
                if not storage_slot:
                    continue
                
                # Check if module has location information
                module_system = item.get('StarSystem', '')
                module_market_id = str(item.get('MarketID', ''))
                
                # If module is at current location and it's a known carrier
                if current_callsign and current_callsign in known_carriers:
                    if not module_system or module_system == current_system:
                        # Module is at current carrier
                        if current_callsign not in modules_by_callsign:
                            modules_by_callsign[current_callsign] = []
                        modules_by_callsign[current_callsign].append(item)
                        continue
                
                # If module has location info, try to match to a known carrier
                # (This is tricky - we'd need to match MarketID to carrier)
                # For now, we only process modules at the current location if it's a carrier
                
                # Note: Modules "in transit" won't have StarSystem/MarketID
            
            # Update modules for each carrier
            for callsign, carrier_items in modules_by_callsign.items():
                # Clear existing modules for this carrier (replace with fresh data)
                self.modules[callsign] = {}
                
                for item in carrier_items:
                    storage_slot = str(item.get('StorageSlot', ''))
                    
                    # Check if module is engineered
                    engineer_mods = item.get('EngineerModifications', '')
                    is_engineered = bool(engineer_mods)
                    
                    self.modules[callsign][storage_slot] = {
                        'callsign': callsign,
                        'storage_slot': storage_slot,
                        'module_name': item.get('Name', ''),
                        'module_name_localized': item.get('Name_Localised', item.get('Name', '')),
                        'buy_price': str(item.get('BuyPrice', 0)),
                        'hot': str(item.get('Hot', False)),
                        'star_system': item.get('StarSystem', current_system),
                        'market_id': item.get('MarketID', current_market_id),
                        'engineered': str(is_engineered),
                        'engineer': engineer_mods if is_engineered else '',
                        'level': str(item.get('Level', '')),
                        'quality': str(item.get('Quality', '')),
                        'last_updated': timestamp
                    }
                
                updated_carriers.add(callsign)
                logger.info(f"Updated stored modules for carrier {callsign}: {len(self.modules[callsign])} modules")
            
            if updated_carriers:
                self.save_modules()
                return True
            
            return False
        
        except Exception:
            logger.warning('!! Error updating modules from StoredModules event: ' + traceback.format_exc(), exc_info=False)
            return False
    
    def get_modules_for_carrier(self, callsign: str) -> List[Dict]:
        """
        Get all stored modules for a specific carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            List of module dictionaries
        """
        if callsign not in self.modules:
            return []
        
        return list(self.modules[callsign].values())
    
    def get_module_count(self, callsign: str) -> int:
        """
        Get number of modules stored at a carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            Number of modules
        """
        if callsign not in self.modules:
            return 0
        
        return len(self.modules[callsign])
    
    def get_engineered_module_count(self, callsign: str) -> int:
        """
        Get number of engineered modules stored at a carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            Number of engineered modules
        """
        if callsign not in self.modules:
            return 0
        
        count = 0
        for module in self.modules[callsign].values():
            if module.get('engineered', '').lower() == 'true':
                count += 1
        
        return count
    
    def clear_modules_for_carrier(self, callsign: str) -> bool:
        """
        Clear all module data for a specific carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            True if cleared, False if carrier not found
        """
        if callsign in self.modules:
            del self.modules[callsign]
            self.save_modules()
            logger.info(f"Cleared stored modules for carrier {callsign}")
            return True
        return False
    
    def get_total_modules_value(self, callsign: str) -> int:
        """
        Calculate total buy price of all stored modules at a carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            Total value as integer
        """
        if callsign not in self.modules:
            return 0
        
        total = 0
        for module in self.modules[callsign].values():
            try:
                total += int(module.get('buy_price', 0))
            except (ValueError, TypeError):
                pass
        
        return total
