# GalaxyGPS - Your Ultimate Space Navigation Companion! 🚀

Welcome to **GalaxyGPS**, the most comprehensive route planning and fleet carrier management plugin for Elite Dangerous! Think of it as your trusty GPS, but for navigating the vast reaches of the galaxy. Whether you're exploring uncharted territories, managing your fleet carrier operations, or planning the perfect Road to Riches expedition, GalaxyGPS has got you covered!

## What Makes GalaxyGPS Special? ✨

GalaxyGPS started as an evolution from SpanshRouter, but has grown into something entirely new and powerful. Built from the ground up with modern Python and EDMC compatibility, it's packed with features that make space navigation a breeze:

- **🌍 Multi-Language Support**: Fully localized in 20+ languages! Whether you speak English, German, Japanese, Chinese, or any of our other supported languages, GalaxyGPS speaks your language.
- **🚢 Fleet Carrier Management**: Complete remote control and tracking of your fleet carriers with real-time data from Frontier's CAPI, including detailed views of cargo, stored ships, and outfitting modules
- **🗺️ Smart Route Planning**: Import routes from Spansh, create custom routes, or plot directly from EDMC
- **📍 Intelligent Waypoint Tracking**: Automatic clipboard copying, route resumption, and progress saving
- **💎 Road to Riches Integration**: Track scan values and terraformable bodies for maximum profit
- **⛽ Tritium Management**: Never run out of fuel with smart warnings and Inara integration
- **🔍 Deep Integration**: Seamless connections with EDSM, Inara, and Spansh for all your navigation needs

## Current Version: 1.5.0

This major release brings comprehensive multi-language support, enhanced fleet carrier management features, and numerous quality-of-life improvements. See the [Changelog](CHANGELOG.md) for full details!

---

## Key Features 🎯

### 🗺️ Smart Route Planning & Navigation

#### Import Routes from Spansh or Create Your Own

- Import any route from [Spansh Plotter](https://www.spansh.co.uk/plotter) - the plugin automatically detects route types (Galaxy Routes, Fleet Carrier Routes, Road to Riches, Neutron Routes)
- Create your own custom CSV files with just system names
- Plot routes directly from EDMC with the "Plot Route" button
- Automatic waypoint detection - the plugin knows where you are and sets the next destination

#### Automatic Clipboard Integration

- Next waypoint automatically copies to your clipboard when you reach each destination
- Just paste into the Galaxy Map and jump!
- Click the waypoint button anytime to copy it again

#### View Your Entire Route

- Click "View Route" to see your complete journey in an easy-to-read table
- System names link directly to Inara.cz and EDSM.net
- Current waypoint highlighted in yellow
- Automatically updates as you progress

#### Never Lose Your Progress

- Routes automatically save when you close EDMC
- Resume exactly where you left off when you restart
- If you reload a route, the plugin automatically finds your current position and continues from there

### 🚢 Complete Fleet Carrier Management

#### Track All Your Carriers

- Select any of your fleet carriers from a dropdown menu
- View carrier name, callsign, current system, and fuel level at a glance
- See all carriers in one detailed window with comprehensive information

#### Detailed Carrier Information

- **Location**: Current system with links to Inara and EDSM
- **Fuel Status**: Tritium in tank and cargo, with clickable search for nearby sources
- **Balance**: Credit balance with proper formatting
- **Icy Rings & Pristine**: Automatic detection of mining opportunities in the current system
- **Cargo Details**: View complete cargo manifest with item names, quantities, and values
- **Stored Ships**: See all ships on your carrier with names and timestamps
- **Stored Modules**: Browse all outfitting modules available on your carrier, organized by category with prices and engineering status

#### Smart Route Warnings

- Get warned when your carrier needs Tritium restocking
- One-click search for nearby Tritium sources on Inara
- Automatic detection based on your route planning

### 💎 Road to Riches & Exploration

#### Track Profitable Bodies

- View terraformable worlds and their scan values
- See body names, subtypes, and estimated values
- Perfect for maximizing exploration profits

### 🌍 Multi-Language Support

GalaxyGPS speaks your language! The plugin automatically detects your EDMC language setting and displays everything in your preferred language. Supported languages include:

- **European**: Czech, Dutch, English, Finnish, French, German, Hungarian, Italian, Latvian, Polish, Russian, Slovenian, Spanish, Swedish, Ukrainian
- **Asian**: Chinese (Simplified), Japanese, Korean
- **Portuguese**: Portuguese (Brazil), Portuguese (Portugal)
- **Serbian**: Serbian (Latin), Serbian (Latin, Bosnia and Herzegovina)

All buttons, labels, messages, and windows are fully translated and update automatically when you change your language setting!

---

## Quick Start Guide 🚀

### Getting Started is Easy

1. **Install the Plugin** (see [Installation](#installation) below for detailed steps)
2. **Enable CAPI** in EDMC Settings (required for fleet carrier features)
3. **Optional**: Set up EDSM API for Icy Rings/Pristine detection
4. **Start Using**: Import a route or plot one directly!

### Basic Usage

**To Import a Route:**

1. Generate a route on [Spansh Plotter](https://www.spansh.co.uk/plotter)
2. Download the CSV file
3. Click "Import File" in GalaxyGPS
4. Select your CSV file
5. Start jumping! The next waypoint automatically copies to your clipboard.

**To Plot a Route:**

1. Click "Plot Route" in GalaxyGPS
2. Enter your starting system, destination, and jump range
3. Adjust efficiency slider if desired
4. Click "Calculate"
5. Your route is ready!

**To View Your Route:**

- Click "View Route" to see the complete journey
- Click any system name to open it on Inara or EDSM
- The current waypoint is highlighted in yellow

**To Manage Your Fleet Carrier:**

- Select your carrier from the dropdown at the top
- Click "View All" to see all your carriers
- Click "Cargo", "Ships", or "Modules" buttons to see detailed information
- Click "Inara" to open your carrier's page on Inara.cz

---

## Installation

### Simple Installation Steps

1. **Open EDMC Plugins Folder**:
   - Launch EDMarketConnector
   - Go to **Settings** > **Plugins** tab
   - Click the **"Open"** button

2. **Download the Latest Release**:
   - Visit the [Latest Release Page](https://github.com/Fenris159/EDMC_GalaxyGPS/releases/latest)
   - Download the **Source code (zip)** file
   - **Important**: Always use releases from this repository (`Fenris159/EDMC_GalaxyGPS`)

3. **Extract and Install**:
   - Extract the downloaded ZIP file
   - Create a folder named **`EDMC_GalaxyGPS`** in your plugins directory
   - Copy all extracted files into this folder
   - Ensure the structure looks like: `plugins/EDMC_GalaxyGPS/GalaxyGPS/`, `plugins/EDMC_GalaxyGPS/load.py`, etc.

4. **Restart EDMC**:
   - Close and restart EDMarketConnector
   - The plugin should appear in the plugins section

### Linux Users - Clipboard Setup

**Standard Linux (X11):**

- Install **xclip**: `sudo apt-get install xclip` (Debian/Ubuntu) or equivalent for your distribution

**Wayland Users:**

- Install **wl-clipboard**: `sudo apt-get install wl-clipboard`
- Set environment variable: `export EDMC_GALAXYGPS_XCLIP="/usr/bin/wl-copy"`
- See [Wayland Support](#wayland-support) section below for detailed setup instructions

---

## Requirements 📋

To use all features of GalaxyGPS, you'll need to configure the following in EDMC:

### CAPI (Companion API) - Required for Fleet Carrier Features

1. Open EDMC Settings
2. Navigate to the "Frontier Auth" or "CAPI" tab
3. Follow the instructions to authenticate with Frontier's servers
4. Ensure fleet carrier data fetching is enabled

**Why it's needed**: GalaxyGPS uses CAPI to automatically track your fleet carrier(s) location, fuel, balance, cargo, stored ships, and modules. Without CAPI, fleet carrier features won't work.

### EDSM API - Required for Icy Rings/Pristine Detection

1. Open EDMC Settings
2. Navigate to the "EDSM" tab
3. Enter your EDSM API key (get one from [EDSM.net](https://www.edsm.net/en/settings/api))
4. Ensure the connection is active

**Why it's needed**: The plugin queries EDSM to determine if a carrier's current system has icy rings and if they're pristine quality. This information helps you find the best mining locations.

### INARA API - Optional but Recommended

1. Open EDMC Settings
2. Navigate to the "Inara" tab
3. Enter your INARA API key (get one from [INARA.cz](https://inara.cz/settings/api/))

**Why it's recommended**: While most INARA features work via web links, having the API enabled provides better overall EDMC integration.

---

## How GalaxyGPS Works 🎮

### Route Planning Methods

**Import from Spansh:**

- Generate any route type on Spansh Plotter (Galaxy, Fleet Carrier, Road to Riches, Neutron, etc.)
- Download as CSV
- Import into GalaxyGPS - it automatically detects the route type and processes it correctly

**Create Custom Routes:**

- Create a simple CSV with "System Name" column (and optionally "Jumps")
- Import it just like a Spansh route
- The plugin handles the rest!

**Plot Directly:**

- Use the "Plot Route" button in GalaxyGPS
- Enter start system, destination, and jump range
- Adjust efficiency slider for route preferences
- Click "Calculate" to generate the route via Spansh API

### Route Management Features

- **Automatic Waypoint Detection**: The plugin finds your current position and sets the next waypoint
- **Progress Saving**: Your route progress saves automatically
- **Route Resumption**: If you reload a route, it automatically continues from where you are
- **View Route Window**: See your entire route with all details, links to Inara/EDSM, and visual indicators
- **Auto-Refresh**: The route window updates automatically as you progress

### Fleet Carrier Features

- **Automatic Tracking**: Carriers are tracked automatically via CAPI
- **Detailed Views**: Access cargo manifests, stored ships, and outfitting modules
- **Smart Warnings**: Get notified when Tritium restocking is needed
- **Quick Links**: One-click access to Inara and EDSM for systems and carriers
- **Data Persistence**: All carrier data is saved to CSV files for backup and analysis

---

## Technical Details 🔧

### Wayland Support

If you're using a Wayland desktop environment, you need to configure the plugin to use **wl-copy** instead of xclip.

#### Standard Wayland Installation (Non-Flatpak)

1. **Install wl-clipboard**: `sudo apt-get install wl-clipboard` (or equivalent)
2. **Set Environment Variable**:

   ```bash
   export EDMC_GALAXYGPS_XCLIP="/usr/bin/wl-copy"
   ```

   Or add to your shell profile (`.bashrc`, `.zshrc`, etc.):

   ```bash
   echo 'export EDMC_GALAXYGPS_XCLIP="/usr/bin/wl-copy"' >> ~/.bashrc
   ```

#### Flatpak Users

**Option A - Using Flatseal (Recommended):**

1. Install Flatseal: `flatpak install flathub com.github.tchx84.Flatseal`
2. Open Flatseal and select EDMarketConnector
3. Enable **Wayland windowing system** in Socket section
4. Enable **All system libraries, executables and static data** in Filesystem section
5. Add environment variable in Environment section:
   - **Name**: `EDMC_GALAXYGPS_XCLIP`
   - **Value**: `/run/host/usr/bin/wl-copy`
6. Restart EDMC

**Option B - Using Command Line:**

```bash
flatpak override --user io.edcd.EDMarketConnector \
  --socket=wayland \
  --filesystem=host-os \
  --env=EDMC_GALAXYGPS_XCLIP=/run/host/usr/bin/wl-copy
```

Then restart EDMarketConnector.

### Fleet Carrier CAPI Integration

The plugin automatically tracks your fleet carrier(s) using Frontier's CAPI. When EDMarketConnector fetches fleet carrier data, the plugin:

- **Automatically stores** all carrier information (location, fuel, balance, cargo, ships, modules, state, theme, etc.)
- **Saves data to CSV files** for easy access and backup:
  - `fleet_carriers.csv` - Main carrier information
  - `fleet_carrier_cargo.csv` - Detailed cargo manifest
  - `fleet_carrier_ships.csv` - Stored ships information
  - `fleet_carrier_modules.csv` - Stored modules information
- **Updates automatically** when you dock at your carrier or when journal events occur

All CSV files use UTF-8 encoding with BOM and persist between EDMC restarts. See `Documentation/CACHE_MODULES_README.md` for detailed column structure information.

### Plugin Priority

This plugin is configured to load **first** in EDMarketConnector, ensuring it appears at the top of the plugin list. This is achieved by:

- Being a **Package Plugin** (contains both `__init__.py` and `load.py`)
- Returning `'!GalaxyGPS'` from `plugin_start3()`, which sorts first alphabetically
- The folder name doesn't affect load order - you can name it anything you want

### Public API

GalaxyGPS provides a stable public API for other EDMC plugins to access route and carrier data. See `Documentation/API_DOCUMENTATION.md` for complete API reference and `examples/galaxygps_api_example/` for usage examples.

---

## Updates 🔄

GalaxyGPS features an **automatic update system** that checks for new versions when EDMC starts.

### How Auto-Updates Work

1. **Automatic Check**: When EDMC starts, the plugin checks GitHub for new versions
2. **Update Notification**: If available, a dialog shows the new version and changelog
3. **Installation**: If you choose to install, the update downloads when you close EDMC
4. **Manual Updates**: You can also download releases manually from the [GitHub repository](https://github.com/Fenris159/EDMC_GalaxyGPS/releases)

**Note**: Auto-updates require an active internet connection and only download if you confirm the installation prompt.

---

## Known Issues

Currently, there are no known issues! If you encounter any problems, please report them on the [GitHub Issues page](https://github.com/Fenris159/EDMC_GalaxyGPS/issues).

---

**Happy exploring, Commander!** 🎮✨

*GalaxyGPS - Because even in space, you need directions.*
