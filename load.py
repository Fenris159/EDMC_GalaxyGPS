import json
import logging
import os
import queue
import sys
import threading
import tkinter as tk

# Plugin folder name; must match what plug.py uses for logger setup (PLUGINS.md)
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
plugin_name = os.path.basename(_plugin_dir)

# Ensure this plugin's directory is first on path so "GalaxyGPS" resolves to the
# inner package (GalaxyGPS/GalaxyGPS/ and GalaxyGPS/ui/), not the plugin folder
# when the folder is named "GalaxyGPS" (EDMC adds plugins dir first, so otherwise
# GalaxyGPS.ui would be looked up as plugin_folder/ui/ and fail with ModuleNotFoundError).
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

# Localization support - use file path as context (EDMC parses plugin name from path)
import l10n
import functools
plugin_tl = functools.partial(l10n.translations.tl, context=__file__)

# Use custom themed message dialogs
from GalaxyGPS.ui.message_dialog import showinfo, showwarning, showerror, askyesno

from companion import SERVER_LIVE, SERVER_LEGACY, SERVER_BETA  # type: ignore
from config import appname, config  # type: ignore
from theme import theme  # type: ignore

logger = logging.getLogger(f'{appname}.{plugin_name}')

# Version for Plugin Browser / auto-updater (PLUGINS.md); single source: version.json
# EDMC Plugin Registry requires __version__ as a string in Semantic Versioning format (Major.Minor.Patch).
try:
    _version_path = os.path.join(_plugin_dir, 'version.json')
    with open(_version_path, 'r', encoding='utf-8') as _f:
        _v = _f.read().strip()
    try:
        __version__ = json.loads(_v)
    except (json.JSONDecodeError, TypeError):
        __version__ = _v.strip('"\'') if _v else '0.0.0'
except Exception:
    __version__ = '0.0.0'
__version__ = str(__version__) if __version__ else '0.0.0'

if not logger.hasHandlers():
    logger.setLevel(logging.INFO)
    _ch = logging.StreamHandler()
    _fmt = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d:%(funcName)s: %(message)s'
    )
    _fmt.default_time_format = '%Y-%m-%d %H:%M:%S'
    _fmt.default_msec_format = '%s.%03d'
    _ch.setFormatter(_fmt)
    logger.addHandler(_ch)

# Import GalaxyGPS class - this must work regardless of plugin folder name
try:
    from GalaxyGPS import GalaxyGPS
except ImportError:
    # If import fails, try to add the plugin directory to sys.path
    if _plugin_dir not in sys.path:
        sys.path.insert(0, _plugin_dir)
    from GalaxyGPS import GalaxyGPS

galaxy_gps = None
_update_check_queue = queue.Queue()

# Export plugin_tl for use in other modules
__all__ = ['plugin_tl', 'plugin_name', 'plugin_start3', 'plugin_stop', 'plugin_app', 'prefs_changed', 
           'journal_entry', 'dashboard_entry', 'cmdr_data', 'capi_fleetcarrier']


def _run_update_check():
    """Worker: run check_for_update off main thread, then put result in queue."""
    global galaxy_gps
    if galaxy_gps:
        try:
            galaxy_gps.check_for_update()
        except Exception:
            pass
    _update_check_queue.put(True)


def _poll_update_check(parent):
    """Main-thread polling: when check done, call ask_for_update if applicable."""
    global galaxy_gps
    if getattr(config, 'shutting_down', False):
        return
    try:
        _update_check_queue.get_nowait()
        if galaxy_gps and galaxy_gps.update_available:
            ask_for_update()
    except queue.Empty:
        parent.after(200, lambda: _poll_update_check(parent))


def plugin_start3(plugin_dir):
    return plugin_start(plugin_dir)


def plugin_start(plugin_dir):
    global galaxy_gps
    galaxy_gps = GalaxyGPS(plugin_dir)
    
    # Register instance with public API for other plugins
    try:
        from GalaxyGPS import api
        api.register_instance(galaxy_gps)
    except Exception as e:
        logger.warning(f"Failed to register API instance: {e}")
    
    return 'GalaxyGPS'


def plugin_stop():
    global galaxy_gps
    if not galaxy_gps:
        return
    galaxy_gps.save_route()
    if galaxy_gps.update_available:
        logger.info("Installing GalaxyGPS update, please wait...")
        def _run_install():
            try:
                galaxy_gps.install_update()
                logger.info("GalaxyGPS update installed successfully")
            except Exception as e:
                logger.error(f"Failed to install update: {e}")
        t = threading.Thread(target=_run_install)
        t.start()
        t.join()  # Wait for update to complete (EDMC compliant - recommended in PLUGINS.md)


def journal_entry(cmdr, is_beta, system, station, entry, state):
    global galaxy_gps
    if not galaxy_gps:
        return
    if (entry['event'] in ['FSDJump', 'Location', 'SupercruiseEntry', 'SupercruiseExit']
            and entry["StarSystem"].lower() == galaxy_gps.next_stop.lower()):
        galaxy_gps.update_route()
        galaxy_gps.set_source_ac(entry["StarSystem"])
    elif entry['event'] == 'FSSDiscoveryScan' and entry['SystemName'] == galaxy_gps.next_stop:
        galaxy_gps.update_route()
    
    # Handle StoredShips and StoredModules events for cache managers
    event_name = entry.get('event', '')
    
    if event_name == 'StoredShips' and galaxy_gps.ships_manager and galaxy_gps.fleet_carrier_manager:
        # Get list of known carrier callsigns
        known_carriers = list(galaxy_gps.fleet_carrier_manager.carriers.keys())
        galaxy_gps.ships_manager.update_from_journal_event(entry, known_carriers)
    
    elif event_name == 'StoredModules' and galaxy_gps.modules_manager and galaxy_gps.fleet_carrier_manager:
        # Get list of known carrier callsigns
        known_carriers = list(galaxy_gps.fleet_carrier_manager.carriers.keys())
        galaxy_gps.modules_manager.update_from_journal_event(entry, known_carriers)
    
    # Update fleet carrier data from journal events (fallback to CAPI)
    if galaxy_gps.fleet_carrier_manager:
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
            updated = galaxy_gps.fleet_carrier_manager.update_carrier_from_journal(
                event_name, entry, state, source_galaxy
            )
            # Update GUI if carrier was updated
            if updated:
                if hasattr(galaxy_gps, 'update_fleet_carrier_dropdown'):
                    galaxy_gps.update_fleet_carrier_dropdown()
                if hasattr(galaxy_gps, 'update_fleet_carrier_system_display'):
                    galaxy_gps.update_fleet_carrier_system_display()
                if hasattr(galaxy_gps, 'update_fleet_carrier_rings_status'):
                    galaxy_gps.update_fleet_carrier_rings_status()
                if hasattr(galaxy_gps, 'update_fleet_carrier_tritium_display'):
                    galaxy_gps.update_fleet_carrier_tritium_display()
                if hasattr(galaxy_gps, 'update_fleet_carrier_balance_display'):
                    galaxy_gps.update_fleet_carrier_balance_display()
                if hasattr(galaxy_gps, 'check_fleet_carrier_restock_warning'):
                    galaxy_gps.check_fleet_carrier_restock_warning()
        
        elif event_name == 'Cargo' and is_at_carrier:
            # Only update cargo if we're at a fleet carrier station
            updated = galaxy_gps.fleet_carrier_manager.update_carrier_from_journal(
                event_name, entry, state, source_galaxy
            )
            
            # Also update detailed cargo cache (fallback when CAPI not available)
            if galaxy_gps.cargo_manager:
                callsign = galaxy_gps.fleet_carrier_manager.find_carrier_for_journal_event(entry, state)
                if callsign:
                    inventory = entry.get('Inventory', [])
                    if isinstance(inventory, list):
                        # Pass journal timestamp for proper comparison
                        event_timestamp = entry.get('timestamp', '')
                        galaxy_gps.cargo_manager.update_cargo_from_journal(callsign, inventory, source_galaxy, event_timestamp)
            
            # Update GUI if carrier was updated
            if updated:
                if hasattr(galaxy_gps, 'update_fleet_carrier_dropdown'):
                    galaxy_gps.update_fleet_carrier_dropdown()
                if hasattr(galaxy_gps, 'update_fleet_carrier_system_display'):
                    galaxy_gps.update_fleet_carrier_system_display()
                if hasattr(galaxy_gps, 'update_fleet_carrier_rings_status'):
                    galaxy_gps.update_fleet_carrier_rings_status()
                if hasattr(galaxy_gps, 'update_fleet_carrier_tritium_display'):
                    galaxy_gps.update_fleet_carrier_tritium_display()
                if hasattr(galaxy_gps, 'update_fleet_carrier_balance_display'):
                    galaxy_gps.update_fleet_carrier_balance_display()
        
        elif event_name == 'Location' and is_at_carrier and entry.get('Docked'):
            # Location event when docked at carrier - update location if carrier moved
            # Only update if we have a new system (carrier may have jumped)
            new_system = entry.get('StarSystem', '')
            if new_system:
                # Find carrier by station name pattern
                callsign = galaxy_gps.fleet_carrier_manager.find_carrier_for_journal_event(entry, state)
                if callsign:
                    carrier = galaxy_gps.fleet_carrier_manager.get_carrier(callsign)
                    if carrier and carrier.get('current_system', '').lower() != new_system.lower():
                        # Carrier location changed - update it
                        location_event_data = {
                            'StationName': entry.get('StationName', station_name),
                            'StarSystem': new_system,
                            'SystemAddress': str(entry.get('SystemAddress', ''))
                        }
                        updated = galaxy_gps.fleet_carrier_manager.update_carrier_from_journal(
                            'CarrierJump', location_event_data, state, source_galaxy
                        )
                        
                        # Update GUI if carrier location was updated
                        if updated:
                            if hasattr(galaxy_gps, 'update_fleet_carrier_dropdown'):
                                galaxy_gps.update_fleet_carrier_dropdown()
                            if hasattr(galaxy_gps, 'update_fleet_carrier_system_display'):
                                galaxy_gps.update_fleet_carrier_system_display()
                            if hasattr(galaxy_gps, 'update_fleet_carrier_rings_status'):
                                galaxy_gps.update_fleet_carrier_rings_status()
                            if hasattr(galaxy_gps, 'update_fleet_carrier_tritium_display'):
                                galaxy_gps.update_fleet_carrier_tritium_display()
                            if hasattr(galaxy_gps, 'update_fleet_carrier_balance_display'):
                                galaxy_gps.update_fleet_carrier_balance_display()
                            if hasattr(galaxy_gps, 'check_fleet_carrier_restock_warning'):
                                galaxy_gps.check_fleet_carrier_restock_warning()


def ask_for_update():
    global galaxy_gps
    if galaxy_gps.update_available:
        # LANG: Update notification dialog
        update_txt = plugin_tl("New GalaxyGPS update available!") + "\n"
        # LANG: Update installation instructions
        update_txt += plugin_tl("If you choose to install it, you will have to restart EDMC for it to take effect.") + "\n\n"
        update_txt += galaxy_gps.spansh_updater.changelogs
        # LANG: Prompt to install update
        update_txt += "\n\n" + plugin_tl("Install?")
        # Get parent window from galaxy_gps
        parent_window = galaxy_gps.parent if hasattr(galaxy_gps, 'parent') and galaxy_gps.parent else None
        install_update = askyesno(parent_window, "GalaxyGPS", update_txt) if parent_window else False

        if install_update:
            # Show status window and run download + install in background; close EDMC when done
            root = parent_window.winfo_toplevel() if parent_window else None
            if not root:
                galaxy_gps.update_available = False
                return
            install_queue = queue.Queue()
            wait_win = tk.Toplevel(root)
            wait_win.title("GalaxyGPS")
            wait_win.transient(root)
            wait_win.resizable(False, False)
            # Apply EDMC theme to match other plugin dialogs
            try:
                _temp = tk.Label(wait_win)
                theme.update(_temp)
                _bg, _fg = _temp.cget('bg'), _temp.cget('foreground')
                _temp.destroy()
            except Exception:
                _bg, _fg = '#1e1e1e', 'orange'
            wait_win.configure(bg=_bg)
            # LANG: Status text while update is downloading and installing
            msg = plugin_tl("Downloading and installing update, please wait…")
            lbl = tk.Label(wait_win, text=msg, padx=24, pady=16, bg=_bg, fg=_fg)
            lbl.pack()
            theme.update(lbl)
            wait_win.update_idletasks()
            wait_win.geometry(f"+{root.winfo_rootx() + max(0, (root.winfo_width() - wait_win.winfo_reqwidth()) // 2)}"
                              f"+{root.winfo_rooty() + max(0, (root.winfo_height() - wait_win.winfo_reqheight()) // 2)}")

            def _run_install():
                try:
                    galaxy_gps.spansh_updater.install()
                    install_queue.put(True)
                except Exception as e:
                    logger.exception("GalaxyGPS update install failed")
                    install_queue.put(False)

            threading.Thread(target=_run_install, daemon=True).start()

            def _poll_install():
                try:
                    done = install_queue.get_nowait()
                    try:
                        wait_win.destroy()
                    except tk.TclError:
                        pass
                    galaxy_gps.update_available = False
                    if done:
                        # LANG: Shown after update install, before EDMC is closed
                        showinfo(parent_window, "GalaxyGPS", plugin_tl("Update installed. EDMC will now close."))
                        root.quit()
                    else:
                        # LANG: Shown when update download/install failed
                        showerror(parent_window, plugin_tl("GalaxyGPS Update"), plugin_tl("Update failed. Check the EDMC log for details."))
                except queue.Empty:
                    root.after(300, _poll_install)

            root.after(300, _poll_install)
        else:
            galaxy_gps.update_available = False


def plugin_app(parent):
    global galaxy_gps
    import traceback

    if not galaxy_gps:
        return None
    try:
        frame = galaxy_gps.init_gui(parent)
        if not frame:
            logger.error("init_gui returned None - plugin will not display")
            return None
        
        galaxy_gps.open_last_route()
        # Update fleet carrier status display if carrier data exists
        if hasattr(galaxy_gps, 'update_fleet_carrier_dropdown'):
            galaxy_gps.update_fleet_carrier_dropdown()
        if hasattr(galaxy_gps, 'update_fleet_carrier_system_display'):
            galaxy_gps.update_fleet_carrier_system_display()
        if hasattr(galaxy_gps, 'update_fleet_carrier_rings_status'):
            galaxy_gps.update_fleet_carrier_rings_status()
        if hasattr(galaxy_gps, 'update_fleet_carrier_tritium_display'):
            galaxy_gps.update_fleet_carrier_tritium_display()
        if hasattr(galaxy_gps, 'update_fleet_carrier_balance_display'):
            galaxy_gps.update_fleet_carrier_balance_display()
        # Run update check off main thread; poll queue and show dialog when done
        root = parent.winfo_toplevel()
        threading.Thread(target=_run_update_check, daemon=True).start()
        root.after(200, lambda: _poll_update_check(root))
        return frame
    except Exception as e:
        logger.error(f"Error in plugin_app: {traceback.format_exc()}")
        # Try to get parent window, but if not available, use None
        parent_window = galaxy_gps.parent if hasattr(galaxy_gps, 'parent') and galaxy_gps.parent else None
        # LANG: Error dialog title
        # LANG: Error message when plugin fails to initialize
        showerror(parent_window, plugin_tl("GalaxyGPS Error"), 
                  plugin_tl("Failed to initialize plugin:{CR}{ERROR}{CR}{CR}Check EDMC log for details.").format(ERROR=str(e), CR="\n"))
        return None


def prefs_changed(cmdr, is_beta):
    """
    Called when EDMC settings/preferences are changed.
    Updates combobox theme and refreshes localized strings when language changes.
    """
    global galaxy_gps
    if galaxy_gps:
        # Update theme
        if hasattr(galaxy_gps, '_update_combobox_theme'):
            try:
                galaxy_gps._update_combobox_theme()
            except Exception as e:
                logger.debug(f"Error updating combobox theme in prefs_changed: {e}")
        
        # Refresh localized UI strings
        if hasattr(galaxy_gps, '_refresh_localized_ui'):
            try:
                galaxy_gps._refresh_localized_ui()
            except Exception as e:
                logger.debug(f"Error refreshing localized UI in prefs_changed: {e}")


def capi_fleetcarrier(data):
    """
    Called when EDMarketConnector fetches fleet carrier data from CAPI.
    
    Args:
        data: CAPIData object containing fleet carrier information
    """
    global galaxy_gps
    if galaxy_gps and galaxy_gps.fleet_carrier_manager:
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
        galaxy_gps.fleet_carrier_manager.update_carrier_from_capi(data, source_galaxy)
        
        # Extract callsign and cargo data for detailed caching
        carrier_data = data
        name_info = carrier_data.get('name', {})
        if isinstance(name_info, dict):
            callsign = name_info.get('callsign', '')
            if callsign and galaxy_gps.cargo_manager:
                # Update cargo details from CAPI (priority source)
                cargo_array = carrier_data.get('cargo', [])
                if isinstance(cargo_array, list):
                    galaxy_gps.cargo_manager.update_cargo_from_capi(callsign, cargo_array, source_galaxy)
        
        # Update the status display in the GUI
        if hasattr(galaxy_gps, 'update_fleet_carrier_dropdown'):
            galaxy_gps.update_fleet_carrier_dropdown()
        
        # Update fleet carrier system display
        if hasattr(galaxy_gps, 'update_fleet_carrier_system_display'):
            galaxy_gps.update_fleet_carrier_system_display()
        
        # Update fleet carrier rings status (Icy Rings and Pristine)
        if hasattr(galaxy_gps, 'update_fleet_carrier_rings_status'):
            galaxy_gps.update_fleet_carrier_rings_status()
        
        # Update fleet carrier Tritium display
        if hasattr(galaxy_gps, 'update_fleet_carrier_tritium_display'):
            galaxy_gps.update_fleet_carrier_tritium_display()
        
        # Update fleet carrier balance display
        if hasattr(galaxy_gps, 'update_fleet_carrier_balance_display'):
            galaxy_gps.update_fleet_carrier_balance_display()
        
        # Update fleet carrier restock warning
        if hasattr(galaxy_gps, 'check_fleet_carrier_restock_warning'):
            galaxy_gps.check_fleet_carrier_restock_warning()
