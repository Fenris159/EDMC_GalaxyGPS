# EDMC_SpanshRouter
## Note on norohind's fork
This is fork where I try to maintain working version of SpanshRouter
plugin for public use with the latest version of EDMarketConnector. 
I have expanded it's functionality and corrected some issues for operating Fleet Carriers

This plugin's purpose is to automatically copy to your clipboard the next waypoint on a route you planned using [Spansh](https://www.spansh.co.uk/plotter).

## Install

- If you're on Linux, you'll need to make sure that **xclip** is installed before using the plugin (`sudo apt-get install xclip` on Debian based systems).
- Open your EDMC plugins folder - in EDMC settings, select "Plugins" tab, click the "Open" button.
- Create a folder inside the plugins folder and call it whatever you want, **SpanshRouter** for instance
- **Download this fork's code** by clicking the green "Code" button above and selecting "Download ZIP", then unzip it.
  - **Note:** Do not use the old releases from the original repository - they are outdated and incompatible with modern EDMC versions.
- Open the folder you created and put all the files and folders you extracted inside
- Restart EDMC

### Wayland Support

If you're using a Wayland desktop environment, you can't use xclip and have to configure the plugin using the `EDMC_SPANSH_ROUTER_XCLIP` environment variable to use Wayland specific `wl-copy` tool before launching EDMC. For example:

```bash
export EDMC_SPANSH_ROUTER_XCLIP="/usr/bin/wl-copy"
python EDMarketConnector.py
```

#### For Flatpak users

You need to grant additional permissions and set an environment variable. You can do this either via command line or using Flatseal:

**Option A - Using Flatseal (recommended for most users):**
1. Install Flatseal from your software center if not already installed
2. Open Flatseal and select "EDMarketConnector" from the list
3. Under "Socket" enable "Wayland windowing system" (`socket=wayland`)
4. Scroll down to "Filesystem" and enable "All system libraries, executables and static data" (`filesystem=host-os`)
5. Scroll to "Environment" and add the following variable:
   - `EDMC_SPANSH_ROUTER_XCLIP=/run/host/usr/bin/wl-copy`
6. Restart EDMC

**Option B - Using command line:**
```bash
flatpak override --user io.edcd.EDMarketConnector --socket=wayland --filesystem=host-os --env=EDMC_SPANSH_ROUTER_XCLIP=/run/host/usr/bin/wl-copy
```
Then restart EDMC normally through your application launcher.


This allows the plugin to use `wl-copy` instead of `xclip` for clipboard operations.


For more details see [this issue](https://github.com/norohind/EDMC_SpanshRouter/issues/6)

## Requirements

To use all features of this plugin, you'll need to configure the following:

### CAPI (Companion API) Configuration

**Required for Fleet Carrier Management features:**

1. **Enable CAPI in EDMarketConnector**:
   - Open EDMC Settings
   - Navigate to the "Frontier Auth" or "CAPI" tab
   - Follow the instructions to authenticate with Frontier's servers
   - Ensure that fleet carrier data fetching is enabled

2. **Why it's needed**: The plugin uses CAPI to automatically track your fleet carrier(s) location, fuel (Tritium), balance, cargo, and other carrier information. Without CAPI enabled, fleet carrier features will not work.

**Note**: CAPI data is typically updated when you dock at your fleet carrier or when certain journal events occur.

### EDSM API Connection

**Required for Icy Rings and Pristine status display:**

1. **Enable EDSM API in EDMarketConnector**:
   - Open EDMC Settings
   - Navigate to the "EDSM" tab
   - Enter your EDSM API key (you can get one from [EDSM.net](https://www.edsm.net/en/settings/api))
   - Ensure the connection is active

2. **Why it's needed**: The plugin queries the EDSM API to determine if a fleet carrier's current system has icy rings and if those rings are pristine quality. This information is cached in the CSV file to minimize API calls.

**Note**: If EDSM API is not configured, the Icy Rings and Pristine checkboxes will not update automatically.

### INARA API Connection (Optional but Recommended)

**Recommended for enhanced integration:**

1. **Enable INARA API in EDMarketConnector**:
   - Open EDMC Settings
   - Navigate to the "Inara" tab
   - Enter your INARA API key (you can get one from [INARA.cz](https://inara.cz/settings/api/))
   - Ensure the connection is active

2. **Why it's recommended**: While the plugin works without INARA API (using web links for Inara.cz), having it enabled provides better integration with EDMC's overall data flow.

**Note**: Most INARA features in this plugin work via web links, so the API is optional. However, enabling it provides better overall EDMC integration.

## How to use

### Basic Route Planning

You can either plot your route directly from EDMC by clicking the "Plot Route" button, or you can import a CSV file from [Spansh](https://www.spansh.co.uk/plotter)
You can also create your own CSV file, as long as it contains the columns "System Name" and "Jumps" (that last one is optional).
A valid CSV file could look like:

```csv
System Name,Jumps
Saggitarius A*,5
Beagle Point,324
```

You can also use a .txt file created with [EDTS](https://bitbucket.org/Esvandiary/edts/wiki/edts)

Once your route is plotted, and every time you reach a waypoint, the next one is automatically copied to your clipboard.

You just need to go to your Galaxy Map and paste it everytime you reach a waypoint.

If for some reason, your clipboard should be empty or containing other stuff that you copied yourself, just click on the **Next waypoint** button, and the waypoint will be copied again to your clipboard.

### Route Management

- **View Route**: Click the "View Route" button to open a window displaying your entire route as an easy-to-read list. System names are hyperlinked to Inara.cz for quick access. For fleet carrier routes, the window shows columns like "Restock Tritium", "Icy Ring", and "Pristine". For galaxy routes, "Refuel" and "Neutron Star" are shown. The window automatically sizes to fit all columns and includes scrollbars if needed.

- **Route Resumption**: If you accidentally clear your route and need to reload the CSV, the plugin will automatically detect your current location and resume from the appropriate waypoint:
  - **For regular routes**: Uses your current system location from Elite Dangerous
  - **For fleet carrier routes**: Uses the selected fleet carrier's current location
  - The plugin searches through the entire route to find where you are and automatically sets the next waypoint accordingly

- **Save Progress**: If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will start back where you stopped.

### Fleet Carrier Management

The plugin includes comprehensive fleet carrier management features at the top of the main window allowing you to remotely control your carrier of choice and plot it's route:

#### Fleet Carrier Selection
- **Dropdown Menu**: Select which fleet carrier you want to track from the dropdown menu. The dropdown shows carrier name, callsign, current system, and Tritium fuel level.

- **View All Button**: Click "View All" to open a detailed window showing all your fleet carriers with comprehensive information:
  - **Select**: Click the "Select" button on any carrier row to set it as the active carrier in the main dropdown
  - **Callsign & Name**: Hyperlinked to Inara.cz - click to view carrier details
  - **System**: Hyperlinked to Inara.cz - click to view system details
  - **Tritium**: Shows fuel tank amount and cargo amount (e.g., "1000 / 500")
  - **Balance**: Carrier credit balance
  - **Cargo**: Cargo count and total value
  - **State**: Current carrier state
  - **Theme**: Carrier theme
  - **Icy Rings**: Checkbox indicating if the carrier's system has icy rings
  - **Pristine**: Checkbox indicating if the carrier's system has pristine icy rings
  - **Docking Access**: Checkbox showing docking access settings
  - **Notorious Access**: Checkbox showing notorious access settings
  - **Last Updated**: Timestamp of last data update

- **Inara Button**: Click "Inara" to open the Inara.cz page for the currently selected fleet carrier.

#### Fleet Carrier Information Display

Below the dropdown, the plugin displays:

- **System**: Shows the current location of the selected fleet carrier

- **Icy Rings & Pristine**: Read-only checkboxes showing whether the carrier's current system has:
  - **Icy Rings**: Any icy rings present in the system
  - **Pristine**: Pristine quality icy rings (only checked if icy rings are also present)
  - *Note*: This data is automatically fetched from EDSM API and cached in the CSV to minimize API calls. It updates when the carrier changes location.

- **Tritium**: Displays fuel amount and cargo (e.g., "Tritium: 1000 (In Cargo: 500)"). Click this label to search Inara.cz for nearby Tritium sources using your current system location.

- **Balance**: Shows the carrier's credit balance (formatted with commas)

#### Fleet Carrier Route Warnings

- **Restock Tritium Warning**: When using a fleet carrier route, the plugin will display a "Warning: Restock Tritium" message if the selected carrier is currently in a system from your route that has "Restock Tritium" set to "Yes" on your route CSV.

- **Find Trit Button**: Appears next to the warning. Click it to search Inara.cz for nearby Tritium sources using the carrier's current system location.

## Fleet Carrier CAPI Integration

The plugin now automatically tracks your fleet carrier(s) using Frontier's CAPI (Companion API). When EDMarketConnector fetches fleet carrier data, the plugin will:

- **Automatically store** fleet carrier information including:
  - Current location (system name and address)
  - Fuel (Tritium) amount
  - Credit balance
  - Cargo count and total value
  - Carrier state, theme, and docking access settings
  - Last update timestamp
  - Source galaxy (Live/Beta/Legacy)

- **Save data to CSV**: All carrier information is stored in `fleet_carriers.csv` in your plugin directory for easy access and backup.

- **Access programmatically**: You can retrieve carrier information using the plugin's API:
  ```python
  # Get a specific carrier
  carrier = spansh_router.get_fleet_carrier("A1A-A1A")
  
  # Get all carriers
  all_carriers = spansh_router.get_all_fleet_carriers()
  
  # Find carriers in a specific system
  carriers_in_system = spansh_router.get_fleet_carriers_in_system("Sol")
  ```

The CSV file format includes columns: Callsign, Name, Current System, System Address, Fuel (Tritium), Balance, State, Theme, Docking Access, Notorious Access, Cargo Count, Cargo Total Value, Last Updated, and Source Galaxy.

**Note**: Fleet carrier data is automatically updated when EDMarketConnector fetches fresh data from Frontier's CAPI servers (typically when you dock at your carrier or when certain journal events occur).


## Plugin Priority

This plugin is configured as a **Package Plugin** (contains both `__init__.py` and `load.py`), which means it will be loaded before regular plugins and appear at the top of the plugin section in the EDMC main window.

## Updates

**Note:** Auto-updates are not maintained in this fork. To update, download the latest code from this repository and replace your plugin files manually.

## Known Issues

TBD
