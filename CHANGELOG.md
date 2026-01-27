<!-- markdownlint-disable MD024 -->
# EDMC_GalaxyGPS Changelog

All notable changes to this project will be documented in this file.

## Version Reset Notice

With the rename from SpanshRouter to GalaxyGPS and the significant code evolution, version numbering has been reset to start fresh at 1.0.0. The version history from SpanshRouter (3.4.2 and earlier) is preserved below for reference, but all future versions will follow the new numbering scheme starting from 1.0.0.

---

## 1.5.0 (Major Release - Multi-Language Support)

### Major Features

- **🌍 Comprehensive Multi-Language Support**: Added full localization support for 20+ languages!
  - **European Languages**: Czech, Dutch, English, Finnish, French, German, Hungarian, Italian, Latvian, Polish, Russian, Slovenian, Spanish, Swedish, Ukrainian
  - **Asian Languages**: Chinese (Simplified), Japanese, Korean
  - **Portuguese Variants**: Portuguese (Brazil), Portuguese (Portugal)
  - **Serbian Variants**: Serbian (Latin), Serbian (Latin, Bosnia and Herzegovina)
  - All UI elements, buttons, labels, messages, and window titles are fully localized
  - Automatic language detection based on EDMC language setting
  - Dynamic UI refresh when language changes in EDMC settings
  - Complete translation files for all supported languages in `L10n/` directory

- **🚢 Enhanced Fleet Carrier Management**:
  - **Cargo Details Window**: New window displaying detailed cargo manifest for fleet carriers
    - Shows cargo item names (localized), quantities, and values
    - Accessible via "Cargo" button in "View All Carriers" window
    - Automatic column sizing and proper data formatting
  - **Ships Details Window**: New window displaying all ships stored on fleet carriers
    - Shows ship names and last updated timestamps
    - Accessible via "Ships" button in "View All Carriers" window
    - Proper handling of missing ships data
  - **Stored Modules Details Window**: New window displaying stored modules on fleet carriers
    - Tree view by category; localized module names, quantities, buy prices, engineered count, and total value
    - Accessible via "Modules" button in "View All Carriers" window
    - Data from `StoredModulesManager` and `fleet_carrier_modules.csv`

### Localization System

- **Translation Infrastructure**: Complete localization system using EDMC's `l10n` module
  - Translation template file (`en.template`) with all translatable strings
  - Individual translation files for each supported language
  - Proper handling of special characters and placeholders
  - Support for `{CR}` (carriage return) and `{ERROR}` placeholders in error messages

- **Dynamic UI Updates**: All UI elements automatically refresh when language changes
  - Buttons, labels, and placeholders update in real-time
  - Window titles and column headers update when windows are opened
  - Message dialogs use current language setting
  - Route view windows refresh with new language on next waypoint change

### UI/UX Improvements

- **Improved Window Management**: Enhanced window positioning and state management
  - Window positions are saved and restored between sessions
  - Better handling of window resizing and positioning
  - Improved visual consistency across all windows

- **Better Data Presentation**: Enhanced formatting and display of carrier information
  - Improved handling of missing data indicators
  - Better visual alignment in detail windows
  - Enhanced readability of cargo, ships, and modules information

### Technical Improvements

- **Code Organization**: Better separation of concerns with new manager classes
  - `CargoDetailsManager`: Handles cargo data storage and retrieval
  - `StoredShipsManager`: Handles ships data storage and retrieval
  - `StoredModulesManager`: Handles stored modules data for the Modules Details window
  - Improved error handling and data validation

- **Translation File Management**: Organized translation files in `L10n/` directory
  - Template file for reference (`en.template`)
  - Active English translations (`en.strings`)
  - Individual language files following EDMC naming conventions
  - Proper file structure for easy maintenance and updates

### Documentation

- **Documentation Reorganization**: Moved reference docs into `Documentation/`
  - `API_DOCUMENTATION.md`, `API_QUICK_REFERENCE.md`, `API_SUMMARY.md`, `INDEX_REFERENCE.md`, `TRANSLATION_VERIFICATION.md`, `CACHE_MODULES_README.md` now live in `Documentation/`
  - Example and doc references updated to `Documentation/...`
- **README and User Docs**: README reorganized (features/benefits first, installation and technical content later); expanded to describe Modules Details, cargo/ships windows, multi-language support, and the four CSV cache files; cache docs use generic paths (e.g. `%LOCALAPPDATA%` / `~/.local/share/...`) instead of user-specific paths

### Requirements

- **EDMC Language Support**: Plugin automatically uses EDMC's language setting
- **Translation Files**: All translation files included in release (no additional downloads needed)

---

## 1.0.0 (GalaxyGPS Initial Release)

### Program Name Change

- **Rebranded from SpanshRouter to GalaxyGPS**: The plugin has been renamed to better reflect its expanded functionality and evolved codebase
- **Version Reset**: Version numbering reset to 1.0.0 to mark the first official release under the GalaxyGPS name
- **Directory Structure**: Renamed `SpanshRouter/` directory to `GalaxyGPS/` and main file from `SpanshRouter.py` to `GalaxyGPS.py`
- **Class and Variable Renaming**: Updated all class names from `SpanshRouter` to `GalaxyGPS` and variable names from `spansh_router` to `galaxy_gps` for consistency
- **Environment Variable**: Updated `EDMC_SPANSH_ROUTER_XCLIP` to `EDMC_GALAXYGPS_XCLIP` for Wayland clipboard support

---

## Previous Versions (SpanshRouter History)

## 3.4.2

### Bug Fixes

- **Fleet Carrier Display Data Source**: Fixed System and Balance displays in main UI to use the same CSV data source as "View All" window
  - Now correctly displays data for the selected carrier from dropdown
  - Simplified data retrieval to match "View All" window behavior
  - Ensures consistency between main UI and detail windows

- **Icy Rings and Pristine Toggle Colors**: Fixed toggle button colors to match EDMC orange theme
  - Toggle circles now display orange when checked (active), gray when unchecked
  - Toggle labels ("Icy Rings" and "Pristine") now display orange when checked, gray when unchecked
  - Improved visual consistency with EDMC color scheme

- **Tritium Search Location**: Fixed Tritium search to use carrier's location instead of player's location
  - Clicking Tritium label now searches near the selected fleet carrier's system
  - More useful when carrier is in a different system than the player
  - Consistent behavior with "Find Trit" button

- **Tritium Search URL Format**: Fixed Inara.cz Tritium search URL to use correct format
  - Changed from `?search=Tritium&nearstarsystem=` to `?pi2=10269&ps1=`
  - Ensures proper search functionality on Inara.cz

### UI Improvements

- **Fleet Carrier Dropdown Styling**: Enhanced dropdown appearance to match EDMC dark theme
  - Background color matches EDMC's dark background
  - Text color changed to orange to match the rest of the program
  - Improved visual consistency with plugin theme

## 3.4.1

### Bug Fixes

- **Fuel Display Rounding**: Fixed "Fuel Used" and "Fuel Left" columns not being rounded to the nearest hundredth in the "View Route" window
  - Now properly rounds up to 2 decimal places, consistent with distance values
  - Applies to all CSV route types that include fuel columns

- **Fleet Carrier Display Errors**: Fixed main UI showing "Error" for System and Balance when data was unavailable
  - Now correctly displays "Unknown" (grayed out) instead of "Error" (red)
  - Improved error handling and null value checking
  - Matches behavior of "View All Carriers" window for consistency

- **Inara Fleet Carrier URL**: Fixed incorrect Inara.cz URL format for fleet carrier lookups
  - Changed from `https://inara.cz/elite/fleetcarrier/?search=` to `https://inara.cz/elite/station/?search=`
  - Fleet carriers are correctly accessed via the station search endpoint
  - Affects both the "Inara" button and carrier name/callsign links in "View All" window

### UI Improvements

- **Fleet Carrier Dropdown Styling**: Enhanced dropdown appearance to match EDMC dark theme
  - Background color matches EDMC's dark background (transparent-like)
  - Text color changed to orange to match the rest of the program
  - Improved visual consistency with plugin theme

## 3.4.0

### Route View Enhancements

- **Next Waypoint Highlighting**: Current next waypoint row is highlighted in light yellow in the "View Route" window
  - Makes it easy to locate your position in the route at a glance
  - Highlight automatically updates as you progress through the route
  - Window refreshes dynamically when next waypoint changes (if window is open)

- **EDSM Integration**: Added EDSM buttons to both "View Route" and "View All Carriers" windows
  - "EDSM" button appears before each system name
  - Opens system page on EDSM.net as an alternative to Inara.cz
  - Useful for systems that may not appear on Inara

- **Visual Indicator Improvements**:
  - **Neutron Star Indicator**: Changed from red to light blue dot to distinguish from other indicators
  - **Dot Indicator Alignment**: All dot indicators (Icy Rings, Pristine, Refuel, Neutron Star, etc.) are now center-aligned within their columns
  - Improved visual consistency and readability

- **Automatic Column Width Adjustment**: Columns now automatically resize to fit content
  - Prevents text cutoff for long system names or data values
  - Calculates maximum width needed based on both headers and all data rows
  - Window opens wide enough to display all columns with scrollbars when needed
  - Applies to both "View Route" and "View All Carriers" windows

- **Improved CSV Data Preservation**: Enhanced CSV import to store all data in memory
  - Preserves all columns from original CSV for display in "View Route" window
  - No longer relies on reading original CSV file - all data stored in memory
  - More efficient and robust - works even if original file is moved or deleted
  - Filters minimal data for route planner while retaining full data for display

### Fleet Carrier Management Improvements

- **Missing Data Handling**: Improved display of missing numerical values
  - Shows "Needs Update" for missing balance, cargo value, fuel, or cargo count
  - Distinguishes between legitimate zero values (displayed as "0") and missing data (displayed as "Needs Update")
  - Helps identify when carrier data needs to be refreshed via CAPI
  - Applies to both main UI display and "View All Carriers" window

- **Enhanced "View All Carriers" Window**:
  - Automatic column width adjustment for optimal display
  - "Needs Update" text properly accounted for in column sizing
  - All dot indicators center-aligned for better visual consistency

### Route Planning Improvements

- **Plot Route Button Enhancement**: Improved route planning interface
  - Button changes from "Plot Route" to "Calculate" when options are shown
  - "Cancel" button appears next to "Calculate" to return to default view
  - Button returns to "Plot Route" state after route calculation completes
  - Clearer workflow and user feedback

- **Distance Rounding**: All distance values rounded up to nearest hundredth
  - Prevents underestimating distances
  - Applies to "Distance to Arrival", "Distance Remaining", and "Fuel Used" displays
  - Consistent rounding throughout the plugin

### UI/UX Refinements

- **Visual Separators**: Added column separators (grid lines) to detail windows
  - Improves readability and alignment in "View Route" and "View All Carriers" windows
  - Helps align data with column headers

- **Improved Column Alignment**: Perfect alignment between headers and data
  - Refactored to use single grid layout for headers and data rows
  - Text columns left-aligned, numeric columns right-aligned, indicator columns center-aligned
  - Consistent spacing and padding throughout

- **UI Compaction**: Optimized horizontal spacing in main plugin window
  - Reduced gaps between elements while maintaining readability
  - Better organization of route action buttons
  - Improved layout efficiency

### Technical Improvements

- **In-Memory Data Storage**: Route data now stored entirely in memory
  - `route_full_data` array preserves all CSV columns
  - `route_fieldnames` preserves original CSV header names
  - Eliminates file I/O when viewing routes
  - Faster access and more reliable data preservation

- **Route Window Management**: Dynamic window refresh system
  - Route window automatically refreshes when next waypoint changes
  - Window reference tracking for efficient updates
  - Proper cleanup when windows are closed

- **Error Handling**: Enhanced error handling for missing data
  - Proper detection of missing vs. zero values
  - Graceful handling of incomplete carrier data
  - Better user feedback for data refresh needs

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
