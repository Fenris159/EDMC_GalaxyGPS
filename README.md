# EDMC_SpanshRouter
## Note on norohind's fork
This is fork where I updated and evolved SpanshRouter
plugin for public use with the latest version of EDMarketConnector. 

I have greatly expanded it's functionality and corrected some issues for operating Fleet Carriers

This plugin's purpose is to automatically copy to your clipboard the next waypoint on a route you planned using [Spansh](https://www.spansh.co.uk/plotter).

It also allows you to keep track of your place on the route and see additional information on the fly like road to riches values and system lookups. You can also keep track of your fleet carriers and their current status. 

## Install

### Prerequisites

- **Linux Users**: Install **xclip** before using the plugin:
  - Debian/Ubuntu: `sudo apt-get install xclip`
  - Fedora/RHEL: `sudo dnf install xclip`
  - Arch Linux: `sudo pacman -S xclip`
  - *Note*: If you're using Wayland, see the [Wayland Support](#wayland-support) section below for alternative setup.

### Installation Steps

1. **Open EDMC Plugins Folder**:
   - Launch EDMarketConnector
   - Go to **Settings** → **Plugins** tab
   - Click the **"Open"** button to open your plugins directory

2. **Download the Latest Release** (Recommended):
   - Visit the [Latest Release Page](https://github.com/Fenris159/EDMC_SpanshRouter/releases/latest)
   - Download the **Source code (zip)** file from the latest release
   - **Important**: Always use releases from this repository (`Fenris159/EDMC_SpanshRouter`) - older releases from other repositories are outdated and incompatible

3. **Extract and Install**:
   - Extract the downloaded ZIP file
   - Create a folder named **`EDMC_SpanshRouter`** (or any name you prefer) inside your EDMC plugins directory
   - Copy all extracted files and folders into this new folder
   - Ensure the folder structure looks like: `plugins/EDMC_SpanshRouter/SpanshRouter/`, `plugins/EDMC_SpanshRouter/load.py`, etc.

4. **Restart EDMC**:
   - Close and restart EDMarketConnector
   - The plugin should appear in the plugins section of EDMC

**Alternative Installation** (Not Recommended): If you prefer to use the latest development code instead of a stable release, you can download the repository as a ZIP from the main branch, but releases are recommended for stability.

### Wayland Support

If you're using a Wayland desktop environment, **xclip** won't work for clipboard operations. You need to configure the plugin to use **wl-copy** instead.

#### Standard Wayland Installation (Non-Flatpak)

1. **Install wl-clipboard** (contains `wl-copy`):
   - Debian/Ubuntu: `sudo apt-get install wl-clipboard`
   - Fedora/RHEL: `sudo dnf install wl-clipboard`
   - Arch Linux: `sudo pacman -S wl-clipboard`

2. **Set Environment Variable**:
   - Before launching EDMC, set the `EDMC_SPANSH_ROUTER_XCLIP` environment variable:
   ```bash
   export EDMC_SPANSH_ROUTER_XCLIP="/usr/bin/wl-copy"
   python EDMarketConnector.py
   ```
   - Or add it to your shell profile (`.bashrc`, `.zshrc`, etc.) to make it permanent:
   ```bash
   echo 'export EDMC_SPANSH_ROUTER_XCLIP="/usr/bin/wl-copy"' >> ~/.bashrc
   ```

#### Flatpak Users

If you're running EDMarketConnector as a Flatpak application, you need to grant additional permissions and configure the environment variable. You can do this using **Flatseal** (recommended) or the command line:

**Option A - Using Flatseal (Recommended):**

1. **Install Flatseal**:
   - Install from your software center or via: `flatpak install flathub com.github.tchx84.Flatseal`

2. **Configure EDMarketConnector**:
   - Open Flatseal
   - Select **"EDMarketConnector"** (or `io.edcd.EDMarketConnector`) from the application list
   - Under **"Socket"** section, enable:
     - **Wayland windowing system** (`socket=wayland`)
   - Scroll down to **"Filesystem"** section, enable:
     - **All system libraries, executables and static data** (`filesystem=host-os`)
   - Scroll to **"Environment"** section, click **"+"** to add a new variable:
     - **Name**: `EDMC_SPANSH_ROUTER_XCLIP`
     - **Value**: `/run/host/usr/bin/wl-copy`
   - Close Flatseal

3. **Restart EDMC**:
   - Close EDMarketConnector completely
   - Restart it through your application launcher

**Option B - Using Command Line:**

Run this command to configure all required permissions and environment variables:

```bash
flatpak override --user io.edcd.EDMarketConnector \
  --socket=wayland \
  --filesystem=host-os \
  --env=EDMC_SPANSH_ROUTER_XCLIP=/run/host/usr/bin/wl-copy
```

Then restart EDMarketConnector normally through your application launcher.

**Note**: The path `/run/host/usr/bin/wl-copy` is the Flatpak-accessible path to the host system's `wl-copy` binary. This allows the Flatpak application to use the Wayland clipboard tool from your host system.



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

The plugin supports multiple methods for route planning:

#### Importing Routes from Spansh

1. **Generate Route on Spansh**: 
   - Visit [Spansh Plotter](https://www.spansh.co.uk/plotter)
   - Configure your route parameters (starting system, destination, jump range, etc.)
   - Select your route type (Galaxy Route, Fleet Carrier Route, Road to Riches, Neutron Route, etc.)
   - Generate and download the route as a CSV file

2. **Import CSV into Plugin**:
   - Click the "Import File" button in the plugin
   - Navigate to and select your downloaded Spansh CSV file
   - The plugin will automatically detect the route type based on the CSV columns and process it accordingly

3. **Automatic Route Type Detection**: The plugin automatically identifies route types by analyzing the CSV column headers:
   - **Fleet Carrier Routes**: Detected by presence of "Restock Tritium", "Icy Ring", or "Pristine" columns
   - **Galaxy Routes**: Detected by presence of "Refuel" column along with "System Name"
   - **Road to Riches Routes**: Detected by presence of "Body Name", "Body Subtype", and "Is Terraformable" columns
   - **Neutron Routes**: Detected by presence of "Neutron Star" column with distance columns
   - **Generic Routes**: Any CSV with "System Name" and optionally "Jumps" columns

4. **Route Processing**: Once imported, the plugin:
   - Preserves all columns from the original CSV for display in the "View Route" window
   - Extracts essential route data (system names, jumps, distances) for route planning
   - Automatically rounds distance values up to the nearest hundredth for display
   - Detects your current position and sets the appropriate next waypoint

#### Creating Custom CSV Files

You can also create your own CSV file with minimal requirements:
- **Required Column**: "System Name" (or "System")
- **Optional Column**: "Jumps"
- **Example Format**:
  ```csv
  System Name,Jumps
  Saggitarius A*,5
  Beagle Point,324
  ```

#### EDTS File Support

The plugin also supports `.txt` files created with [EDTS](https://bitbucket.org/Esvandiary/edts/wiki/edts) for compatibility with other Elite Dangerous tools.

#### Plot Route Button

- **Initial State**: Click "Plot Route" to show route planning options
- **Route Options**: Enter starting system, destination system, jump range, and toggle supercharge (orange circular toggle)
- **Efficiency Slider**: Adjust route efficiency preference
- **Calculate Button**: After entering options, the button changes to "Calculate" - click it to compute the route via Spansh API
- **Cancel Button**: Appears next to "Calculate" - click it to return to the default view without calculating
- **After Calculation**: The button returns to "Plot Route" state after the route is calculated

Once your route is plotted, and every time you reach a waypoint, the next one is automatically copied to your clipboard.

You just need to go to your Galaxy Map and paste it everytime you reach a waypoint.

If for some reason, your clipboard should be empty or containing other stuff that you copied yourself, just click on the **Next waypoint** button, and the waypoint will be copied again to your clipboard.

### Route Management

- **View Route**: Click the "View Route" button to open a window displaying your entire route as an easy-to-read list. Features include:
  - **System Links**: System names are hyperlinked to Inara.cz for quick access. An "EDSM" button appears before each system name to open the system on EDSM.net as an alternative.
  - **Route Type Detection**: The window automatically detects route types and displays appropriate columns:
    - **Fleet Carrier routes**: Shows "Restock Tritium", "Icy Ring", and "Pristine" columns
    - **Galaxy routes**: Shows "Refuel" and "Neutron Star" columns
    - **Road to Riches routes**: Shows "Body Name", "Body Subtype", "Is Terraformable", "Estimated Scan Value", and "Estimated Mapping Value" columns
    - **Neutron routes**: Shows "Neutron Star" column
  - **Visual Indicators**: 
    - Checkbox columns (Refuel, Neutron Star, Icy Ring, Pristine, etc.) are displayed as colored dot indicators:
      - **Red dots**: Indicate "yes" for most checkbox fields
      - **Light blue dots**: Indicate "yes" for Neutron Star fields (to distinguish from other indicators)
      - **Gray dots**: Indicate "no" or empty values
    - All dot indicators are center-aligned within their columns
  - **Next Waypoint Highlighting**: The current next waypoint row is highlighted in light yellow, making it easy to locate your position in the route. The highlight automatically updates as you progress through the route.
  - **Automatic Column Sizing**: Columns automatically adjust their width to fit content, preventing text cutoff. The window opens wide enough to display all columns, with horizontal and vertical scrollbars if needed.
  - **Column Alignment**: 
    - Text columns are left-aligned
    - Numeric columns (distances, fuel, values) are right-aligned
    - Indicator columns (dots) are center-aligned
  - **Visual Separators**: Column separators (grid lines) help align data with headers for better readability.

- **Route Resumption**: If you accidentally clear your route and need to reload the CSV, the plugin will automatically detect your current location and resume from the appropriate waypoint:
  - **For regular routes**: Uses your current system location from Elite Dangerous
  - **For fleet carrier routes**: Uses the selected fleet carrier's current location
  - The plugin searches through the entire route to find where you are and automatically sets the next waypoint accordingly

- **Save Progress**: If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will start back where you stopped.

- **Route Window Auto-Refresh**: If the "View Route" window is open, it automatically refreshes when the next waypoint changes, updating the highlighted row to show your current position in the route.

### Fleet Carrier Management

The plugin includes comprehensive fleet carrier management features at the top of the main window allowing you to remotely control your carrier of choice and plot it's route:

#### Fleet Carrier Selection
- **Dropdown Menu**: Select which fleet carrier you want to track from the dropdown menu. The dropdown shows carrier name, callsign, current system, and Tritium fuel level.

- **View All Button**: Click "View All" to open a detailed window showing all your fleet carriers with comprehensive information:
  - **Select**: Click the "Select" button on any carrier row to set it as the active carrier in the main dropdown
  - **EDSM Button**: An "EDSM" button appears before each system name to open the system on EDSM.net
  - **Callsign & Name**: Hyperlinked to Inara.cz - click to view carrier details
  - **System**: Hyperlinked to Inara.cz - click to view system details
  - **Tritium**: Shows fuel tank amount and cargo amount (e.g., "1000 / 500"). Displays "Needs Update" if fuel data is missing.
  - **Balance**: Carrier credit balance (formatted with commas). Displays "Needs Update" if balance data is missing. Legitimate zero values display as "0".
  - **Cargo**: Cargo count and total value (e.g., "5 (10,000 cr)"). Displays "Needs Update" if cargo data is missing. Legitimate zero values display as "0 (0 cr)".
  - **State**: Current carrier state
  - **Theme**: Carrier theme
  - **Icy Rings**: Colored dot indicator (red for yes, gray for no) - center-aligned in column
  - **Pristine**: Colored dot indicator (red for yes, gray for no) - center-aligned in column
  - **Docking Access**: Colored dot indicator (red if access granted, gray if not) - center-aligned in column
  - **Notorious Access**: Colored dot indicator (red if access granted, gray if not) - center-aligned in column
  - **Last Updated**: Timestamp of last data update
  - **Automatic Column Sizing**: Columns automatically adjust their width to fit content, including "Needs Update" text, preventing text cutoff
  - **Visual Separators**: Column separators (grid lines) help align data with headers for better readability

- **Inara Button**: Click "Inara" to open the Inara.cz page for the currently selected fleet carrier.

#### Fleet Carrier Information Display

Below the dropdown, the plugin displays:

- **System**: Shows the current location of the selected fleet carrier

- **Icy Rings & Pristine**: Indicators showing whether the carrier's current system has:
  - **Icy Rings**: Any icy rings present in the system
  - **Pristine**: Pristine quality icy rings (only checked if icy rings are also present)
  - *Note*: This data is automatically fetched from EDSM API and cached in the CSV to minimize API calls. It updates when the carrier changes location.

- **Tritium**: Displays fuel amount and cargo (e.g., "Tritium: 1000 (In Cargo: 500)"). Click this label to search Inara.cz for nearby Tritium sources using your current system location. If fuel data is missing, displays "Tritium: Unknown" (grayed out and not clickable). Legitimate zero values display as "Tritium: 0".

- **Balance**: Shows the carrier's credit balance (formatted with commas). Displays "Balance: Unknown" (grayed out) if balance data is missing. Legitimate zero values display as "Balance: 0 cr".

#### Fleet Carrier Route Warnings

- **Restock Tritium Warning**: When using a fleet carrier route, the plugin will display a "Warning: Restock Tritium" message (centered and colored red) if the selected carrier is currently in a system from your route that has "Restock Tritium" set to "Yes" on your route CSV.

- **Find Trit Button**: Appears next to the warning. Click it to search Inara.cz for nearby Tritium sources using the carrier's current system location.

#### Missing Data Handling

- **"Needs Update" Display**: If numerical values (balance, cargo value, fuel, or cargo count) are missing from the fleet carrier data, the plugin displays "Needs Update" instead of showing "0" or empty values. This helps distinguish between:
  - **Legitimate zero values**: Displayed as "0" (e.g., a carrier with zero balance shows "Balance: 0 cr")
  - **Missing data**: Displayed as "Needs Update" (e.g., if balance hasn't been fetched yet)
- **Data Refresh**: Missing values will automatically update when CAPI data is refreshed (typically when you dock at your carrier or when certain journal events occur).

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

The plugin features an **automatic update system** that checks for new versions when EDMC starts.

### How Auto-Updates Work

1. **Automatic Check**: When EDMC starts, the plugin automatically checks the GitHub repository (`Fenris159/EDMC_SpanshRouter`) for new versions by comparing the local `version.json` with the remote version.

2. **Update Notification**: If a new version is available, a dialog will appear showing:
   - The new version number
   - The changelog from the GitHub release
   - A prompt asking if you want to install the update

3. **Installation**: If you choose to install:
   - The update will be downloaded when you close EDMC
   - The plugin files will be automatically updated
   - You'll need to restart EDMC for the update to take effect

4. **Manual Updates**: If you prefer to update manually, you can:
   - Download the latest release from the [GitHub repository](https://github.com/Fenris159/EDMC_SpanshRouter/releases)
   - Extract and replace the plugin files in your EDMC plugins folder
   - Restart EDMC

**Note**: The auto-update system requires an active internet connection to check for updates. Updates are only downloaded if you confirm the installation prompt.

## Known Issues

TBD
