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

## How to use

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

If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will start back where you stopped.

Fly dangerous! o7

## Updates

**Note:** Auto-updates are not maintained in this fork. To update, download the latest code from this repository and replace your plugin files manually.

## Known Issues

TBD
