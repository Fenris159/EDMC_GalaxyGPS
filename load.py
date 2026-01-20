import os
import sys
import tkinter.messagebox as confirmDialog

from companion import SERVER_LIVE, SERVER_LEGACY, SERVER_BETA  # type: ignore

# Import SpanshRouter class - this must work regardless of plugin folder name
try:
    from SpanshRouter.SpanshRouter import SpanshRouter
except ImportError as e:
    # If import fails, try to add the plugin directory to sys.path
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)
    from SpanshRouter.SpanshRouter import SpanshRouter

spansh_router = None


def plugin_start3(plugin_dir):
    return plugin_start(plugin_dir)


def plugin_start(plugin_dir):
    global spansh_router
    spansh_router = SpanshRouter(plugin_dir)
    spansh_router.check_for_update()
    return 'SpanshRouter'


def plugin_stop():
    global spansh_router
    spansh_router.save_route()

    if spansh_router.update_available:
        spansh_router.install_update()


def journal_entry(cmdr, is_beta, system, station, entry, state):
    global spansh_router
    if (entry['event'] in ['FSDJump', 'Location', 'SupercruiseEntry', 'SupercruiseExit']
            and entry["StarSystem"].lower() == spansh_router.next_stop.lower()):
        spansh_router.update_route()
        spansh_router.set_source_ac(entry["StarSystem"])
    elif entry['event'] == 'FSSDiscoveryScan' and entry['SystemName'] == spansh_router.next_stop:
        spansh_router.update_route()
    
    # Update fleet carrier data from journal events (fallback to CAPI)
    if spansh_router and spansh_router.fleet_carrier_manager:
        # Determine source galaxy from state or default to Live
        source_galaxy = 'Live'
        if hasattr(state, 'get'):
            # Could check state for galaxy info if available
            pass
        
        # Handle fleet carrier journal events
        event_name = entry.get('event', '')
        
        # Check if player is docked at a fleet carrier (for Location/Cargo events)
        station_type = state.get('StationType', '') if state else ''
        station_name = state.get('StationName', '') if state else entry.get('StationName', '')
        is_at_carrier = (station_type and 'fleetcarrier' in station_type.lower()) or (
            station_name and 'FC' in station_name.upper()
        )
        
        if event_name in ['CarrierJump', 'CarrierDepositFuel', 'CarrierStats']:
            # Always update for carrier-specific events
            updated = spansh_router.fleet_carrier_manager.update_carrier_from_journal(
                event_name, entry, state, source_galaxy
            )
            
                # Update GUI if carrier was updated
            if updated:
                if hasattr(spansh_router, 'update_fleet_carrier_dropdown'):
                    spansh_router.update_fleet_carrier_dropdown()
                if hasattr(spansh_router, 'update_fleet_carrier_system_display'):
                    spansh_router.update_fleet_carrier_system_display()
                if hasattr(spansh_router, 'update_fleet_carrier_rings_status'):
                    spansh_router.update_fleet_carrier_rings_status()
                if hasattr(spansh_router, 'update_fleet_carrier_tritium_display'):
                    spansh_router.update_fleet_carrier_tritium_display()
                if hasattr(spansh_router, 'update_fleet_carrier_balance_display'):
                    spansh_router.update_fleet_carrier_balance_display()
                if hasattr(spansh_router, 'check_fleet_carrier_restock_warning'):
                    spansh_router.check_fleet_carrier_restock_warning()
        
        elif event_name == 'Cargo' and is_at_carrier:
            # Only update cargo if we're at a fleet carrier station
            updated = spansh_router.fleet_carrier_manager.update_carrier_from_journal(
                event_name, entry, state, source_galaxy
            )
            
            # Update GUI if carrier was updated
            if updated:
                if hasattr(spansh_router, 'update_fleet_carrier_dropdown'):
                    spansh_router.update_fleet_carrier_dropdown()
                if hasattr(spansh_router, 'update_fleet_carrier_system_display'):
                    spansh_router.update_fleet_carrier_system_display()
                if hasattr(spansh_router, 'update_fleet_carrier_rings_status'):
                    spansh_router.update_fleet_carrier_rings_status()
                if hasattr(spansh_router, 'update_fleet_carrier_tritium_display'):
                    spansh_router.update_fleet_carrier_tritium_display()
                if hasattr(spansh_router, 'update_fleet_carrier_balance_display'):
                    spansh_router.update_fleet_carrier_balance_display()
        
        elif event_name == 'Location' and is_at_carrier and entry.get('Docked'):
            # Location event when docked at carrier - update location if carrier moved
            # Only update if we have a new system (carrier may have jumped)
            new_system = entry.get('StarSystem', '')
            if new_system:
                # Find carrier by station name pattern
                callsign = spansh_router.fleet_carrier_manager.find_carrier_for_journal_event(entry, state)
                if callsign:
                    carrier = spansh_router.fleet_carrier_manager.get_carrier(callsign)
                    if carrier and carrier.get('current_system', '').lower() != new_system.lower():
                        # Carrier location changed - update it
                        location_event_data = {
                            'StationName': entry.get('StationName', station_name),
                            'StarSystem': new_system,
                            'SystemAddress': str(entry.get('SystemAddress', ''))
                        }
                        updated = spansh_router.fleet_carrier_manager.update_carrier_from_journal(
                            'CarrierJump', location_event_data, state, source_galaxy
                        )
                        
                        # Update GUI if carrier location was updated
                        if updated:
                            if hasattr(spansh_router, 'update_fleet_carrier_dropdown'):
                                spansh_router.update_fleet_carrier_dropdown()
                            if hasattr(spansh_router, 'update_fleet_carrier_system_display'):
                                spansh_router.update_fleet_carrier_system_display()
                            if hasattr(spansh_router, 'update_fleet_carrier_rings_status'):
                                spansh_router.update_fleet_carrier_rings_status()
                            if hasattr(spansh_router, 'update_fleet_carrier_tritium_display'):
                                spansh_router.update_fleet_carrier_tritium_display()
                            if hasattr(spansh_router, 'update_fleet_carrier_balance_display'):
                                spansh_router.update_fleet_carrier_balance_display()
                            if hasattr(spansh_router, 'check_fleet_carrier_restock_warning'):
                                spansh_router.check_fleet_carrier_restock_warning()


def ask_for_update():
    global spansh_router
    if spansh_router.update_available:
        update_txt = "New Spansh Router update available!\n"
        update_txt += "If you choose to install it, you will have to restart EDMC for it to take effect.\n\n"
        update_txt += spansh_router.spansh_updater.changelogs
        update_txt += "\n\nInstall?"
        install_update = confirmDialog.askyesno("SpanshRouter", update_txt)

        if install_update:
            confirmDialog.showinfo("SpanshRouter", "The update will be installed as soon as you quit EDMC.")
        else:
            spansh_router.update_available = False


def plugin_app(parent):
    global spansh_router
    frame = spansh_router.init_gui(parent)
    spansh_router.open_last_route()
        # Update fleet carrier status display if carrier data exists
    if hasattr(spansh_router, 'update_fleet_carrier_dropdown'):
        spansh_router.update_fleet_carrier_dropdown()
    if hasattr(spansh_router, 'update_fleet_carrier_system_display'):
        spansh_router.update_fleet_carrier_system_display()
    if hasattr(spansh_router, 'update_fleet_carrier_rings_status'):
        spansh_router.update_fleet_carrier_rings_status()
    if hasattr(spansh_router, 'update_fleet_carrier_tritium_display'):
        spansh_router.update_fleet_carrier_tritium_display()
    if hasattr(spansh_router, 'update_fleet_carrier_balance_display'):
        spansh_router.update_fleet_carrier_balance_display()
    parent.master.after_idle(ask_for_update)
    return frame


def capi_fleetcarrier(data):
    """
    Called when EDMarketConnector fetches fleet carrier data from CAPI.
    
    Args:
        data: CAPIData object containing fleet carrier information
    """
    global spansh_router
    if spansh_router and spansh_router.fleet_carrier_manager:
        # Determine source galaxy
        source_galaxy = 'Unknown'
        if hasattr(data, 'source_host'):
            if data.source_host == SERVER_LIVE:
                source_galaxy = 'Live'
            elif data.source_host == SERVER_BETA:
                source_galaxy = 'Beta'
            elif data.source_host == SERVER_LEGACY:
                source_galaxy = 'Legacy'
        
        # Update carrier data
        spansh_router.fleet_carrier_manager.update_carrier_from_capi(data, source_galaxy)
        
        # Update the status display in the GUI
        if hasattr(spansh_router, 'update_fleet_carrier_dropdown'):
            spansh_router.update_fleet_carrier_dropdown()
        
        # Update fleet carrier system display
        if hasattr(spansh_router, 'update_fleet_carrier_system_display'):
            spansh_router.update_fleet_carrier_system_display()
        
        # Update fleet carrier rings status (Icy Rings and Pristine)
        if hasattr(spansh_router, 'update_fleet_carrier_rings_status'):
            spansh_router.update_fleet_carrier_rings_status()
        
        # Update fleet carrier Tritium display
        if hasattr(spansh_router, 'update_fleet_carrier_tritium_display'):
            spansh_router.update_fleet_carrier_tritium_display()
        
        # Update fleet carrier balance display
        if hasattr(spansh_router, 'update_fleet_carrier_balance_display'):
            spansh_router.update_fleet_carrier_balance_display()
        
        # Update fleet carrier restock warning
        if hasattr(spansh_router, 'check_fleet_carrier_restock_warning'):
            spansh_router.check_fleet_carrier_restock_warning()
