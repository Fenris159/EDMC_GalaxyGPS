import csv
import logging
import os
import traceback
from datetime import datetime
from typing import Dict, List, Optional

from config import appname  # type: ignore

# We need a name of plugin dir, not CargoDetailsManager.py dir
plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
logger = logging.getLogger(f'{appname}.{plugin_name}')


class CargoDetailsManager:
    """
    Manages detailed cargo information for fleet carriers from CAPI and journal events.
    Stores complete cargo array with commodity details in CSV format.
    """
    
    # CSV column headers
    CSV_HEADERS = [
        'Callsign',
        'Commodity',
        'Localized Name',
        'Quantity',
        'Value Per Unit',
        'Total Value',
        'Last Updated',
        'Source Galaxy'
    ]
    
    def __init__(self, plugin_dir: str):
        """
        Initialize the CargoDetailsManager.
        
        Args:
            plugin_dir: Directory where the plugin is installed
        """
        self.plugin_dir = plugin_dir
        self.cargo_file = os.path.join(plugin_dir, 'fleet_carrier_cargo.csv')
        # Keyed by callsign, value is dict of commodity name -> cargo item
        self.cargo: Dict[str, Dict[str, Dict]] = {}
        
        # Load existing cargo data
        self.load_cargo()
    
    def load_cargo(self) -> None:
        """
        Load cargo details from CSV file.
        """
        if not os.path.exists(self.cargo_file):
            logger.debug("No existing fleet carrier cargo file found")
            return
        
        try:
            with open(self.cargo_file, 'r', encoding='utf-8-sig', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    callsign = row.get('Callsign', '').strip()
                    commodity = row.get('Commodity', '').strip().lower()
                    
                    if callsign and commodity:
                        if callsign not in self.cargo:
                            self.cargo[callsign] = {}
                        
                        self.cargo[callsign][commodity] = {
                            'callsign': callsign,
                            'commodity': commodity,
                            'localized_name': row.get('Localized Name', ''),
                            'quantity': row.get('Quantity', '0'),
                            'value_per_unit': row.get('Value Per Unit', '0'),
                            'total_value': row.get('Total Value', '0'),
                            'last_updated': row.get('Last Updated', ''),
                            'source_galaxy': row.get('Source Galaxy', '')
                        }
            
            total_entries = sum(len(items) for items in self.cargo.values())
            logger.info(f"Loaded cargo details for {len(self.cargo)} carrier(s), {total_entries} total commodities")
        
        except Exception:
            logger.warning('!! Error loading fleet carrier cargo: ' + traceback.format_exc(), exc_info=False)
    
    def save_cargo(self) -> None:
        """
        Save cargo details to CSV file.
        """
        try:
            with open(self.cargo_file, 'w', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                
                # Flatten nested dict structure for CSV output
                for callsign in sorted(self.cargo.keys()):
                    for commodity in sorted(self.cargo[callsign].keys()):
                        item = self.cargo[callsign][commodity]
                        writer.writerow({
                            'Callsign': item.get('callsign', ''),
                            'Commodity': item.get('commodity', ''),
                            'Localized Name': item.get('localized_name', ''),
                            'Quantity': item.get('quantity', '0'),
                            'Value Per Unit': item.get('value_per_unit', '0'),
                            'Total Value': item.get('total_value', '0'),
                            'Last Updated': item.get('last_updated', ''),
                            'Source Galaxy': item.get('source_galaxy', '')
                        })
            
            total_entries = sum(len(items) for items in self.cargo.values())
            logger.debug(f"Saved cargo details for {len(self.cargo)} carrier(s), {total_entries} total commodities")
        
        except Exception:
            logger.warning('!! Error saving fleet carrier cargo: ' + traceback.format_exc(), exc_info=False)
    
    def update_cargo_from_capi(self, callsign: str, cargo_array: List[Dict], source_galaxy: str, event_timestamp: Optional[str] = None) -> None:
        """
        Update cargo details from CAPI response. REPLACES all cargo for this carrier.
        
        Uses timestamp comparison to only update if CAPI data is newer than existing Journal data.
        
        Args:
            callsign: Fleet carrier callsign
            cargo_array: List of cargo items from CAPI
            source_galaxy: Source galaxy (SERVER_LIVE, SERVER_BETA, SERVER_LEGACY)
            event_timestamp: Journal timestamp from the triggering event (ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ)
        """
        if not callsign:
            logger.warning("Cannot update cargo: missing callsign")
            return
        
        try:
            # Get current timestamp - use event timestamp if provided, otherwise use current time
            if event_timestamp:
                # Journal format: "2021-05-21T10:39:43Z"
                timestamp = event_timestamp
            else:
                # CAPI doesn't have timestamps, so use current time as best estimate
                timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Check if we have existing cargo data and compare timestamps
            if callsign in self.cargo and self.cargo[callsign]:
                # Get timestamp from any existing cargo item (they all have the same timestamp)
                existing_item = next(iter(self.cargo[callsign].values()))
                existing_timestamp = existing_item.get('last_updated', '')
                
                # Compare timestamps - only update if new data is newer
                try:
                    existing_dt = datetime.strptime(existing_timestamp, '%Y-%m-%dT%H:%M:%SZ')
                    new_dt = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
                    
                    if new_dt < existing_dt:
                        logger.info(f"Skipping CAPI cargo update for {callsign} - existing data is newer (existing: {existing_timestamp}, new: {timestamp})")
                        return
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not compare timestamps for {callsign}: {e}. Proceeding with update.")
            
            # Clear existing cargo for this carrier (replace, don't append)
            self.cargo[callsign] = {}
            
            if not isinstance(cargo_array, list):
                logger.warning(f"Cargo array is not a list for carrier {callsign}")
                self.save_cargo()
                return
            
            # Process each cargo item
            for item in cargo_array:
                if not isinstance(item, dict):
                    continue
                
                # Get commodity name (use 'commodity' or 'locName' field)
                commodity_raw = item.get('commodity', '') or item.get('locName', '')
                commodity = commodity_raw.lower().strip()
                
                if not commodity:
                    continue
                
                qty = item.get('qty', 0)
                value = item.get('value', 0)
                
                # Calculate total value
                try:
                    total_value = int(qty) * int(value)
                except (ValueError, TypeError):
                    total_value = 0
                
                # Store cargo item (replaces if already exists)
                self.cargo[callsign][commodity] = {
                    'callsign': callsign,
                    'commodity': commodity,
                    'localized_name': item.get('locName', commodity_raw),
                    'quantity': str(qty),
                    'value_per_unit': str(value),
                    'total_value': str(total_value),
                    'last_updated': timestamp,
                    'source_galaxy': source_galaxy
                }
            
            logger.info(f"Updated cargo details for carrier {callsign}: {len(self.cargo[callsign])} commodities (timestamp: {timestamp})")
            
            # Save to CSV
            self.save_cargo()
        
        except Exception:
            logger.warning(f'!! Error updating cargo from CAPI for {callsign}: ' + traceback.format_exc(), exc_info=False)
    
    def update_cargo_from_journal(self, callsign: str, inventory: List[Dict], source_galaxy: str, event_timestamp: str) -> None:
        """
        Update cargo details from journal Cargo event. REPLACES all cargo for this carrier.
        Uses timestamp comparison to only update if Journal data is newer than existing data.
        
        Args:
            callsign: Fleet carrier callsign
            inventory: List of cargo items from journal Cargo event
            source_galaxy: Source galaxy (Live/Beta/Legacy)
            event_timestamp: Journal event timestamp (ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ)
        """
        if not callsign:
            logger.warning("Cannot update cargo from journal: missing callsign")
            return
        
        try:
            # Check if we have existing cargo data and compare timestamps
            if callsign in self.cargo and self.cargo[callsign]:
                # Get timestamp from any existing cargo item (they all have the same timestamp)
                existing_item = next(iter(self.cargo[callsign].values()))
                existing_timestamp = existing_item.get('last_updated', '')
                
                # Compare timestamps - only update if new data is newer
                try:
                    existing_dt = datetime.strptime(existing_timestamp, '%Y-%m-%dT%H:%M:%SZ')
                    new_dt = datetime.strptime(event_timestamp, '%Y-%m-%dT%H:%M:%SZ')
                    
                    if new_dt < existing_dt:
                        logger.info(f"Skipping Journal cargo update for {callsign} - existing data is newer (existing: {existing_timestamp}, new: {event_timestamp})")
                        return
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not compare timestamps for {callsign}: {e}. Proceeding with update.")
            
            # Clear existing cargo for this carrier (replace, don't append)
            self.cargo[callsign] = {}
            
            if not isinstance(inventory, list):
                logger.warning(f"Inventory is not a list for carrier {callsign}")
                self.save_cargo()
                return
            
            # Process each cargo item
            for item in inventory:
                if not isinstance(item, dict):
                    continue
                
                # Get commodity name from journal format
                name = item.get('Name', '') or item.get('Name_Localised', '')
                commodity = name.lower().strip()
                
                if not commodity:
                    continue
                
                count = item.get('Count', 0)
                
                # Journal events don't always include value per unit
                # We'll store what we have and calculate total if available
                
                # Store cargo item (replaces if already exists)
                self.cargo[callsign][commodity] = {
                    'callsign': callsign,
                    'commodity': commodity,
                    'localized_name': item.get('Name_Localised', name),
                    'quantity': str(count),
                    'value_per_unit': '0',  # Journal doesn't provide this
                    'total_value': '0',  # Can't calculate without value per unit
                    'last_updated': event_timestamp,
                    'source_galaxy': source_galaxy
                }
            
            logger.info(f"Updated cargo details from journal for carrier {callsign}: {len(self.cargo[callsign])} commodities (timestamp: {event_timestamp})")
            
            # Save to CSV
            self.save_cargo()
        
        except Exception:
            logger.warning(f'!! Error updating cargo from journal for {callsign}: ' + traceback.format_exc(), exc_info=False)
    
    def get_cargo_for_carrier(self, callsign: str) -> List[Dict]:
        """
        Get all cargo items for a specific carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            List of cargo item dictionaries
        """
        if callsign not in self.cargo:
            return []
        
        return list(self.cargo[callsign].values())
    
    def get_commodity_quantity(self, callsign: str, commodity: str) -> int:
        """
        Get quantity of a specific commodity on a carrier.
        
        Args:
            callsign: Fleet carrier callsign
            commodity: Commodity name (case-insensitive)
            
        Returns:
            Quantity as integer, 0 if not found
        """
        commodity = commodity.lower().strip()
        
        if callsign not in self.cargo or commodity not in self.cargo[callsign]:
            return 0
        
        try:
            return int(self.cargo[callsign][commodity].get('quantity', 0))
        except (ValueError, TypeError):
            return 0
    
    def clear_cargo_for_carrier(self, callsign: str) -> bool:
        """
        Clear all cargo data for a specific carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            True if cleared, False if carrier not found
        """
        if callsign in self.cargo:
            del self.cargo[callsign]
            self.save_cargo()
            logger.info(f"Cleared cargo details for carrier {callsign}")
            return True
        return False
    
    def get_total_cargo_value(self, callsign: str) -> int:
        """
        Calculate total value of all cargo on a carrier.
        
        Args:
            callsign: Fleet carrier callsign
            
        Returns:
            Total value as integer
        """
        if callsign not in self.cargo:
            return 0
        
        total = 0
        for item in self.cargo[callsign].values():
            try:
                total += int(item.get('total_value', 0))
            except (ValueError, TypeError):
                pass
        
        return total
