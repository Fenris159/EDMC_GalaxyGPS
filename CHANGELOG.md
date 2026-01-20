# EDMC_SpanshRouter Change Log

All notable changes to this project will be documented in this file.

## 3.3.0

### Major Features

- **Fleet Carrier CAPI Integration**: Comprehensive fleet carrier management using Frontier's Companion API
  - Automatic tracking of all fleet carriers via CAPI data
  - Stores carrier data in `fleet_carriers.csv` for persistence and backup
  - Tracks location, fuel (Tritium), balance, cargo, state, theme, docking access, and more
  - Supports multiple carriers and tracks source galaxy (Live/Beta/Legacy)
  - Real-time updates from CAPI and journal event fallback for location, fuel, and cargo changes

- **Fleet Carrier Management UI**: Complete fleet carrier management interface at the top of the plugin window
  - **Dropdown Menu**: Select and track specific fleet carriers with name, callsign, system, and Tritium displayed
  - **View All Window**: Comprehensive window showing all carriers with full details
    - Select button to set active carrier from the list
    - Hyperlinked carrier names/callsigns and system names to Inara.cz
    - Displays Tritium (fuel/cargo), Balance, Cargo, State, Theme, Icy Rings, Pristine, Docking Access, Notorious Access
    - Auto-sizing and scrollbars for optimal display
  - **Inara Button**: Quick access to Inara.cz page for selected carrier
  - **System Display**: Shows current location of selected fleet carrier
  - **Balance Display**: Shows carrier credit balance with comma formatting
  - **Icy Rings & Pristine Status**: Read-only checkboxes showing ring information for carrier's current system
    - Data fetched from EDSM API and cached in CSV to minimize API calls
    - Updates automatically when carrier location changes

- **Fleet Carrier Route Integration**: Enhanced route features for fleet carrier routes
  - **Tritium Display**: Shows fuel and cargo amounts (e.g., "Tritium: 1000 (In Cargo: 500)")
    - Clickable label to search Inara.cz for nearby Tritium using current system location
  - **Restock Tritium Warning**: Displays warning when carrier is in a route system requiring Tritium restock
  - **Find Trit Button**: Quick search for Tritium sources near carrier location via Inara.cz
  - Route resumption uses carrier location instead of player location for fleet carrier routes

### Route Management Enhancements

- **View Route Window**: New window displaying entire route as formatted list
  - System names hyperlinked to Inara.cz
  - Auto-detects route type (Fleet Carrier, Galaxy, Road to Riches, Neutron)
  - Displays appropriate columns based on route type
  - Yes/No fields shown as read-only checkboxes (Restock Tritium, Icy Ring, Pristine, Refuel, Neutron Star, Is Terraformable)
  - Auto-sizing to fit content with screen width constraints
  - Horizontal and vertical scrollbars when needed
  - Road to Riches routes: System name repetition handled for better readability

- **Intelligent Route Resumption**: Automatically resumes route from current location when reloading CSV
  - For regular routes: Uses player's current system location
  - For fleet carrier routes: Uses selected fleet carrier's current location
  - Searches entire route to find matching system and sets appropriate next waypoint
  - Properly adjusts jump counts when resuming mid-route

- **Fuel Used Display**: Shows "Fuel Used" value in waypoint details area when route CSV includes this column
  - Supports Fleet Carrier, Galaxy, and generic route formats

### UI/UX Improvements

- **Plugin Display Priority**: Configured as Package Plugin to appear at top of EDMC plugin section
- **Hyperlinked Elements**: Carrier names, system names, and other elements link to Inara.cz for quick access
- **Enhanced Window Management**: All popup windows (View Route, View All Carriers) feature proper auto-sizing and scrolling
- **Improved Data Presentation**: Better formatting for numbers, checkboxes for boolean values, and organized column layouts

### Technical Improvements

- **EDSM API Integration**: Queries EDSM API for system body/ring information
  - Determines Icy Rings and Pristine status for fleet carrier locations
  - Caches results in CSV to minimize API calls
  - Only queries when carrier location changes or data is missing

- **Journal Event Handling**: Enhanced journal event processing for fleet carrier updates
  - Handles `CarrierJump`, `CarrierDepositFuel`, `CarrierStats`, `Cargo`, and `Location` events
  - Fallback mechanism when CAPI data is unavailable
  - Real-time updates for fuel, cargo, and location changes

- **CSV Data Management**: Extended fleet carrier CSV to include Icy Rings and Pristine status
  - Preserves cached data when updating from CAPI
  - Invalidates cached ring data when carrier location changes

### Requirements

- **CAPI (Companion API)**: Required for fleet carrier features
- **EDSM API**: Required for Icy Rings and Pristine status display
- **INARA API**: Optional but recommended for enhanced integration

## 3.2.0

- **Python 3.13 Compatibility**: Updated codebase for full Python 3.13 compatibility
  - Removed deprecated `sys.platform == "linux2"` check (deprecated since Python 3.3)
  - Replaced all `__len__()` method calls with `len()` function for better performance
  - Replaced bare `except:` clauses with specific exception types for better error handling
  - Modernized exception logging using `traceback.format_exc()` instead of deprecated `sys.exc_info()` pattern
  - Replaced `io.open()` with standard `open()` function
  - Fixed bug in updater.py where `os.path.join()` was incorrectly used with binary content
- **CSV Import Improvements**:
  - Made CSV column name matching case-insensitive to prevent import issues
  - CSV files now work regardless of column name capitalization (e.g., "System Name", "system name", "SYSTEM NAME" all work)
- **Auto-advance Feature**: Automatically advances to next waypoint when importing CSV if already in the first waypoint system
  - No more manual button clicking needed when starting a route from your current location
  - Properly updates jump counts when auto-advancing
- **Fleet Carrier Improvements**:
  - Fixed fleet carrier restock notification to correctly detect "Restock Tritium" field regardless of CSV format
  - Now uses last element of route array instead of hardcoded index for better compatibility
- **Code Quality**:
  - Added `# type: ignore` comments for EDMC runtime imports to suppress IDE warnings
  - Centralized GUI layout management for easier maintenance and configuration
  - Refactored widget visibility logic into single state-based method
  - Reduced code duplication and improved maintainability

## 3.1.0

- BE ADVISED: This version only works for EDMC 4.0.0.0 and above. Do not install if you're not currently running the latest EDMC version.
- Fixed a bug with csv file containing system names in uppercase
- Fixed a bug where the suggestions list would linger on the main screen

## 3.0.4

- BE ADVISED: This version only works for EDMC 4.0.0.0 and above. Do not install if you're not currently running the latest EDMC version. This will be left as e pre-release for some time to let everyone update EDMC.
- Dropped support for previous EDMC versions
- Fixed bugs with the autocompleted fields in the "plot route" interface

## 3.0.3

- Fixed "no previously saved route" message even though a saved route was present
- Allow single click selection in the "Plot route" interface
- Fixed update issue when using Python 3

## 3.0.2

- Fixed an issue where the update popup would crash EDMC

## 3.0.1

- Fixed issues with Python 2

## 3.0.0

- Add compatibility with the Python 3 version of EDMC
- Fixed an issue with CSV files containing a BOM code (added by some programs such as Microsoft Excel)
- When browsing to import a file, set starting directory at user's home

## 2.2.1

- Changes from updates now appear in a popup so the user can choose wether they want to install it or not.

## 2.2.0

- Now supports any CSV having columns named "System Name" and "Jumps". The "Jumps" column is optional
- Supports text files given by EDTS (it is the only .txt file supported for now)
- The "Start System" in the potter is now automatically set to the one you are currently in
- Fixed a bug where the plugin could make EDMC crash by accessing TkInter state in a thread

## 2.1.4

- Autosaves your progress more often in case EDMC crashes
- Add a right click menu for copy/pasting in the system entries
- Better themes integration

## 2.1.3

- Bugfix: System suggestions actually show up when you type in either Source or Destination system inputs on Windows

## 2.1.2

- Fixed conflicts when other plugins used similar file names
- Fixed plugin sometimes just breaking when nasty errors occured and actually recover from them
- Remove trailing whitespaces when plotting a route to avoid issues with Spansh
- Show plotting errors in the GUI (like unknown system name or invalid range)
- Fixed an issue with the systems list where it wouldn't disappear
- Fixed an issue when plotting from the system you're currently in (it should now *finally* start at the next waypoint)
- Keep previous entries in the *Route plotting* GUI when closing it

## 2.1.1

- Fixed an issue with CSV files containing blank lines

## 2.1.0

- Automatically download and install updates
- Right clicking on a System input now pastes what's in your clipboard

## 2.0.1

- Add an error prompt when things go wrong while plotting a route
- Add requests timeout to prevent the plugin from hanging
- Better recovery from errors

## 2.0.0

- You can now plot your route directly from EDMC
- A few bugs were fixed

## 1.2.1

- Added update button which opens the releases page

## 1.2.0

- Added "Clear route" button
- Added an estimated "jumps left" count
- Better GUI layout
- Better "route save" handling
- Bug fixes

## 1.1.0

- Added "next/previous waypoint" buttons
- Added update notification
- Better route save handling
- Fixed first waypoint not copied when using new route
- Added workarounds for an issue where the first waypoint is not copied/updated

## 1.0.0

- Initial release

