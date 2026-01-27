import csv
import json
import logging
import math
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.ttk as ttk
import traceback
import urllib.parse
import webbrowser
from time import sleep
from tkinter import *

import requests  # type: ignore
from config import appname, config, user_agent  # type: ignore
import timeout_session  # type: ignore
from monitor import monitor  # type: ignore
from ttkHyperlinkLabel import HyperlinkLabel  # type: ignore
from theme import theme  # type: ignore

# Import localization function from load.py
from load import plugin_tl  # type: ignore

from . import AutoCompleter, PlaceHolder
from .updater import SpanshUpdater
from .FleetCarrierManager import FleetCarrierManager
from .ui_helpers import ThemeSafeCanvas, ThemedCombobox
from .windows import show_carrier_details_window, show_route_window, refresh_route_window_if_open
from .ui.message_dialog import showinfo, showwarning, showerror, askyesno

# We need a name of plugin dir, not GalaxyGPS.py dir
plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
logger = logging.getLogger(f'{appname}.{plugin_name}')


def _round_distance(val):
    """Round distance value up to nearest hundredth. Used by Spansh route worker."""
    if not val or val == "":
        return ""
    try:
        val_float = float(val)
        return f"{math.ceil(val_float * 100) / 100:.2f}"
    except (ValueError, TypeError):
        return str(val) if val is not None else ""


class GalaxyGPS():
    def __init__(self, plugin_dir):
        version_file = os.path.join(plugin_dir, "version.json")
        with open(version_file, 'r') as version_fd:
            # Parse as JSON to handle quoted strings properly
            version_content = version_fd.read().strip()
            try:
                self.plugin_version = json.loads(version_content)
            except json.JSONDecodeError:
                # Fallback: if it's not valid JSON, treat as plain text (remove quotes if present)
                self.plugin_version = version_content.strip('"\'')

        self.update_available = False
        # Initialize Fleet Carrier Manager for CAPI integration
        self.fleet_carrier_manager = FleetCarrierManager(plugin_dir)
        # Initialize cache managers for detailed carrier data
        from GalaxyGPS.CargoDetailsManager import CargoDetailsManager
        from GalaxyGPS.StoredShipsManager import StoredShipsManager
        from GalaxyGPS.StoredModulesManager import StoredModulesManager
        self.cargo_manager = CargoDetailsManager(plugin_dir)
        self.ships_manager = StoredShipsManager(plugin_dir)
        self.modules_manager = StoredModulesManager(plugin_dir)
        self.roadtoriches = False
        self.fleetcarrier = False
        self.galaxy = False
        self.neutron = False  # Flag for neutron plotter routes with cumulative jumps
        self.next_stop = "No route planned"
        self.route = []
        self.route_full_data = []  # Store full CSV row data to preserve all columns
        self.route_fieldnames = []  # Original CSV fieldnames (preserved for display)
        # Note: These labels will be refreshed on language change via _refresh_localized_ui
        self.next_wp_label = plugin_tl("Next waypoint: ")
        self.route_window_ref = None  # Reference to open route window for dynamic updates
        self.jumpcountlbl_txt = plugin_tl("Estimated jumps left: ")
        self.bodieslbl_txt = plugin_tl("Bodies to scan at: ")
        self.fleetstocklbl_txt = plugin_tl("Warning: Restock Tritium")
        self.refuellbl_txt = plugin_tl("Time to scoop some fuel")
        self.bodies = ""
        self.parent = None
        self.plugin_dir = plugin_dir
        self.save_route_path = os.path.join(plugin_dir, 'route.csv')
        self.export_route_path = os.path.join(plugin_dir, 'Export for TCE.exp')
        self.offset_file_path = os.path.join(plugin_dir, 'offset')
        self.original_csv_path = None  # Store path to original CSV file to preserve all columns
        self.offset = 0
        self.jumps_left = 0
        self.error_txt = tk.StringVar()
        # LANG: Error message when route plotting fails
        self.plot_error = plugin_tl("Error while trying to plot a route, please try again.")
        self.system_header = "System Name"
        self.bodyname_header = "Body Name"
        self.bodysubtype_header = "Body Subtype"
        self.jumps_header = "Jumps"
        self.restocktritium_header = "Restock Tritium"
        self.refuel_header = "Refuel"
        self.pleaserefuel = False
        # distance tracking
        self.dist_next = ""
        self.dist_prev = ""
        self.dist_remaining = ""
        self.last_dist_next = ""
        self.fuel_used = ""
        self.fuel_remaining = ""
        self.has_fuel_used = False
        # Supercharge mode (Spansh neutron routing)
        # False = normal supercharge (x4)
        # True  = overcharge supercharge (x6)
        self.supercharge_overcharge = tk.BooleanVar(value=False)
        # Fleet carrier status display
        self.fleet_carrier_status_label = None
        self.fleet_carrier_combobox = None
        self.fleet_carrier_details_btn = None
        self.fleet_carrier_inara_btn = None
        self.fleet_carrier_system_label = None
        self.fleet_carrier_tritium_label = None
        self.fleet_carrier_separator = None
        self.selected_carrier_callsign = None
        self.fleet_carrier_var = tk.StringVar()
        self._gui_initialized = False  # Track if GUI has been initialized
        self._route_queue = queue.Queue()

    #   -- GUI part --
    def init_gui(self, parent):
        try:
            self.parent = parent
            
            # Check if GUI has already been initialized and widgets still exist
            if self._gui_initialized:
                if hasattr(self, 'frame') and self.frame:
                    try:
                        if self.frame.winfo_exists():
                            # Check if fleet carrier widgets still exist
                            if (hasattr(self, 'fleet_carrier_status_label') and 
                                self.fleet_carrier_status_label):
                                try:
                                    if self.fleet_carrier_status_label.winfo_exists():
                                        # GUI already initialized and widgets exist, return existing frame
                                        return self.frame
                                except (tk.TclError, AttributeError):
                                    # Widget was destroyed, need to reinitialize
                                    self._gui_initialized = False
                    except (tk.TclError, AttributeError):
                        # Frame was destroyed, need to reinitialize
                        self._gui_initialized = False
            
            # Check for and destroy any existing frames with fleet carrier widgets (defensive check)
            try:
                for widget in parent.winfo_children():
                    if isinstance(widget, tk.Frame):
                        # Check if this frame has our signature widgets
                        try:
                            for child in widget.winfo_children():
                                if isinstance(child, tk.Label):
                                    try:
                                        text = child.cget('text')
                                        if text and 'Fleet Carrier' in text:
                                            # Found our frame - reuse if it's our tracked frame
                                            if hasattr(self, 'frame') and widget == self.frame:
                                                try:
                                                    if self.frame.winfo_exists():
                                                        if (hasattr(self, 'fleet_carrier_status_label') and 
                                                            self.fleet_carrier_status_label and
                                                            self.fleet_carrier_status_label.winfo_exists()):
                                                            self._gui_initialized = True
                                                            return self.frame
                                                except (tk.TclError, AttributeError):
                                                    pass
                                            # Otherwise destroy duplicate frames
                                            for child_widget in widget.winfo_children():
                                                try:
                                                    child_widget.destroy()
                                                except Exception:
                                                    pass
                                            widget.destroy()
                                            break
                                    except Exception:
                                        pass
                        except Exception:
                            pass
            except Exception:
                pass
            
            # Destroy existing frame if it exists
            if hasattr(self, 'frame') and self.frame:
                try:
                    try:
                        self.frame.winfo_exists()
                        # Frame exists, destroy all child widgets first
                        for widget in self.frame.winfo_children():
                            try:
                                widget.destroy()
                            except Exception:
                                pass
                        self.frame.destroy()
                    except tk.TclError:
                        # Frame was already destroyed
                        pass
                except Exception:
                    pass
                finally:
                    self.frame = None
            
            # Reset fleet carrier widget references (they'll be recreated below)
            self.fleet_carrier_status_label = None
            self.fleet_carrier_combobox = None
            self.fleet_carrier_details_btn = None
            self.fleet_carrier_inara_btn = None
            self.fleet_carrier_buttons_container = None
            self.fleet_carrier_system_label = None
            self.fleet_carrier_icy_rings_label = None
            self.fleet_carrier_icy_rings_cb = None
            self.fleet_carrier_pristine_label = None
            self.fleet_carrier_pristine_cb = None
            self.fleet_carrier_tritium_label = None
            self.fleet_carrier_balance_value = None
            self.fleet_carrier_tritium_balance_container = None
            self.fleet_carrier_separator = None
            
            # Create frame fresh
            self.frame = tk.Frame(parent, borderwidth=2)
            self.frame.grid(sticky=tk.NSEW, columnspan=2)
            
            # Fleet carrier status display (compact, at top)
            # Create all widgets fresh
            # Use container frame for tight spacing (like System display)
            carrier_container = tk.Frame(self.frame, bg=self.frame.cget('bg'))
            # LANG: Label for fleet carrier selector
            self.fleet_carrier_status_label = tk.Label(carrier_container, text=plugin_tl("Fleet Carrier:"))
            self.fleet_carrier_status_label.pack(side=tk.LEFT)
            
            # Create custom themed combobox (replaces ttk.Combobox for full theme control)
            self.fleet_carrier_combobox = ThemedCombobox(
                carrier_container, 
                textvariable=self.fleet_carrier_var,
                state="readonly"
            )
            self.fleet_carrier_combobox.pack(side=tk.LEFT, padx=(2, 0))
            self.fleet_carrier_combobox.bind("<<ComboboxSelected>>", self.on_carrier_selected)
            
            # Create container for View All and Inara buttons
            buttons_container = tk.Frame(self.frame, bg=self.frame.cget('bg'))
            self.fleet_carrier_details_btn = tk.Button(
                buttons_container, 
                text=plugin_tl("View All"),  # LANG: Button to view all fleet carriers
                command=self.show_carrier_details_window
            )
            self.fleet_carrier_details_btn.pack(side=tk.LEFT, padx=(0, 2))
            self.fleet_carrier_inara_btn = tk.Button(
                buttons_container,
                text=plugin_tl("Inara"),  # LANG: Button to open Inara website
                command=self.open_selected_carrier_inara,
                width=6,
                fg="blue",
                cursor="hand2",
                state=tk.DISABLED
            )
            self.fleet_carrier_inara_btn.pack(side=tk.LEFT)
            # Store container reference
            self.fleet_carrier_buttons_container = buttons_container
            
            # Fleet Carrier System display - styled like EDMC's main system display
            # Orange "System:" label + clickable white system name with context menu
            # Use a container frame to pack them tightly side-by-side
            system_container = tk.Frame(self.frame, bg=self.frame.cget('bg'))
            # LANG: Label for fleet carrier system display
            self.fleet_carrier_system_label = tk.Label(system_container, text=plugin_tl("System:"))
            self.fleet_carrier_system_label.pack(side=tk.LEFT)
            self.fleet_carrier_system_name = HyperlinkLabel(
                system_container,
                compound=tk.RIGHT,
                url=self.fleet_carrier_system_url,
                popup_copy=True,
                text="",
                name='system'  # Must be 'system' for full context menu (EDSM, Inara, Spansh)
            )
            self.fleet_carrier_system_name.pack(side=tk.LEFT, padx=(2, 0))
            
            # Create container for Icy Rings and Pristine status - circular toggle buttons (radio-button style)
            # This will be gridded separately between system and tritium
            frame_bg = self.frame.cget('bg')
            rings_pristine_container = tk.Frame(self.frame, bg=frame_bg)
            
            self.fleet_carrier_icy_rings_var = tk.BooleanVar(value=False)
            
            # Icy Rings toggle button
            icy_rings_frame = tk.Frame(rings_pristine_container, bg=frame_bg)
            self.fleet_carrier_icy_rings_canvas = ThemeSafeCanvas(
                icy_rings_frame,
                width=20,
                height=20,
                highlightthickness=0,
                bg=frame_bg
            )
            self.fleet_carrier_icy_rings_canvas.pack(side=tk.LEFT, padx=(0, 2))
            # No click binding - read-only display
            # LANG: Label for icy rings status
            self.fleet_carrier_icy_rings_label = tk.Label(
                icy_rings_frame,
                text=plugin_tl("Icy Rings"),
                foreground="gray",
                bg=frame_bg
            )
            self.fleet_carrier_icy_rings_label.pack(side=tk.LEFT)
            icy_rings_frame.pack(side=tk.LEFT)
            
            # Pristine toggle button
            self.fleet_carrier_pristine_var = tk.BooleanVar(value=False)
            pristine_frame = tk.Frame(rings_pristine_container, bg=frame_bg)
            self.fleet_carrier_pristine_canvas = ThemeSafeCanvas(
                pristine_frame,
                width=20,
                height=20,
                highlightthickness=0,
                bg=frame_bg
            )
            self.fleet_carrier_pristine_canvas.pack(side=tk.LEFT, padx=(2, 0))  # Small left padding to separate from Icy Rings
            # No click binding - read-only display
            # LANG: Label for pristine ring status
            self.fleet_carrier_pristine_label = tk.Label(
                pristine_frame,
                text=plugin_tl("Pristine"),
                foreground="gray",
                bg=frame_bg
            )
            self.fleet_carrier_pristine_label.pack(side=tk.LEFT)
            pristine_frame.pack(side=tk.LEFT)
            
            # Store references to the frames for drawing and the container for grid placement
            self.fleet_carrier_icy_rings_cb = icy_rings_frame
            self.fleet_carrier_pristine_cb = pristine_frame
            self.fleet_carrier_rings_pristine_container = rings_pristine_container
            
            # Create container for Tritium and Balance
            tritium_balance_container = tk.Frame(self.frame, bg=self.frame.cget('bg'))
            self.fleet_carrier_tritium_label = tk.Label(
                tritium_balance_container, 
                text="Tritium:", 
                foreground="blue", 
                cursor="hand2",
                underline=-1
            )
            self.fleet_carrier_tritium_label.pack(side=tk.LEFT)
            
            # Balance label and value in separate labels for color control
            # LANG: Label for fleet carrier balance
            self.fleet_carrier_balance_label = tk.Label(tritium_balance_container, text=plugin_tl("Balance:"))
            self.fleet_carrier_balance_label.pack(side=tk.LEFT, padx=(10, 2))
            self.fleet_carrier_balance_value = tk.Label(tritium_balance_container, text="", foreground="green")
            self.fleet_carrier_balance_value.pack(side=tk.LEFT)
            
            # Store container reference
            self.fleet_carrier_tritium_balance_container = tritium_balance_container

            # Route info - make waypoint button more compact with minimal internal padding
            self.waypoint_prev_btn = tk.Button(self.frame, text="↑", command=self.goto_prev_waypoint, width=3, font=("Arial", 12, "bold"), padx=0, pady=0)
            self.waypoint_btn = tk.Button(self.frame, text=self.next_wp_label + '\n' + self.next_stop, command=self.copy_waypoint, width=20, padx=2, pady=2)
            self.waypoint_next_btn = tk.Button(self.frame, text="↓", command=self.goto_next_waypoint, width=3, font=("Arial", 12, "bold"), padx=0, pady=0)
            self.jumpcounttxt_lbl = tk.Label(self.frame, text=self.jumpcountlbl_txt + str(self.jumps_left))
            self.dist_prev_lbl = tk.Label(self.frame, text="")
            self.dist_next_lbl = tk.Label(self.frame, text="")
            # Create a container frame for fuel labels to display them side by side
            self.fuel_labels_frame = tk.Frame(self.frame)
            self.fuel_used_lbl = tk.Label(self.fuel_labels_frame, text="")
            self.fuel_remaining_lbl = tk.Label(self.fuel_labels_frame, text="")
            self.dist_remaining_lbl = tk.Label(self.frame, text="")
            self.bodies_lbl = tk.Label(self.frame, justify=LEFT, text=self.bodieslbl_txt + self.bodies)
            self.fleetrestock_lbl = tk.Label(self.frame, justify=tk.CENTER, text=self.fleetstocklbl_txt, fg="red")
            self.find_trit_btn = tk.Button(self.frame, text=plugin_tl("Find Trit"), command=self.find_tritium_on_inara)  # LANG: Button to find tritium on Inara
            self.refuel_lbl = tk.Label(self.frame, justify=tk.CENTER, text=self.refuellbl_txt, fg="red")
            self.error_lbl = tk.Label(self.frame, textvariable=self.error_txt)

            # Plotting GUI
            # LANG: Placeholder text for source system input
            self.source_ac = AutoCompleter(self.frame, plugin_tl("Source System"), width=30)
            # LANG: Placeholder text for destination system input
            self.dest_ac = AutoCompleter(self.frame, plugin_tl("Destination System"), width=30)
            
            # Create container frame for range entry and supercharge toggle (side-by-side)
            range_supercharge_container = tk.Frame(self.frame, bg=self.frame.cget('bg'))
            
            # LANG: Placeholder text for jump range input
            # Calculate width based on placeholder text length (add 2 chars padding)
            range_placeholder = plugin_tl("Range (LY)")
            range_width = max(8, len(range_placeholder) + 2)  # Minimum 8, or text length + padding
            self.range_entry = PlaceHolder(range_supercharge_container, range_placeholder, width=range_width)
            self.range_entry.pack(side=tk.LEFT, padx=(0, 10))
            
            # Supercharge toggle button - circular radio-button style that toggles like a checkbox
            # Create a frame to hold the toggle button and label
            supercharge_frame = tk.Frame(range_supercharge_container, bg=self.frame.cget('bg'))
            # Create a custom toggle button using a canvas to draw a circle
            frame_bg = self.frame.cget('bg')
            self.supercharge_toggle_canvas = ThemeSafeCanvas(
                supercharge_frame,
                width=24,
                height=24,
                highlightthickness=0,
                bg=frame_bg,
                cursor="hand2"
            )
            self.supercharge_toggle_canvas.pack(side=tk.LEFT, padx=(0, 8))
            
            # Bind click event to toggle
            self.supercharge_toggle_canvas.bind("<Button-1>", self._toggle_supercharge)
            
            # Create label for the text - match font size of Plot Route button (default button font)
            # LANG: Label for neutron star supercharge toggle
            self.supercharge_label = tk.Label(
                supercharge_frame,
                text=plugin_tl("Supercharge"),
                foreground="orange",
                bg=frame_bg,
                cursor="hand2"
            )
            self.supercharge_label.pack(side=tk.LEFT)
            self.supercharge_label.bind("<Button-1>", self._toggle_supercharge)
            
            # Pack supercharge frame into container
            supercharge_frame.pack(side=tk.LEFT)
            
            # Store reference to the container frame for grid positioning
            self.supercharge_cb = range_supercharge_container
            
            # Draw the initial circles (unchecked state) - do this after all setup
            # Use after_idle to ensure canvas is ready
            self.frame.after_idle(self._draw_supercharge_toggle)
            self.frame.after_idle(self._draw_icy_rings_toggle)
            self.frame.after_idle(self._draw_pristine_toggle)

            # LANG: Label for efficiency slider
            self.efficiency_slider = tk.Scale(self.frame, from_=1, to=100, orient=tk.HORIZONTAL, label=plugin_tl("Efficiency (%)"), foreground="orange", sliderrelief=tk.FLAT, bd=0, highlightthickness=0, troughcolor="red")
            self.efficiency_slider.set(60)
            
            # Create container for basic controls first
            self.basic_controls_container = tk.Frame(self.frame)
            
            # Create buttons as children of the container for tight packing
            # LANG: Button to import route from CSV file
            self.csv_route_btn = tk.Button(self.basic_controls_container, text=plugin_tl("Import file"), command=self.plot_file)
            # LANG: Button to view current route
            self.view_route_btn = tk.Button(self.basic_controls_container, text=plugin_tl("View Route"), command=self.show_route_window)
            # LANG: Button to show route plotting GUI
            self.plot_gui_btn = tk.Button(self.basic_controls_container, text=plugin_tl("Plot route"), command=self.show_plot_gui)
            
            # Create container for plotting controls (Calculate, Cancel)
            self.plotting_controls_container = tk.Frame(self.frame)
            
            # Plotting controls as children of their container
            # LANG: Button to calculate/compute route
            self.plot_route_btn = tk.Button(self.plotting_controls_container, text=plugin_tl("Calculate"), command=self.plot_route)
            # LANG: Button to cancel route plotting
            self.cancel_plot = tk.Button(self.plotting_controls_container, text=plugin_tl("Cancel"), command=lambda: self.show_plot_gui(False))
            
            # Clear route button remains a child of self.frame
            # LANG: Button to clear current route
            self.clear_route_btn = tk.Button(self.frame, text=plugin_tl("Clear route"), command=self.clear_route)

            row = 0
            # Fleet carrier status at the top
            # Store grid positions to prevent accidental repositioning
            carrier_container.grid(row=row, column=0, columnspan=2, padx=2, pady=2, sticky=tk.W)
            # Store grid info to prevent repositioning
            self._fleet_carrier_row_start = row
            self.update_fleet_carrier_dropdown()
            row += 1
            # View All and Inara buttons packed together in column 0
            self.fleet_carrier_buttons_container.grid(row=row, column=0, padx=2, pady=2, sticky=tk.W)
            row += 1
            # Fleet carrier system location
            system_container.grid(row=row, column=0, columnspan=2, padx=2, pady=2, sticky=tk.W)
            self.update_fleet_carrier_system_display()
            row += 1
            # Icy Rings and Pristine status on their own row
            self.fleet_carrier_rings_pristine_container.grid(row=row, column=0, columnspan=2, padx=2, pady=2, sticky=tk.W)
            self.update_fleet_carrier_rings_status()
            row += 1
            # Fleet carrier Tritium display (clickable to search Inara) with Balance packed next to it
            self.fleet_carrier_tritium_balance_container.grid(row=row, column=0, columnspan=2, padx=2, pady=2, sticky=tk.W)
            # Bind click and hover events - handlers will check if data is available
            self.fleet_carrier_tritium_label.bind("<Button-1>", lambda e: self._on_tritium_click())
            self.fleet_carrier_tritium_label.bind("<Enter>", lambda e: self._on_tritium_enter())
            self.fleet_carrier_tritium_label.bind("<Leave>", lambda e: self._on_tritium_leave())
            self.update_fleet_carrier_tritium_display()
            self.update_fleet_carrier_balance_display()
            row += 1
            # Separator line
            self.fleet_carrier_separator = tk.Frame(self.frame, height=1, bg="gray")
            self.fleet_carrier_separator.grid(row=row, column=0, columnspan=4, sticky=tk.EW, padx=2, pady=2)
            self._fleet_carrier_row_end = row  # Store end row for fleet carrier section
            row += 1
            # Route waypoint controls - buttons in column 0
            # All buttons natural size (no sticky) - column width determined by widest button
            # Buttons will auto-center in the column
            # No horizontal padding for tight spacing between columns
            self.waypoint_prev_btn.grid(row=row, column=0, padx=0, pady=5)
            row += 1
            self.waypoint_btn.grid(row=row, column=0, padx=0, pady=5)
            row += 1
            self.waypoint_next_btn.grid(row=row, column=0, padx=0, pady=5)
            row += 1
            # Info labels in their own rows after the buttons
            # Swapped: dist_prev (Number of Jumps) now appears before dist_remaining (Remaining jumps afterwards)
            self.dist_prev_lbl.grid(row=row, column=0, columnspan=2, padx=0, pady=2, sticky=tk.W)
            row += 1
            self.dist_remaining_lbl.grid(row=row, column=0, columnspan=2, padx=0, pady=2, sticky=tk.W)
            row += 1
            self.dist_next_lbl.grid(row=row, column=0, columnspan=2, padx=0, pady=2, sticky=tk.W)
            row += 1
            self.fuel_labels_frame.grid(row=row, column=0, columnspan=2, padx=0, pady=2, sticky=tk.W)
            row += 1
            self.bodies_lbl.grid(row=row, columnspan=4, padx=2, sticky=tk.W)
            row += 1
            # Fleet restock warning - centered and red
            self.fleetrestock_lbl.grid(row=row, column=0, columnspan=4, padx=2, sticky=tk.EW)
            row += 1
            self.find_trit_btn.grid(row=row, column=0, padx=2, pady=2, sticky=tk.W)
            row += 1
            # Refuel warning - centered and red
            self.refuel_lbl.grid(row=row, column=0, columnspan=4, padx=2, sticky=tk.EW)
            row += 1
            self.source_ac.grid(row=row, columnspan=4, padx=2, pady=(5,0)) # The AutoCompleter takes two rows to show the list when needed, so we skip one
            row += 2
            self.dest_ac.grid(row=row, columnspan=4, padx=2, pady=(5,0))
            row += 2
            self.supercharge_cb.grid(row=row, column=0, padx=2, pady=5, sticky=tk.W)
            row += 1
            self.efficiency_slider.grid(row=row, padx=2, pady=(0, 5), columnspan=3, sticky=tk.EW)
            # Configure columns to allow slider to expand with window width
            # Column 0 has weight=0 to auto-size to range_entry, columns 1 and 2 expand
            self.frame.grid_columnconfigure(0, weight=0)
            self.frame.grid_columnconfigure(1, weight=1)
            self.frame.grid_columnconfigure(2, weight=1)
            row += 1
            
            # Pack buttons inside their container
            self.csv_route_btn.pack(side=tk.LEFT, padx=(0, 2))
            self.view_route_btn.pack(side=tk.LEFT, padx=(0, 2))
            self.plot_gui_btn.pack(side=tk.LEFT)
            # Grid the basic controls container into the main frame
            self.basic_controls_container.grid(row=row, column=0, padx=2, pady=5, sticky=tk.W)
            
            # Pack plotting buttons inside their container
            self.plot_route_btn.pack(side=tk.LEFT, padx=(0, 2))
            self.cancel_plot.pack(side=tk.LEFT)
            # Grid the plotting controls container into the main frame (same row)
            self.plotting_controls_container.grid(row=row, column=0, padx=2, pady=5, sticky=tk.W)
            # Initially hide plotting controls container (they'll be shown when plotting state is active)
            self.plotting_controls_container.grid_remove()
            row += 1
            self.clear_route_btn.grid(row=row, column=0, padx=(2, 1), pady=5, sticky=tk.W)
            row += 1
            self.error_lbl.grid(row=row, columnspan=4, padx=2)
            self.error_lbl.grid_remove()
            row += 1

            # Check if we're having a valid range on the fly
            self.range_entry.var.trace('w', self.check_range)

            # Initialize GUI to appropriate state
            self.update_gui()
            
            # Mark GUI as initialized
            self._gui_initialized = True
            
            # Apply EDMC theme to the main frame and all widgets
            theme.update(self.frame)
            
            # Now style the combobox with theme-aware colors (after theme.update() has been applied)
            # Get frame background color AFTER theme.update() to get the correct theme color
            frame_bg = self.frame.cget('bg')
            
            # Convert named system colors to actual color values for ttk.Style
            # ttk.Style may not accept 'systemwindow' directly, so we need to get the actual color
            def get_actual_color(color_name):
                """Convert a named system color to its actual RGB hex value"""
                try:
                    # Create a temporary widget to get the actual color value
                    temp_widget = tk.Label(self.frame, bg=color_name)
                    temp_widget.update_idletasks()
                    actual_color = temp_widget.cget('bg')
                    temp_widget.destroy()
                    return actual_color
                except:
                    return color_name  # Fallback to original if conversion fails
            
            # Determine background color based on theme
            try:
                from config import config  # type: ignore
                current_theme = config.get_int('theme')
                # Theme 0 = default (light), 1 = dark, 2 = transparent (dark)
                if current_theme in [1, 2]:
                    # Dark or transparent theme
                    if frame_bg and frame_bg.strip():
                        # For transparent theme (2), 'systemwindow' is a valid background color
                        if current_theme == 2 and frame_bg.lower() == 'systemwindow':
                            # Convert 'systemwindow' to actual color for ttk.Style
                            bg_color = get_actual_color('systemwindow')
                        elif frame_bg.lower() not in ['white', '#ffffff', 'systembuttonface']:
                            # If it's already a hex color, use it directly
                            if frame_bg.startswith('#'):
                                bg_color = frame_bg
                            else:
                                # Convert named color to actual value
                                bg_color = get_actual_color(frame_bg)
                        else:
                            bg_color = '#1e1e1e'  # Fallback for dark theme
                    else:
                        bg_color = '#1e1e1e'  # Dark gray/black typical of EDMC dark theme
                else:
                    # Light/default theme
                    if frame_bg and frame_bg.strip() and frame_bg.lower() not in ['black', '#000000', '#1e1e1e', 'systemwindow']:
                        if frame_bg.startswith('#'):
                            bg_color = frame_bg
                        else:
                            bg_color = get_actual_color(frame_bg)
                    else:
                        bg_color = '#ffffff'  # White for light theme
            except:
                # Fallback: detect from background color
                if frame_bg and frame_bg.strip():
                    if frame_bg.lower() == 'systemwindow':
                        bg_color = get_actual_color('systemwindow')
                    elif frame_bg.startswith('#'):
                        bg_color = frame_bg
                    elif frame_bg.lower() not in ['white', '#ffffff', 'systembuttonface']:
                        bg_color = get_actual_color(frame_bg)
                    else:
                        bg_color = '#1e1e1e'  # Default to dark
                else:
                    bg_color = '#1e1e1e'  # Default to dark
            
            # Style the custom combobox using its built-in theme styling method
            try:
                self.fleet_carrier_combobox.apply_theme_styling()
            except Exception as e:
                logger.debug(f'[init_gui] Error applying theme styling to combobox: {e}')

            try:
                theme.update(self.efficiency_slider)
            except Exception as e:
                logger.debug(f'[init_gui] Error applying theme styling to efficiency slider: {e}')
            
            # Apply initial theme-aware colors to labels
            try:
                self._update_combobox_theme()
            except Exception as e:
                logger.debug(f'[init_gui] Error applying initial theme colors: {e}')
            
            return self.frame
        except Exception as e:
            logger.error(f"Error in init_gui: {traceback.format_exc()}")
            # Try to return a minimal frame so plugin doesn't completely disappear
            try:
                if not hasattr(self, 'frame') or not self.frame:
                    self.frame = tk.Frame(parent, borderwidth=2)
                    self.frame.grid(sticky=tk.NSEW, columnspan=2)
                    error_label = tk.Label(self.frame, text=f"Error loading plugin: {str(e)}", fg="red")
                    error_label.pack()
                return self.frame
            except Exception:
                # Last resort - return None and let EDMC handle it
                return None
    
    def _update_combobox_theme(self):
        """
        Update the fleet carrier combobox and orange label colors when EDMC theme changes.
        Called by prefs_changed() in load.py.
        """
        # Update combobox
        if hasattr(self, 'fleet_carrier_combobox'):
            try:
                self.fleet_carrier_combobox.apply_theme_styling()
                logger.debug('[_update_combobox_theme] Successfully updated combobox theme')
            except Exception as e:
                logger.debug(f'[_update_combobox_theme] Error applying theme to combobox: {e}')
        
        # Update orange labels to be theme-aware
        try:
            from config import config  # type: ignore
            current_theme = config.get_int('theme')
            # Theme 0 = default (light), 1 = dark, 2 = transparent (dark)
            label_color = "black" if current_theme == 0 else "orange"
            
            # Update all orange labels
            labels_to_update = []
            
            if hasattr(self, 'fleet_carrier_icy_rings_label'):
                labels_to_update.append(self.fleet_carrier_icy_rings_label)
            if hasattr(self, 'fleet_carrier_pristine_label'):
                labels_to_update.append(self.fleet_carrier_pristine_label)
            if hasattr(self, 'supercharge_label'):
                labels_to_update.append(self.supercharge_label)
            if hasattr(self, 'efficiency_slider'):
                labels_to_update.append(self.efficiency_slider)
            if hasattr(self, 'source_ac') and hasattr(self.source_ac, 'label'):
                labels_to_update.append(self.source_ac.label)
            
            for label in labels_to_update:
                try:
                    label.config(foreground=label_color)
                except Exception as e:
                    logger.debug(f'[_update_combobox_theme] Error updating label color: {e}')
            
            # Redraw toggles to update their label colors
            try:
                self._draw_icy_rings_toggle()
                self._draw_pristine_toggle()
            except Exception as e:
                logger.debug(f'[_update_combobox_theme] Error redrawing toggles: {e}')
            
            # Update AutoCompleter text boxes to use correct text color
            try:
                if hasattr(self, 'source_ac'):
                    self.source_ac.set_default_style()
                if hasattr(self, 'dest_ac'):
                    self.dest_ac.set_default_style()
            except Exception as e:
                logger.debug(f'[_update_combobox_theme] Error updating AutoCompleter colors: {e}')
            
            logger.debug(f'[_update_combobox_theme] Updated label colors to {label_color} for theme {current_theme}')
        except Exception as e:
            logger.debug(f'[_update_combobox_theme] Error updating label colors: {e}')
    
    def _refresh_localized_ui(self):
        """
        Refresh all localized UI strings when language changes.
        Called by prefs_changed() in load.py.
        """
        try:
            # Refresh button labels
            if hasattr(self, 'fleet_carrier_details_btn'):
                self.fleet_carrier_details_btn.config(text=plugin_tl("View All"))
            if hasattr(self, 'fleet_carrier_inara_btn'):
                self.fleet_carrier_inara_btn.config(text=plugin_tl("Inara"))
            if hasattr(self, 'find_trit_btn'):
                self.find_trit_btn.config(text=plugin_tl("Find Trit"))
            if hasattr(self, 'csv_route_btn'):
                self.csv_route_btn.config(text=plugin_tl("Import file"))
            if hasattr(self, 'view_route_btn'):
                self.view_route_btn.config(text=plugin_tl("View Route"))
            if hasattr(self, 'plot_gui_btn'):
                self.plot_gui_btn.config(text=plugin_tl("Plot route"))
            if hasattr(self, 'plot_route_btn'):
                self.plot_route_btn.config(text=plugin_tl("Calculate"))
            if hasattr(self, 'cancel_plot'):
                self.cancel_plot.config(text=plugin_tl("Cancel"))
            if hasattr(self, 'clear_route_btn'):
                self.clear_route_btn.config(text=plugin_tl("Clear route"))
            
            # Refresh main UI labels
            if hasattr(self, 'fleet_carrier_status_label'):
                self.fleet_carrier_status_label.config(text=plugin_tl("Fleet Carrier:"))
            if hasattr(self, 'fleet_carrier_system_label'):
                self.fleet_carrier_system_label.config(text=plugin_tl("System:"))
            if hasattr(self, 'fleet_carrier_balance_label'):
                self.fleet_carrier_balance_label.config(text=plugin_tl("Balance:"))
            if hasattr(self, 'fleet_carrier_icy_rings_label'):
                self.fleet_carrier_icy_rings_label.config(text=plugin_tl("Icy Rings"))
            if hasattr(self, 'fleet_carrier_pristine_label'):
                self.fleet_carrier_pristine_label.config(text=plugin_tl("Pristine"))
            if hasattr(self, 'supercharge_label'):
                self.supercharge_label.config(text=plugin_tl("Supercharge"))
            
            # Refresh slider label
            if hasattr(self, 'efficiency_slider'):
                self.efficiency_slider.config(label=plugin_tl("Efficiency (%)"))
            
            # Refresh placeholder text for AutoCompleter and PlaceHolder widgets
            if hasattr(self, 'source_ac'):
                new_source_placeholder = plugin_tl("Source System")
                old_placeholder = self.source_ac.placeholder
                self.source_ac.placeholder = new_source_placeholder
                # If currently showing placeholder text, update it
                if self.source_ac.get() == old_placeholder:
                    self.source_ac.put_placeholder()
            
            if hasattr(self, 'dest_ac'):
                new_dest_placeholder = plugin_tl("Destination System")
                old_placeholder = self.dest_ac.placeholder
                self.dest_ac.placeholder = new_dest_placeholder
                # If currently showing placeholder text, update it
                if self.dest_ac.get() == old_placeholder:
                    self.dest_ac.put_placeholder()
            
            if hasattr(self, 'range_entry'):
                new_range_placeholder = plugin_tl("Range (LY)")
                old_placeholder = self.range_entry.placeholder
                self.range_entry.placeholder = new_range_placeholder
                # If currently showing placeholder text, update it
                if self.range_entry.get() == old_placeholder:
                    self.range_entry.put_placeholder()
                # Update width to accommodate translated text
                range_width = max(8, len(new_range_placeholder) + 2)
                self.range_entry.config(width=range_width)
            
            # Refresh dynamic route label text (used in compute_distances)
            self.next_wp_label = plugin_tl("Next waypoint: ")
            self.jumpcountlbl_txt = plugin_tl("Estimated jumps left: ")
            self.bodieslbl_txt = plugin_tl("Bodies to scan at: ")
            self.fleetstocklbl_txt = plugin_tl("Warning: Restock Tritium")
            self.refuellbl_txt = plugin_tl("Time to scoop some fuel")
            self.plot_error = plugin_tl("Error while trying to plot a route, please try again.")
            
            # If route is loaded, recalculate distances to update displayed labels
            if hasattr(self, 'route') and self.route:
                self.compute_distances()
            
            logger.debug('[_refresh_localized_ui] Refreshed UI strings for language change')
        except Exception as e:
            logger.debug(f'[_refresh_localized_ui] Error refreshing localized UI: {e}')
    
    def _draw_supercharge_toggle(self):
        """
        Draw the circular toggle button (radio-button style) for Supercharge.
        Shows filled orange circle when checked, empty circle when unchecked.
        """
        if not hasattr(self, 'supercharge_toggle_canvas'):
            return
        
        try:
            # Clear the canvas
            self.supercharge_toggle_canvas.delete("all")
            
            # Get the current state
            is_checked = self.supercharge_overcharge.get()
            
            # Get background color
            try:
                bg_color = self.supercharge_toggle_canvas.cget('bg')
            except:
                bg_color = "white"
            
            # Draw outer circle (always visible) - larger size (20x20 circle in 24x24 canvas)
            self.supercharge_toggle_canvas.create_oval(
                2, 2, 22, 22,
                outline="orange",
                width=2,
                fill=bg_color if not is_checked else "orange"
            )
            
            # If checked, draw inner filled circle
            if is_checked:
                self.supercharge_toggle_canvas.create_oval(
                    7, 7, 17, 17,
                    outline="orange",
                    fill="orange",
                    width=1
                )
        except Exception:
            # Silently fail if canvas isn't ready yet
            pass
    
    def _toggle_supercharge(self, event=None):
        """
        Toggle the supercharge state and redraw the toggle button.
        """
        # Toggle the boolean variable
        current_state = self.supercharge_overcharge.get()
        self.supercharge_overcharge.set(not current_state)
        
        # Redraw the toggle button
        self._draw_supercharge_toggle()
    
    def _draw_icy_rings_toggle(self):
        """
        Draw the circular toggle button for Icy Rings (read-only display).
        Shows filled orange circle when checked, empty circle when unchecked.
        Updates label color: orange when checked, gray when unchecked.
        """
        if not hasattr(self, 'fleet_carrier_icy_rings_canvas'):
            return
        
        try:
            # Clear the canvas
            self.fleet_carrier_icy_rings_canvas.delete("all")
            
            # Get the current state
            is_checked = self.fleet_carrier_icy_rings_var.get()
            
            # Get background color
            try:
                bg_color = self.fleet_carrier_icy_rings_canvas.cget('bg')
            except:
                bg_color = "white"
            
            # Draw outer circle (always visible)
            # Use theme-aware color when checked, gray when unchecked
            from config import config  # type: ignore
            current_theme = config.get_int('theme')
            active_color = "black" if current_theme == 0 else "orange"
            
            outline_color = active_color if is_checked else "gray"
            self.fleet_carrier_icy_rings_canvas.create_oval(
                2, 2, 18, 18,
                outline=outline_color,
                width=2,
                fill=bg_color if not is_checked else active_color
            )
            
            # If checked, draw inner filled circle
            if is_checked:
                inner_color = "darkgray" if current_theme == 0 else "darkorange"
                self.fleet_carrier_icy_rings_canvas.create_oval(
                    6, 6, 14, 14,
                    outline=inner_color,
                    fill=active_color,
                    width=1
                )
            
            # Update label color: active color when checked, gray when unchecked
            if hasattr(self, 'fleet_carrier_icy_rings_label'):
                label_color = active_color if is_checked else "gray"
                self.fleet_carrier_icy_rings_label.config(foreground=label_color)
        except Exception:
            pass
    
    def _draw_pristine_toggle(self):
        """
        Draw the circular toggle button for Pristine (read-only display).
        Shows filled orange circle when checked, empty circle when unchecked.
        Updates label color: orange when checked, gray when unchecked.
        """
        if not hasattr(self, 'fleet_carrier_pristine_canvas'):
            return
        
        try:
            # Clear the canvas
            self.fleet_carrier_pristine_canvas.delete("all")
            
            # Get the current state
            is_checked = self.fleet_carrier_pristine_var.get()
            
            # Get background color
            try:
                bg_color = self.fleet_carrier_pristine_canvas.cget('bg')
            except:
                bg_color = "white"
            
            # Draw outer circle (always visible)
            # Use theme-aware color when checked, gray when unchecked
            from config import config  # type: ignore
            current_theme = config.get_int('theme')
            active_color = "black" if current_theme == 0 else "orange"
            
            outline_color = active_color if is_checked else "gray"
            self.fleet_carrier_pristine_canvas.create_oval(
                2, 2, 18, 18,
                outline=outline_color,
                width=2,
                fill=bg_color if not is_checked else active_color
            )
            
            # If checked, draw inner filled circle
            if is_checked:
                inner_color = "darkgray" if current_theme == 0 else "darkorange"
                self.fleet_carrier_pristine_canvas.create_oval(
                    6, 6, 14, 14,
                    outline=inner_color,
                    fill=active_color,
                    width=1
                )
            
            # Update label color: active color when checked, gray when unchecked
            if hasattr(self, 'fleet_carrier_pristine_label'):
                label_color = active_color if is_checked else "gray"
                self.fleet_carrier_pristine_label.config(foreground=label_color)
        except Exception:
            pass

    def show_plot_gui(self, show=True):
        """Show or hide the route plotting interface"""
        if show:
            # Hide autocomplete lists before switching
            self.source_ac.hide_list()
            self.dest_ac.hide_list()
            self._update_widget_visibility('plotting')
        else:
            # Clear placeholders if empty
            if not self.source_ac.var.get() or self.source_ac.var.get() == self.source_ac.placeholder:
                self.source_ac.put_placeholder()
            if not self.dest_ac.var.get() or self.dest_ac.var.get() == self.dest_ac.placeholder:
                self.dest_ac.put_placeholder()
            self.source_ac.hide_list()
            self.dest_ac.hide_list()
            # Return to appropriate state
            self.update_gui()

    def set_source_ac(self, text):
        self.source_ac.delete(0, tk.END)
        self.source_ac.insert(0, text)
        self.source_ac.set_default_style()

    def show_route_gui(self, show):
        """Show or hide the route navigation interface (legacy method, now uses centralized approach)"""
        self.hide_error()
        if show and len(self.route) > 0:
            self._update_widget_visibility('route')
        else:
            self._update_widget_visibility('empty')

    def _update_widget_visibility(self, state):
        """
        Centralized method to manage widget visibility based on UI state.
        
        States:
        - 'plotting': Show route plotting interface
        - 'route': Show route navigation interface
        - 'empty': No route loaded, show basic controls
        """
        # Define widget groups for each state
        route_widgets = [
            self.waypoint_prev_btn, self.waypoint_btn, self.waypoint_next_btn,
            self.clear_route_btn,
            self.dist_prev_lbl, self.dist_next_lbl, self.fuel_labels_frame, self.dist_remaining_lbl
        ]
        
        plotting_widgets = [
            self.source_ac, self.dest_ac,
            self.supercharge_cb, self.efficiency_slider
        ]
        
        # Control containers (replaces individual button management)
        basic_controls_container = [self.basic_controls_container] if hasattr(self, 'basic_controls_container') else []
        plotting_controls_container = [self.plotting_controls_container] if hasattr(self, 'plotting_controls_container') else []
        
        info_labels = [
            self.bodies_lbl, self.fleetrestock_lbl, self.refuel_lbl, self.find_trit_btn
        ]
        
        # Hide all widgets first (except fleet carrier status and basic controls which are always visible)
        # Fleet carrier widgets should never be hidden or repositioned
        fleet_carrier_widgets = [
            self.fleet_carrier_status_label, self.fleet_carrier_combobox
        ]
        
        # Add containers that hold multiple widgets
        if hasattr(self, 'fleet_carrier_buttons_container'):
            fleet_carrier_widgets.append(self.fleet_carrier_buttons_container)
        if hasattr(self, 'fleet_carrier_tritium_balance_container'):
            fleet_carrier_widgets.append(self.fleet_carrier_tritium_balance_container)
        
        # Also include the separator in the always-visible list
        if hasattr(self, 'fleet_carrier_separator'):
            fleet_carrier_widgets.append(self.fleet_carrier_separator)
        
        # Fleet carrier widgets are always visible, but basic controls can be hidden/shown
        always_visible = fleet_carrier_widgets
        
        # Hide all widgets first (except fleet carrier widgets which are always visible)
        for widget in route_widgets + plotting_widgets + info_labels + basic_controls_container + plotting_controls_container:
            if widget not in always_visible:
                widget.grid_remove()
        
        # Show widgets based on state
        if state == 'plotting':
            # Hide basic controls container (Plot route, Import file, View Route)
            for widget in basic_controls_container:
                widget.grid_remove()
            
            # Show plotting interface (inputs + Calculate/Cancel buttons)
            for widget in plotting_widgets:
                widget.grid()
            for widget in plotting_controls_container:
                widget.grid()
            
            # Prefill source if needed
            if not self.source_ac.var.get() or self.source_ac.var.get() == self.source_ac.placeholder:
                current_system = monitor.state.get('SystemName')
                if current_system:
                    self.source_ac.set_text(current_system, placeholder_style=False)
                else:
                    self.source_ac.put_placeholder()
        elif state == 'empty':
            # Hide plotting widgets and container
            for widget in plotting_widgets:
                widget.grid_remove()
            for widget in plotting_controls_container:
                widget.grid_remove()
            
            # Show basic controls container
            for widget in basic_controls_container:
                widget.grid()
        elif state == 'route' and len(self.route) > 0:
            # Hide plotting widgets and container
            for widget in plotting_widgets:
                widget.grid_remove()
            for widget in plotting_controls_container:
                widget.grid_remove()
            
            # Show basic controls container
            for widget in basic_controls_container:
                widget.grid()
            
            # Show route navigation interface
            for widget in route_widgets:
                widget.grid()
            
            # Update waypoint button text - use config() for more reliable updates
            if hasattr(self, 'waypoint_btn') and hasattr(self, 'next_stop') and hasattr(self, 'next_wp_label'):
                try:
                    button_text = self.next_wp_label + '\n' + (self.next_stop if self.next_stop else "")
                    self.waypoint_btn.config(text=button_text)
                    self.waypoint_btn.update_idletasks()
                except Exception:
                    pass
            
            # Update distance labels
            # Update distance labels - always show them when route is loaded
            self.dist_prev_lbl["text"] = self.dist_prev
            self.dist_remaining_lbl["text"] = self.dist_remaining
            
            # Hide "Next waypoint jumps" for neutron routes (only show for other route types)
            if self.neutron:
                self.dist_next_lbl.grid_remove()
            else:
                self.dist_next_lbl["text"] = self.dist_next
                self.dist_next_lbl.grid()
            
            # Update fuel labels display
            # Pack labels inside the container frame to display side by side
            # Clear any existing packed widgets first
            for widget in self.fuel_labels_frame.winfo_children():
                widget.pack_forget()
            
            show_fuel_frame = False
            
            logger.debug(f"[_update_widget_visibility] offset={self.offset}, route_len={len(self.route)}, galaxy={self.galaxy}, has_fuel_used={self.has_fuel_used}, fuel_used={self.fuel_used!r}, fuel_remaining={self.fuel_remaining!r}")
            
            # Show Fuel Used if available
            if self.has_fuel_used and self.fuel_used:
                # fuel_used is already rounded and formatted as string from compute_distances()
                self.fuel_used_lbl["text"] = f"{plugin_tl('Fuel Used')}: {self.fuel_used}"
                self.fuel_used_lbl.pack(side=tk.LEFT, padx=(0, 10))
                show_fuel_frame = True
                logger.debug(f"[_update_widget_visibility] Showing Fuel Used label")
            
            # Show Fuel Remaining for galaxy routes if available
            if self.galaxy and self.fuel_remaining:
                self.fuel_remaining_lbl["text"] = f"{plugin_tl('Fuel Remaining')}: {self.fuel_remaining}"
                self.fuel_remaining_lbl.pack(side=tk.LEFT)
                show_fuel_frame = True
                logger.debug(f"[_update_widget_visibility] Showing Fuel Remaining label")
            
            # Show or hide the container frame based on whether any fuel labels are visible
            if show_fuel_frame:
                self.fuel_labels_frame.grid()
                logger.debug(f"[_update_widget_visibility] Showing fuel_labels_frame")
            else:
                self.fuel_labels_frame.grid_remove()
                logger.debug(f"[_update_widget_visibility] Hiding fuel_labels_frame")
            
            # Update waypoint button states
            if self.offset == 0:
                self.waypoint_prev_btn.config(state=tk.DISABLED)
            else:
                self.waypoint_prev_btn.config(state=tk.NORMAL)
            
            if self.offset == len(self.route) - 1:
                self.waypoint_next_btn.config(state=tk.DISABLED)
            else:
                self.waypoint_next_btn.config(state=tk.NORMAL)
            
            # Show conditional info labels
            if self.roadtoriches:
                self.bodies_lbl["text"] = self.bodieslbl_txt + self.bodies
                self.bodies_lbl.grid()
            
            # Check if carrier is in a system that requires Tritium restock
            self.check_fleet_carrier_restock_warning()
            
            if self.galaxy and self.pleaserefuel:
                self.refuel_lbl['text'] = self.refuellbl_txt
                self.refuel_lbl.grid()

    def update_gui(self):
        """Update the GUI based on current state"""
        if len(self.route) > 0:
            self._update_widget_visibility('route')
            # Ensure waypoint button text is updated (especially important for Road to Riches)
            # This handles cases where next_stop might have been updated but button text wasn't refreshed
            if hasattr(self, 'waypoint_btn') and hasattr(self, 'next_stop') and hasattr(self, 'next_wp_label'):
                try:
                    # Use config() instead of direct assignment for more reliable updates
                    button_text = self.next_wp_label + '\n' + (self.next_stop if self.next_stop else "")
                    self.waypoint_btn.config(text=button_text)
                    self.waypoint_btn.update_idletasks()
                except Exception:
                    pass  # Silently fail if button doesn't exist yet
        else:
            self._update_widget_visibility('empty')

    def show_error(self, error):
        self.error_txt.set(error)
        self.error_lbl.grid()

    def hide_error(self):
        self.error_lbl.grid_remove()

    def enable_plot_gui(self, enable):
        if enable:
            self.source_ac.config(state=tk.NORMAL)
            self.source_ac.update_idletasks()
            self.dest_ac.config(state=tk.NORMAL)
            self.dest_ac.update_idletasks()
            self.efficiency_slider.config(state=tk.NORMAL)
            self.efficiency_slider.update_idletasks()
            self.range_entry.config(state=tk.NORMAL)
            self.range_entry.update_idletasks()
            self.plot_route_btn.config(state=tk.NORMAL, text=plugin_tl("Calculate"))  # LANG: Button text when ready to calculate
            self.plot_route_btn.update_idletasks()
            self.cancel_plot.config(state=tk.NORMAL)
            self.cancel_plot.update_idletasks()
            # supercharge_cb is a Frame containing Canvas and Label - re-bind events to enable interaction
            if hasattr(self, 'supercharge_toggle_canvas'):
                self.supercharge_toggle_canvas.bind("<Button-1>", self._toggle_supercharge)
            if hasattr(self, 'supercharge_label'):
                self.supercharge_label.bind("<Button-1>", self._toggle_supercharge)
        else:
            self.source_ac.config(state=tk.DISABLED)
            self.source_ac.update_idletasks()
            self.dest_ac.config(state=tk.DISABLED)
            self.dest_ac.update_idletasks()
            self.efficiency_slider.config(state=tk.DISABLED)
            self.efficiency_slider.update_idletasks()
            self.range_entry.config(state=tk.DISABLED)
            self.range_entry.update_idletasks()
            self.plot_route_btn.config(state=tk.DISABLED, text=plugin_tl("Computing..."))  # LANG: Button text during route calculation
            self.plot_route_btn.update_idletasks()
            self.cancel_plot.config(state=tk.DISABLED)
            self.cancel_plot.update_idletasks()
            # supercharge_cb is a Frame containing Canvas and Label - disable interaction by unbinding events
            if hasattr(self, 'supercharge_toggle_canvas'):
                # Unbind click events to disable interaction during calculation
                self.supercharge_toggle_canvas.unbind("<Button-1>")
            if hasattr(self, 'supercharge_label'):
                self.supercharge_label.unbind("<Button-1>")

    #   -- END GUI part --


    def open_last_route(self):
        try:
            has_headers = False
            with open(self.save_route_path, 'r', encoding='utf-8-sig', newline='') as csvfile:
                # Check if the file has a header for compatibility with previous versions
                dict_route_reader = csv.DictReader(csvfile)
                if dict_route_reader.fieldnames and dict_route_reader.fieldnames[0] == self.system_header:
                    has_headers = True

            if has_headers:
                # Use plot_csv to properly load the route with all columns
                self.plot_csv(self.save_route_path, clear_previous_route=False)
                
                # Load offset
                try:
                    with open(self.offset_file_path, 'r') as offset_fh:
                        self.offset = int(offset_fh.readline())
                except (IOError, OSError, ValueError):
                    self.offset = 0
                
                # Calculate jumps_left from current offset
                self.jumps_left = 0
                for i in range(self.offset, len(self.route)):
                    row = self.route[i]
                    if len(row) > 1 and row[1] not in [None, "", []]:
                        if not self.galaxy:  # galaxy type doesn't have a jumps column
                            try:
                                self.jumps_left += int(row[1])
                            except (ValueError, TypeError):
                                pass  # Skip rows with non-numeric jumps values
                        else:
                            self.jumps_left += 1
                
                # Set next waypoint
                if self.route and len(self.route) > 0:
                    self.next_stop = self.route[self.offset][0]
                    self.update_bodies_text()
                    self.compute_distances()
                    self.copy_waypoint()
                    
                    # Explicitly update GUI to show route navigation
                    self.update_gui()
                    # Force GUI refresh to ensure all widgets are visible
                    if hasattr(self, 'parent'):
                        self.parent.update_idletasks()
            else:
                # Old format without headers - legacy support
                with open(self.save_route_path, 'r', newline='') as csvfile:
                    route_reader = csv.reader(csvfile)
                    for row in route_reader:
                        if row not in (None, "", []):
                            self.route.append(row)
                
                # Load offset
                try:
                    with open(self.offset_file_path, 'r') as offset_fh:
                        self.offset = int(offset_fh.readline())
                except (IOError, OSError, ValueError):
                    self.offset = 0
                
                # Calculate jumps_left
                self.jumps_left = 0
                for i in range(self.offset, len(self.route)):
                    row = self.route[i]
                    if len(row) > 1 and row[1] not in [None, "", []]:
                        if not self.galaxy:
                            try:
                                self.jumps_left += int(row[1])
                            except (ValueError, TypeError):
                                pass
                        else:
                            self.jumps_left += 1
                
                if self.route and len(self.route) > 0:
                    self.next_stop = self.route[self.offset][0]
                    self.update_bodies_text()
                    self.compute_distances()
                    self.copy_waypoint()
                    self.update_gui()

        except IOError:
            logger.debug("No previously saved route")
        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)

    def copy_waypoint(self):
        if sys.platform == "linux":
            cmd = (os.getenv("EDMC_GALAXYGPS_XCLIP") or "xclip -selection c").split()
            try:
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                p.communicate(input=self.next_stop.encode('utf-8'), timeout=2)
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug("Linux clipboard failed: %s", e)
            return
        if self.parent:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(self.next_stop)
            self.parent.update()

    def goto_next_waypoint(self):
        # allow manual navigation even if offset wasn't set by journal events yet
        if len(self.route) == 0:
            return

        if not hasattr(self, "offset") or self.offset is None:
            self.offset = 0

        # Ensure offset is valid before proceeding
        if self.offset < 0:
            self.offset = 0
        if self.offset >= len(self.route):
            self.offset = len(self.route) - 1

        # For Road to Riches, we skip to next different system, so we can't just check offset < len - 1
        # Instead, check if we're not already at the last system
        if self.offset < len(self.route) - 1:
            self.update_route(1)

    def goto_prev_waypoint(self):
        # allow manual navigation even if offset wasn't set by journal events yet
        if len(self.route) == 0:
            return

        if not hasattr(self, "offset") or self.offset is None:
            self.offset = 0

        # Ensure offset is valid before proceeding
        if self.offset < 0:
            self.offset = 0
        if self.offset >= len(self.route):
            self.offset = len(self.route) - 1

        # For Road to Riches, we skip to previous different system, so we can't just check offset > 0
        # Instead, check if we're not already at the first system
        if self.offset > 0:
            self.update_route(-1)

    def compute_distances(self):
        """Compute LY from prev, to next, and total remaining.

        Correct semantics:
          - Distance To Arrival (if present) is stored on the target row:
              route[i][2] == distance from route[i-1] -> route[i]
          - Distance Remaining (if present) is stored on the current row as route[i][3].
        This function handles rows that may or may not have the distance columns.
        """
        
        # Reset
        self.dist_prev = ""
        self.dist_next = ""
        self.dist_remaining = ""
        self.fuel_used = ""
        self.fuel_remaining = ""

        if not (0 <= self.offset < len(self.route)):
            return

        def safe_flt(x):
            """Convert to float, rounding UP to nearest hundredth (2 decimal places)"""
            try:
                val = float(x)
                # Round UP to nearest hundredth: multiply by 100, ceil, divide by 100
                return math.ceil(val * 100) / 100
            except Exception:
                return None

        cur = self.route[self.offset]
        
        # Extract Fuel Remaining from current waypoint for galaxy routes (index 4)
        if self.galaxy and len(cur) >= 5:
            fuel_remaining_val = cur[4]
            if fuel_remaining_val and fuel_remaining_val.strip():
                self.fuel_remaining = fuel_remaining_val
            else:
                self.fuel_remaining = ""
        else:
            self.fuel_remaining = ""

        # --- Special handling for neutron routes with per-leg jumps ---
        if self.neutron:
            # For neutron routes, internal format is: [System Name, Distance To Arrival, Distance Remaining, Jumps]
            # cur[1] = Distance To Arrival
            # cur[2] = Distance Remaining
            # cur[3] = Jumps (jumps TO REACH that waypoint)
            cur_jumps = safe_flt(cur[3]) if len(cur) >= 4 else None
            
            # "Number of Jumps" = jumps to reach this waypoint (read directly from current row)
            if cur_jumps is not None:
                if cur_jumps == 0:
                    # Starting point
                    self.dist_prev = plugin_tl("Start of the journey")
                elif self.offset >= len(self.route) - 1:
                    # Check if Distance Remaining (column 2) is 0 to show Finished
                    dist_remaining_val = safe_flt(cur[2]) if len(cur) >= 3 else None
                    if dist_remaining_val is not None and dist_remaining_val == 0:
                        self.dist_prev = plugin_tl("Finished")
                    else:
                        self.dist_prev = f"{plugin_tl('Number of Jumps')}: {cur_jumps:.2f}"
                else:
                    self.dist_prev = f"Number of Jumps: {cur_jumps:.2f}"
            else:
                self.dist_prev = ""
            
            # "Next waypoint jumps" = jumps to reach next waypoint (read from next row)
            if self.offset < len(self.route) - 1:
                nxt = self.route[self.offset + 1]
                next_jumps = safe_flt(nxt[3]) if len(nxt) >= 4 else None
                if next_jumps is not None and next_jumps > 0:
                    self.dist_next = f"{plugin_tl('Next waypoint jumps')}: {next_jumps:.2f}"
                else:
                    # Check if we're at the end (Distance Remaining = 0)
                    dist_remaining_val = safe_flt(nxt[2]) if len(nxt) >= 3 else None
                    if dist_remaining_val is not None and dist_remaining_val == 0:
                        self.dist_next = plugin_tl("Finished")
                    else:
                        self.dist_next = ""
            else:
                self.dist_next = plugin_tl("Finished")
            
            # Skip the normal computation and jump to distance remaining calculation
            # (which is handled at the end of this function)
            self.fuel_used = ""  # Neutron routes don't have fuel used
        else:
            # Normal (non-neutron) route handling follows below
            pass

        # --- LY from previous / Number of Jumps (current waypoint) ---
        # Get the jump count for the system shown in "Next Waypoint" (self.next_stop)
        # This ensures the jump count matches the displayed waypoint system
        
        if not self.neutron:
            # Determine if we're at the start of the journey
            # Show "Start of the journey" if:
            # 1. The next waypoint system (self.next_stop) is the first system in the route
            # 2. AND current EDMC system doesn't match that first system
            at_start = False
            first_route_system = self._get_system_name_at_index(0)
            
            # Check if the waypoint we're showing (next_stop) is the first system in the route
            if self.next_stop and first_route_system and self.next_stop.lower() == first_route_system.lower():
                # We're showing the first system - check if we need to travel there
                current_system = None
                if self.fleetcarrier:
                    if self.selected_carrier_callsign and self.fleet_carrier_manager:
                        carrier = self.fleet_carrier_manager.get_carrier(self.selected_carrier_callsign)
                        if carrier:
                            current_system = carrier.get('current_system', '')
                else:
                    current_system = monitor.state.get('SystemName')
                
                # Show "Start of the journey" unless we're already at the first system
                if current_system and first_route_system:
                    # If systems match, we're already at the first waypoint - show jumps instead
                    at_start = current_system.lower() != first_route_system.lower()
                else:
                    # If we don't have system info, default to showing "Start of the journey"
                    at_start = True
            
            # Find the jump count for the current waypoint system (shown in next_stop)
            jump_count = None
            
            # For Fleet Carrier routes, read distance from index 1
            if self.fleetcarrier and len(cur) >= 2:
                pv = safe_flt(cur[1])
                if pv is not None:
                    self.dist_prev = f"Jump LY: {pv:.2f}"
                    jump_count = -1  # Flag to skip jump count display
            elif len(cur) >= 3:
                pv = safe_flt(cur[2])
                if pv is not None:
                    self.dist_prev = f"Jump LY: {pv:.2f}"
                    jump_count = -1  # Flag to skip jump count display
                else:
                    # Get jumps from current row or look backward for Road to Riches
                    jump_count = safe_flt(cur[1])
                    # For Road to Riches: if jump_count is 0 or None, look backward
                    # (0 means body row, None means missing data)
                    if self.roadtoriches and (jump_count is None or jump_count == 0) and self.offset > 0:
                        # Look backward to find the first non-zero jump (the system's jump count)
                        for idx in range(self.offset - 1, -1, -1):
                            prev_row = self.route[idx]
                            if len(prev_row) >= 2:
                                prev_jump = safe_flt(prev_row[1])
                                if prev_jump is not None and prev_jump > 0:
                                    jump_count = prev_jump
                                    break
                    # For non-Road to Riches: if jump_count is 0, look backward
                    elif not self.roadtoriches and jump_count == 0 and self.offset > 0:
                        for idx in range(self.offset - 1, -1, -1):
                            prev_row = self.route[idx]
                            if len(prev_row) >= 2:
                                prev_jump = safe_flt(prev_row[1])
                                if prev_jump is not None and prev_jump > 0:
                                    jump_count = prev_jump
                                    break
            else:
                # no explicit distance columns — try jumps from current row or look backward
                jump_count = safe_flt(cur[1]) if len(cur) >= 2 else None
                # For Road to Riches: if jump_count is 0 or None, look backward
                if self.roadtoriches and (jump_count is None or jump_count == 0) and self.offset > 0:
                    # Look backward to find the first non-zero jump (the system's jump count)
                    for idx in range(self.offset - 1, -1, -1):
                        prev_row = self.route[idx]
                        if len(prev_row) >= 2:
                            prev_jump = safe_flt(prev_row[1])
                            if prev_jump is not None and prev_jump > 0:
                                jump_count = prev_jump
                                break
                # For non-Road to Riches: if jump_count is 0, look backward
                elif not self.roadtoriches and jump_count == 0 and self.offset > 0:
                    for idx in range(self.offset - 1, -1, -1):
                        prev_row = self.route[idx]
                        if len(prev_row) >= 2:
                            prev_jump = safe_flt(prev_row[1])
                            if prev_jump is not None and prev_jump > 0:
                                jump_count = prev_jump
                                break
            
            # Display jump count or status
            
            # Check at_start FIRST before checking jump_count
            # At offset 0, show "Start of the journey" unless we're already at the first system
            if at_start:
                self.dist_prev = plugin_tl("Start of the journey")
            elif jump_count == -1:
                pass  # Already set dist_prev with LY
            elif jump_count is not None and jump_count > 0:
                if self.offset >= len(self.route) - 1:
                    self.dist_prev = plugin_tl("Finished")
                else:
                    self.dist_prev = f"{plugin_tl('Number of Jumps')}: {jump_count:.2f}"
            else:
                # No valid jump count found
                if self.offset >= len(self.route) - 1:
                    self.dist_prev = plugin_tl("Finished")
                else:
                    # No jump data available - leave empty
                    self.dist_prev = ""

            # --- LY to next / Next waypoint jumps ---
            # For galaxy routes: show Distance Remaining from next waypoint
            # For other routes: skip rows with 0 jumps to find the next actual system jump (for Road to Riches)
            if self.offset < len(self.route) - 1:
                next_jump_idx = None  # Initialize for non-galaxy routes
                
                # For galaxy routes, use the next row's Distance Remaining (index 3)
                if self.galaxy:
                    nxt = self.route[self.offset + 1]
                    if len(nxt) >= 4:
                        dist_remaining_val = safe_flt(nxt[3])
                        if dist_remaining_val is not None:
                            if dist_remaining_val == 0:
                                self.dist_next = plugin_tl("Finished")
                            else:
                                self.dist_next = f"{plugin_tl('Distance Remaining')}: {dist_remaining_val:.2f}"
                        else:
                            self.dist_next = ""
                    else:
                        self.dist_next = ""
                else:
                    # For non-galaxy routes: Find next row with non-zero jumps (for Road to Riches)
                    # For fleet carrier routes: Just use the next row directly
                    if self.fleetcarrier:
                        # Fleet carrier routes: Use next row directly
                        # Format: [System Name, Distance, Distance Remaining, Tritium in tank, Tritium in market, Fuel Used, Icy Ring, Pristine, Restock Tritium]
                        nxt = self.route[self.offset + 1]
                        if len(nxt) >= 2:
                            # Distance is at index 1 for fleet carrier routes
                            nv = safe_flt(nxt[1])
                            if nv is not None and nv > 0:
                                self.dist_next = f"{plugin_tl('Next jump LY')}: {nv:.2f}"
                            else:
                                self.dist_next = plugin_tl("Finished")
                        else:
                            self.dist_next = plugin_tl("Finished")
                        next_jump_idx = self.offset + 1
                    else:
                        # For other non-galaxy routes: Find next row with non-zero jumps (for Road to Riches)
                        for idx in range(self.offset + 1, len(self.route)):
                            nxt = self.route[idx]
                            # Check if this row has a non-zero jump value
                            if len(nxt) >= 2:
                                jump_val = safe_flt(nxt[1])
                                if jump_val is not None and jump_val > 0:
                                    next_jump_idx = idx
                                    break
                        
                        if next_jump_idx is not None:
                            nxt = self.route[next_jump_idx]
                            # prefer distance_to_arrival on the NEXT row (distance from current -> next)
                            if len(nxt) >= 3:
                                nv = safe_flt(nxt[2])
                                if nv is not None:
                                    self.dist_next = f"{plugin_tl('Next jump LY')}: {nv:.2f}"
                                else:
                                    nv2 = safe_flt(nxt[1])
                                    if nv2 is not None and nv2 > 0:
                                        self.dist_next = f"{plugin_tl('Next waypoint jumps')}: {nv2:.2f}"
                                    else:
                                        self.dist_next = plugin_tl("Finished")
                            else:
                                nv2 = safe_flt(nxt[1])
                                if nv2 is not None and nv2 > 0:
                                    self.dist_next = f"{plugin_tl('Next waypoint jumps')}: {nv2:.2f}"
                                else:
                                    self.dist_next = plugin_tl("Finished")
                        else:
                            # No more non-zero jumps found - we're finished
                            self.dist_next = plugin_tl("Finished")
                            self.fuel_used = ""
                
                # Extract Fuel Used from waypoint
                if next_jump_idx is not None or self.galaxy or self.fleetcarrier:
                    if self.galaxy:
                        # For galaxy routes, use the next row directly
                        nxt = self.route[self.offset + 1] if self.offset < len(self.route) - 1 else None
                    elif self.fleetcarrier:
                        # For fleet carrier routes, use the CURRENT row
                        nxt = cur
                    else:
                        # For other routes, use the next_jump_idx
                        nxt = self.route[next_jump_idx] if next_jump_idx is not None else None
                    
                    if nxt:
                        # Extract Fuel Used from waypoint if available
                        # For galaxy routes with has_fuel_used: [System, Refuel, Dist, Dist Rem, Fuel Left, Fuel Used, ...]
                        #   Fuel Left is at index 4, Fuel Used is at index 5 (from NEXT waypoint)
                        # For fleet carrier routes with has_fuel_used: [System Name, Distance, Distance Remaining, Tritium in tank, Tritium in market, Fuel Used, Icy Ring, Pristine, Restock Tritium]
                        #   Fuel Used is at index 5 (from CURRENT waypoint via nxt=cur)
                        # For generic routes with has_fuel_used: [System, Jumps, Fuel Used, ...]
                        #   Fuel Used is at index 2
                        if self.has_fuel_used:
                            fuel_used_value = None
                            if self.galaxy and len(nxt) > 5:
                                # Galaxy route: Fuel Used is at index 5
                                fuel_used_value = nxt[5] if nxt[5] else None
                            elif self.fleetcarrier and len(nxt) > 5:
                                # Fleet carrier route: Fuel Used is at index 5
                                fuel_used_value = nxt[5] if nxt[5] else None
                            elif len(nxt) > 2:
                                # Generic route: Fuel Used might be at index 2 (after System, Jumps)
                                fuel_used_value = nxt[2] if nxt[2] else None
                            
                            if fuel_used_value and fuel_used_value.strip():
                                # Round Fuel Used UP to nearest hundredth (2 decimal places) like distances
                                try:
                                    val = float(fuel_used_value.strip())
                                    rounded_val = math.ceil(val * 100) / 100
                                    self.fuel_used = f"{rounded_val:.2f}"
                                except (ValueError, TypeError):
                                    # If not a number, use as-is
                                    self.fuel_used = fuel_used_value.strip()
                            else:
                                self.fuel_used = ""
                        else:
                            self.fuel_used = ""
                    else:
                        self.fuel_used = ""
            else:
                # At the last row - finished
                self.dist_next = plugin_tl("Finished")
                # For galaxy routes, still show fuel used from current row at last waypoint
                if self.galaxy and self.has_fuel_used:
                    logger.debug(f"[compute_distances] At last row, galaxy route with fuel_used column. cur length: {len(cur)}")
                    if len(cur) > 5:
                        fuel_used_value = cur[5] if cur[5] else None
                        logger.debug(f"[compute_distances] fuel_used_value from cur[5]: {fuel_used_value}")
                        if fuel_used_value and fuel_used_value.strip():
                            try:
                                val = float(fuel_used_value.strip())
                                rounded_val = math.ceil(val * 100) / 100
                                self.fuel_used = f"{rounded_val:.2f}"
                                logger.debug(f"[compute_distances] Set fuel_used to: {self.fuel_used}")
                            except (ValueError, TypeError):
                                self.fuel_used = fuel_used_value.strip()
                                logger.debug(f"[compute_distances] Set fuel_used (non-float) to: {self.fuel_used}")
                        else:
                            self.fuel_used = ""
                            logger.debug(f"[compute_distances] fuel_used_value was empty/None, setting fuel_used to empty")
                    else:
                        self.fuel_used = ""
                        logger.debug(f"[compute_distances] cur length {len(cur)} <= 5, setting fuel_used to empty")
                # For fleet carrier routes, also show fuel used from current row at last waypoint
                elif self.fleetcarrier and self.has_fuel_used:
                    logger.debug(f"[compute_distances] At last row, fleet carrier route with fuel_used column. cur length: {len(cur)}")
                    # Fleet carrier routes have fuel used at index 5
                    if len(cur) > 5:
                        fuel_used_value = cur[5] if cur[5] else None
                        logger.debug(f"[compute_distances] fuel_used_value from cur[5]: {fuel_used_value}")
                        if fuel_used_value and fuel_used_value.strip():
                            try:
                                val = float(fuel_used_value.strip())
                                rounded_val = math.ceil(val * 100) / 100
                                self.fuel_used = f"{rounded_val:.2f}"
                                logger.debug(f"[compute_distances] Set fuel_used to: {self.fuel_used}")
                            except (ValueError, TypeError):
                                self.fuel_used = fuel_used_value.strip()
                                logger.debug(f"[compute_distances] Set fuel_used (non-float) to: {self.fuel_used}")
                        else:
                            self.fuel_used = ""
                            logger.debug(f"[compute_distances] fuel_used_value was empty/None, setting fuel_used to empty")
                    else:
                        self.fuel_used = ""
                        logger.debug(f"[compute_distances] cur length {len(cur)} <= 5, setting fuel_used to empty")
                else:
                    self.fuel_used = ""
                    if self.galaxy:
                        logger.debug(f"[compute_distances] Galaxy route but has_fuel_used={self.has_fuel_used}, setting fuel_used to empty")
                    elif self.fleetcarrier:
                        logger.debug(f"[compute_distances] Fleet carrier route but has_fuel_used={self.has_fuel_used}, setting fuel_used to empty")
            # End of non-neutron route handling

        # --- Total remaining ---
        # Check if the route has a "Jumps" column
        has_jumps_column = any(
            fieldname.lower() == 'jumps' 
            for fieldname in self.route_fieldnames
        ) if self.route_fieldnames else False
        
        # If no "Jumps" column, use fallback: count remaining rows (for fleet carrier routes, etc.)
        if not has_jumps_column:
            # Check if we're at the last waypoint
            if self.offset >= len(self.route) - 1:
                self.dist_remaining = plugin_tl("Finished")
            else:
                # Count remaining rows after current position (each row = 1 jump)
                remaining_rows = len(self.route) - self.offset - 1
                if remaining_rows > 0:
                    self.dist_remaining = f"{plugin_tl('Remaining jumps afterwards')}: {remaining_rows}"
                else:
                    self.dist_remaining = plugin_tl("Finished")
            return
        
        # For neutron routes, the "Jumps" column contains jumps TO REACH each waypoint
        # Internal format: [System Name, Distance To Arrival, Distance Remaining, Jumps]
        # Check Distance Remaining column (index 2) first to see if we're finished
        if self.neutron:
            # Check if Distance Remaining = 0 (we're at the destination)
            if len(cur) >= 3:
                dist_remaining_val = safe_flt(cur[2])
                if dist_remaining_val is not None and dist_remaining_val == 0:
                    self.dist_remaining = plugin_tl("Finished")
                    return
            
            # Not finished yet - sum all remaining jump values from the next row onwards
            # Jumps are now at index 3
            s = 0.0
            for r in self.route[self.offset + 1:]:
                if len(r) >= 4:
                    v = safe_flt(r[3])
                    if v is not None:
                        s += v
            
            if s > 0:
                self.dist_remaining = f"{plugin_tl('Remaining jumps afterwards')}: {s:.2f}"
            else:
                self.dist_remaining = ""
            return
        
        # For non-neutron routes: calculate by summing or using Distance Remaining column
        # Prefer exact Distance Remaining at current row (index 3)
        total_rem = None
        if len(cur) >= 4:
            total_rem = safe_flt(cur[3])

        if total_rem is None:
            # Try summing distance_to_arrival of subsequent rows (index 2)
            total = 0.0
            ok = True
            for r in self.route[self.offset + 1:]:
                if len(r) >= 3:
                    v = safe_flt(r[2])
                    if v is None:
                        ok = False
                        break
                    total += v
                else:
                    ok = False
                    break
            if ok:
                total_rem = total

        if total_rem is not None:
            self.dist_remaining = f"{plugin_tl('Remaining jumps afterwards')}: {total_rem:.2f}"
        else:
            # final fallback: sum numeric jumps (index 1) as approximate
            s = 0.0
            ok = True
            for r in self.route[self.offset + 1:]:
                v = safe_flt(r[1])
                if v is None:
                    ok = False
                    break
                s += v
            if ok and s > 0:
                self.dist_remaining = f"{plugin_tl('Remaining jumps afterwards')}: {s:.2f}"
            else:
                self.dist_remaining = ""

    def find_current_waypoint_in_route(self):
        """
        Find the appropriate waypoint index based on current system location.
        For fleet carrier routes: Uses the selected fleet carrier's location.
        For non-fleet carrier routes: Uses the player's current system.
        Searches through the route to find if the current location matches any waypoint system,
        and returns the index of the next waypoint to visit.
        
        Returns:
            int: Index of the next waypoint (0 if at start, or last index if at end)
        """
        if not self.route or len(self.route) == 0:
            return 0
        
        # Determine which system to check based on route type
        current_system = None
        if self.fleetcarrier:
            # For fleet carrier routes, use the selected fleet carrier's location
            if self.selected_carrier_callsign and self.fleet_carrier_manager:
                carrier = self.fleet_carrier_manager.get_carrier(self.selected_carrier_callsign)
                if carrier:
                    current_system = carrier.get('current_system', '')
            # If no carrier selected or no carrier data, try to get the most recent carrier
            if not current_system:
                carriers = self.get_all_fleet_carriers()
                if carriers:
                    # Get the most recently updated carrier
                    sorted_carriers = sorted(
                        carriers,
                        key=lambda x: x.get('last_updated', ''),
                        reverse=True
                    )
                    carrier = sorted_carriers[0]
                    current_system = carrier.get('current_system', '') if carrier else None
        else:
            # For non-fleet carrier routes, use the player's current system
            current_system = monitor.state.get('SystemName')
        
        if not current_system:
            # No current system info, start from beginning
            return 0
        
        current_system_lower = current_system.lower()
        
        # Search through route from start to find the best match
        # Strategy: Find the last waypoint we've already visited
        # (i.e., where the system matches), then advance to the next one
        found_index = -1
        
        for idx, waypoint in enumerate(self.route):
            # Use helper method to get system name (handles empty names for Road to Riches)
            waypoint_system = self._get_system_name_at_index(idx)
            if waypoint_system and waypoint_system.lower() == current_system_lower:
                # Found a match - we're at this waypoint
                found_index = idx
        
        if found_index >= 0:
            # We're at a waypoint - advance to the next one with a different system name
            # Get the current system name to compare against
            current_waypoint_system = self._get_system_name_at_index(found_index)
            next_index = found_index + 1
            
            # Skip rows with the same system name (for Road to Riches where system names don't repeat)
            while next_index < len(self.route):
                next_system_name = self._get_system_name_at_index(next_index)
                # If we found a different system name (or reached the end), use it
                if next_system_name != current_waypoint_system:
                    break
                next_index += 1
            
            if next_index >= len(self.route):
                # We're at or past the last waypoint, stay at the last one
                next_index = len(self.route) - 1
            
            # Update jumps_left to account for skipping waypoints we've already passed
            for idx in range(next_index):
                if idx < len(self.route) and len(self.route[idx]) > 1:
                    try:
                        if self.fleetcarrier:
                            # Fleet carrier routes: each row is 1 jump
                            self.jumps_left -= 1
                        elif self.neutron:
                            # Neutron routes: jumps are at index 3
                            if len(self.route[idx]) > 3 and self.route[idx][3] not in [None, "", []]:
                                self.jumps_left -= int(self.route[idx][3])
                        elif self.galaxy:
                            # Galaxy routes: each row is 1 jump
                            self.jumps_left -= 1
                        else:
                            # Generic routes: jumps are at index 1
                            if len(self.route[idx]) > 1 and self.route[idx][1] not in [None, "", []]:
                                self.jumps_left -= int(self.route[idx][1])
                    except (ValueError, TypeError):
                        pass
            
            return next_index
        else:
            # Not at any waypoint - check if we're between waypoints
            # For now, default to starting from the beginning
            # Could enhance this later to check distance to nearest waypoint
            return 0
    
    def _get_system_name_at_index(self, idx):
        """
        Get the system name at a given route index, handling empty system names for Road to Riches.
        For Road to Riches, if system name is empty, use the previous non-empty system name.
        """
        if idx < 0 or idx >= len(self.route):
            return None
        
        system_name = self.route[idx][0] if len(self.route[idx]) > 0 else ""
        
        # For Road to Riches, if system name is empty, look backwards for the last non-empty name
        if self.roadtoriches and (not system_name or system_name.strip() == ""):
            # Look backwards to find the last non-empty system name
            for prev_idx in range(idx - 1, -1, -1):
                prev_system = self.route[prev_idx][0] if len(self.route[prev_idx]) > 0 else ""
                if prev_system and prev_system.strip():
                    return prev_system.strip()
            return None
        
        return system_name.strip() if system_name else None

    def update_route(self, direction=1):
        # Guard: no route -> nothing to do
        if len(self.route) == 0:
            self.next_stop = "No route planned"
            self.update_gui()
            return

        # Ensure offset exists and is within bounds
        if not hasattr(self, "offset") or self.offset is None:
            self.offset = 0

        # clamp offset into valid range before operating
        # CRITICAL: Ensure offset is always valid, especially after window operations
        if self.offset < 0:
            logger.warning(f'[update_route] Offset was negative ({self.offset}), correcting to 0')
            self.offset = 0
        if self.offset >= len(self.route):
            logger.warning(f'[update_route] Offset ({self.offset}) >= route length ({len(self.route)}), correcting')
            self.offset = len(self.route) - 1
        
        # Additional safety check: if route is empty after validation, reset
        if len(self.route) == 0:
            self.next_stop = "No route planned"
            self.update_gui()
            return

        # Get current system name (handling empty names for Road to Riches)
        current_system_name = self._get_system_name_at_index(self.offset)
        # Handle None case - if we can't get system name, use empty string for comparison
        if current_system_name is None:
            current_system_name = ""

        try:
            if direction > 0:
                # Moving forward: skip to next row with different system name
                # First, subtract jumps for current offset (if present)
                if self.fleetcarrier:
                    # Fleet carrier routes: each row is 1 jump
                    self.jumps_left -= 1
                elif self.neutron:
                    # Neutron routes: jumps are at index 3
                    if len(self.route[self.offset]) > 3 and self.route[self.offset][3] not in [None, "", []]:
                        self.jumps_left -= int(self.route[self.offset][3])
                elif self.galaxy:
                    # Galaxy routes: each row is 1 jump
                    self.jumps_left -= 1
                else:
                    # Generic routes: jumps are at index 1
                    if len(self.route[self.offset]) > 1 and self.route[self.offset][1] not in [None, "", []]:
                        self.jumps_left -= int(self.route[self.offset][1])
                
                # Find next row with different system name
                new_offset = self.offset
                while new_offset < len(self.route) - 1:
                    new_offset += 1
                    next_system_name = self._get_system_name_at_index(new_offset)
                    # Handle None case
                    if next_system_name is None:
                        next_system_name = ""
                    # If we found a different system name (or reached the end), use it
                    if next_system_name != current_system_name:
                        self.offset = new_offset
                        break
                else:
                    # Reached end of route without finding different system
                    self.offset = len(self.route) - 1
            else:
                # Moving backward: skip to previous row with different system name
                if self.offset > 0:
                    # Find previous row with different system name
                    new_offset = self.offset
                    while new_offset > 0:
                        new_offset -= 1
                        prev_system_name = self._get_system_name_at_index(new_offset)
                        # Handle None case
                        if prev_system_name is None:
                            prev_system_name = ""
                        # If we found a different system name, use it
                        if prev_system_name != current_system_name:
                            self.offset = new_offset
                            # Add jumps for the new offset (if present)
                            if self.fleetcarrier:
                                # Fleet carrier routes: each row is 1 jump
                                self.jumps_left += 1
                            elif self.neutron:
                                # Neutron routes: jumps are at index 3
                                if len(self.route[self.offset]) > 3 and self.route[self.offset][3] not in [None, "", []]:
                                    self.jumps_left += int(self.route[self.offset][3])
                            elif self.galaxy:
                                # Galaxy routes: each row is 1 jump
                                self.jumps_left += 1
                            else:
                                # Generic routes: jumps are at index 1
                                if len(self.route[self.offset]) > 1 and self.route[self.offset][1] not in [None, "", []]:
                                    self.jumps_left += int(self.route[self.offset][1])
                            break
                    else:
                        # Reached beginning without finding different system, stay at current
                        pass
        except Exception:
            # If something odd in route contents, try to recover by resetting offset to 0
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)
            self.offset = max(0, min(self.offset, len(self.route) - 1))

        # Now update next_stop and GUI according to new offset
        if self.offset >= len(self.route):
            self.next_stop = "End of the road!"
            self.update_gui()
        else:
            # Get the system name for display (handling empty names for Road to Riches)
            display_system_name = self._get_system_name_at_index(self.offset)
            if display_system_name:
                self.next_stop = display_system_name
            else:
                # Fallback to raw value if we can't determine system name
                # For Road to Riches, if raw value is empty, look backwards for system name
                raw_system = self.route[self.offset][0] if len(self.route[self.offset]) > 0 else ""
                if not raw_system and self.roadtoriches and self.offset > 0:
                    # Look backwards for the last non-empty system name
                    for prev_idx in range(self.offset - 1, -1, -1):
                        prev_system = self.route[prev_idx][0] if len(self.route[prev_idx]) > 0 else ""
                        if prev_system and prev_system.strip():
                            self.next_stop = prev_system.strip()
                            break
                    else:
                        self.next_stop = raw_system if raw_system else ""
                else:
                    self.next_stop = raw_system if raw_system else ""

            try:
                self.update_bodies_text()
            except Exception as e:
                logger.warning(f'[update_route] Exception in update_bodies_text(): {e}', exc_info=True)

            try:
                self.compute_distances()
            except Exception as e:
                logger.warning(f'[update_route] Exception in compute_distances(): {e}', exc_info=True)

            if self.galaxy:
                try:
                    self.pleaserefuel = self.route[self.offset][1] == "Yes"
                except Exception as e:
                    logger.warning(f'[update_route] Exception setting pleaserefuel: {e}', exc_info=True)
            
            # Update fleet carrier restock warning when route changes
            if self.fleetcarrier:
                try:
                    self.check_fleet_carrier_restock_warning()
                except Exception as e:
                    logger.warning(f'[update_route] Exception in check_fleet_carrier_restock_warning(): {e}', exc_info=True)

            # Update GUI (this will update button text)
            try:
                self.update_gui()
            except Exception as e:
                logger.error(f'[update_route] Exception in update_gui(): {e}', exc_info=True)
                raise  # Re-raise to see the full stack trace
            
            # CRITICAL: Explicitly update button text AFTER next_stop is set
            # This is especially important for Road to Riches where system names might be empty
            # Use the same method the window uses to ensure consistency
            # Force update even if window is open (window operations shouldn't block this)
            def update_button_text():
                if hasattr(self, 'waypoint_btn') and hasattr(self, 'next_wp_label'):
                    try:
                        # Verify button widget is still valid (not destroyed)
                        if not hasattr(self.waypoint_btn, 'winfo_exists') or not self.waypoint_btn.winfo_exists():
                            logger.warning('[update_button_text] Button widget does not exist, skipping update')
                            return  # Button was destroyed, can't update
                        
                        # Re-get the system name using the same method the window uses
                        # This ensures button text matches what the window highlights
                        if hasattr(self, '_get_system_name_at_index') and hasattr(self, 'offset') and hasattr(self, 'route'):
                            # Ensure offset is still valid
                            if self.offset >= 0 and self.offset < len(self.route):
                                display_system_name = self._get_system_name_at_index(self.offset)
                                if display_system_name:
                                    current_next_stop = display_system_name
                                else:
                                    current_next_stop = self.next_stop if hasattr(self, 'next_stop') and self.next_stop else ""
                            else:
                                current_next_stop = self.next_stop if hasattr(self, 'next_stop') and self.next_stop else ""
                        else:
                            current_next_stop = self.next_stop if hasattr(self, 'next_stop') and self.next_stop else ""
                        
                        button_text = self.next_wp_label + '\n' + current_next_stop

                        # Update using config() for more reliable updates
                        # Use both config() and direct assignment to ensure it works
                        self.waypoint_btn.config(text=button_text)
                        self.waypoint_btn["text"] = button_text
                        # Force immediate GUI update
                        self.waypoint_btn.update_idletasks()
                        # Also update the parent frame to ensure visibility
                        if hasattr(self, 'frame'):
                            self.frame.update_idletasks()
                        # Force parent window update as well
                        if hasattr(self, 'parent') and self.parent:
                            self.parent.update_idletasks()
                        
                        # Verify the update actually took (log only on mismatch)
                        actual_text = self.waypoint_btn.cget('text')
                        if actual_text != button_text:
                            logger.warning(f'[update_button_text] Button text mismatch! Expected: {button_text[:50]}..., Got: {actual_text[:50]}...')
                    except (tk.TclError, AttributeError) as e:
                        # Button was destroyed or invalid, skip update
                        logger.warning(f'[update_button_text] TclError/AttributeError: {e}', exc_info=False)
                    except Exception as e:
                        logger.warning(f'[update_button_text] Error updating waypoint button text: {e}', exc_info=True)
            
            # Update immediately - use try/except to ensure it always happens
            try:
                update_button_text()
            except Exception as e:
                logger.warning(f'Error in immediate button text update: {e}', exc_info=False)
            
            # Also schedule multiple updates after delays to ensure it sticks
            # This helps if window operations are interfering
            if hasattr(self, 'parent') and self.parent:
                try:
                    self.parent.after(10, update_button_text)
                    self.parent.after(50, update_button_text)
                    self.parent.after(100, update_button_text)
                    self.parent.after(200, update_button_text)
                except Exception:
                    pass
            
            self.copy_waypoint()
            
            # CRITICAL: Validate route and offset after all operations
            # This ensures they remain valid even if window operations interfere
            if hasattr(self, 'route') and hasattr(self, 'offset'):
                if self.offset < 0:
                    self.offset = 0
                if self.offset >= len(self.route):
                    self.offset = len(self.route) - 1 if len(self.route) > 0 else 0
                # Re-validate next_stop after offset validation
                if self.offset < len(self.route):
                    display_system_name = self._get_system_name_at_index(self.offset)
                    if display_system_name:
                        self.next_stop = display_system_name
            
            # Refresh route window if open to update highlighted waypoint
            # Do this after all GUI updates to ensure consistency
            try:
                refresh_route_window_if_open(self)
            except Exception as e:
                logger.warning(f'Error refreshing route window: {e}', exc_info=False)
            
            # Final button text update after all operations complete
            # Use after() to ensure this happens after any window operations
            # Use the same method the window uses to get system name for consistency
            if hasattr(self, 'parent') and hasattr(self, 'waypoint_btn') and hasattr(self, 'next_wp_label'):
                def final_button_update():
                    try:
                        # Verify button widget is still valid (not destroyed)
                        if not hasattr(self.waypoint_btn, 'winfo_exists') or not self.waypoint_btn.winfo_exists():
                            logger.warning('[final_button_update] Button widget does not exist, skipping update')
                            return  # Button was destroyed, can't update
                        
                        # Ensure route and offset are still valid
                        if hasattr(self, 'route') and hasattr(self, 'offset'):
                            if self.offset < 0 or self.offset >= len(self.route):
                                # Offset is invalid, try to recover
                                if len(self.route) > 0:
                                    self.offset = max(0, min(self.offset, len(self.route) - 1))
                                else:
                                    return
                        
                        # Re-get the system name using the same method the window uses
                        if hasattr(self, '_get_system_name_at_index') and hasattr(self, 'offset') and hasattr(self, 'route'):
                            if self.offset >= 0 and self.offset < len(self.route):
                                display_system_name = self._get_system_name_at_index(self.offset)
                                if display_system_name:
                                    current_next_stop = display_system_name
                                else:
                                    current_next_stop = self.next_stop if hasattr(self, 'next_stop') and self.next_stop else ""
                            else:
                                current_next_stop = self.next_stop if hasattr(self, 'next_stop') and self.next_stop else ""
                        else:
                            current_next_stop = self.next_stop if hasattr(self, 'next_stop') and self.next_stop else ""
                        button_text = self.next_wp_label + '\n' + current_next_stop
                        # Use both methods to ensure update
                        self.waypoint_btn.config(text=button_text)
                        self.waypoint_btn["text"] = button_text
                        self.waypoint_btn.update_idletasks()
                        
                        # Verify the update (log only on mismatch)
                        actual_text = self.waypoint_btn.cget('text')
                        if actual_text != button_text:
                            logger.warning(f'[final_button_update] Button text mismatch! Expected: {button_text[:50]}..., Got: {actual_text[:50]}...')
                    except (tk.TclError, AttributeError) as e:
                        # Button was destroyed or invalid, skip update
                        logger.warning(f'[final_button_update] TclError/AttributeError: {e}', exc_info=False)
                    except Exception as e:
                        logger.warning(f'[final_button_update] Error in final button update: {e}', exc_info=True)
                # Schedule multiple updates to ensure it sticks
                # Use longer delays to ensure window creation has completed
                if self.parent:
                    try:
                        self.parent.after(250, final_button_update)  # After window creation likely completes
                        self.parent.after(500, final_button_update)  # Second attempt for safety
                        self.parent.after(1000, final_button_update)  # Final fallback
                    except Exception:
                        pass

        self.save_offset()

    def goto_changelog_page(self):
        changelog_url = 'https://github.com/Fenris159/EDMC_GalaxyGPS/blob/master/CHANGELOG.md#'
        changelog_url += self.spansh_updater.version.replace('.', '')
        webbrowser.open(changelog_url)

    def plot_file(self):
        ftypes = [
            ('All supported files', '*.csv *.txt'),
            ('CSV files', '*.csv'),
            ('Text files', '*.txt'),
        ]
        filename = filedialog.askopenfilename(filetypes = ftypes, initialdir=os.path.expanduser('~'))

        if filename.__len__() > 0:
            try:
                ftype_supported = False
                if filename.endswith(".csv"):
                    ftype_supported = True
                    # Store the original CSV path so we can read all columns later
                    self.original_csv_path = filename
                    self.plot_csv(filename)

                elif filename.endswith(".txt"):
                    ftype_supported = True
                    self.plot_edts(filename)

                if ftype_supported:
                    # Find where we are in the route based on current system location
                    self.offset = self.find_current_waypoint_in_route()
                    
                    self.next_stop = self.route[self.offset][0] if self.route else ""
                    if self.galaxy:
                        self.pleaserefuel = self.route[self.offset][1] == "Yes" if self.route and len(self.route[self.offset]) > 1 else False
                    self.update_bodies_text()
                    self.compute_distances()
                    self.copy_waypoint()
                    self.update_gui()
                    # Check fleet carrier restock warning
                    if self.fleetcarrier and hasattr(self, 'check_fleet_carrier_restock_warning'):
                        self.check_fleet_carrier_restock_warning()
                    # Save route to cache (now preserves all columns via route_full_data)
                    self.save_all_route()
                else:
                    self.show_error("Unsupported file type")
            except Exception:
                logger.warning('!! ' + traceback.format_exc(), exc_info=False)
                self.enable_plot_gui(True)
                self.show_error("(1) An error occured while reading the file.")

    def plot_csv(self, filename, clear_previous_route=True):
        with open(filename, 'r', encoding='utf-8-sig', newline='') as csvfile:
            self.roadtoriches = False
            self.fleetcarrier = False
            self.galaxy = False
            self.neutron = False

            if clear_previous_route:
                self.clear_route(False)
                self.has_fuel_used = False  # Reset flag when clearing route

            route_reader = csv.DictReader(csvfile)
            fieldnames = route_reader.fieldnames if route_reader.fieldnames else []
            
            # Store full CSV data for View Route window (preserve all columns)
            self.route_full_data = []
            self.route_fieldnames = fieldnames  # Preserve original fieldnames for display
            
            # Create case-insensitive fieldname mapping
            fieldname_map = {name.lower(): name for name in fieldnames}
            
            def get_field(row, field_name, default=""):
                """Get field value from row using case-insensitive lookup"""
                key = fieldname_map.get(field_name.lower(), field_name)
                return row.get(key, default)
            
            def has_field(field_name):
                """Check if field exists in header (case-insensitive)"""
                return field_name.lower() in fieldname_map
            
            headerline = ','.join(fieldnames) if fieldnames else ""
            headerline_lower = headerline.lower()

            internalbasicheader1 = "System Name"
            internalbasicheader2 = "System Name,Jumps"
            internalrichesheader = "System Name,Jumps,Body Name,Body Subtype"
            internalfleetcarrierheader_with_distances = "System Name,Distance,Distance Remaining,Tritium in tank,Tritium in market,Fuel Used,Icy Ring,Pristine,Restock Tritium"
            internalfleetcarrierheader = "System Name,Distance,Distance Remaining,Tritium in tank,Tritium in market,Fuel Used,Icy Ring,Pristine,Restock Tritium"
            internalgalaxyheader = "System Name,Refuel"
            neutronimportheader = "System Name,Distance To Arrival,Distance Remaining,Neutron Star,Jumps"
            road2richesimportheader = "System Name,Body Name,Body Subtype,Is Terraformable,Distance To Arrival,Estimated Scan Value,Estimated Mapping Value,Jumps"
            fleetcarrierimportheader = "System Name,Distance,Distance Remaining,Tritium in tank,Tritium in market,Fuel Used,Icy Ring,Pristine,Restock Tritium"
            galaxyimportheader = "System Name,Distance,Distance Remaining,Fuel Left,Fuel Used,Refuel,Neutron Star"

            def get_distance_fields(row):
                dist_to_arrival = get_field(row, "Distance To Arrival", "") or get_field(row, "Distance", "")
                dist_remaining = get_field(row, "Distance Remaining", "")
                
                # Round distance values UP to nearest hundredth (2 decimal places)
                def round_distance(value):
                    if not value or value == "":
                        return ""
                    try:
                        val = float(value)
                        # Round UP to nearest hundredth: multiply by 100, ceil, divide by 100
                        rounded = math.ceil(val * 100) / 100
                        return f"{rounded:.2f}"
                    except (ValueError, TypeError):
                        return value  # Return as-is if not a number
                
                return round_distance(dist_to_arrival), round_distance(dist_remaining)

            # --- neutron import ---
            if headerline_lower == neutronimportheader.lower():
                self.neutron = True  # Flag neutron routes for special cumulative jump handling
                logger.info(f"[plot_csv] Importing neutron route with headers: {fieldnames}")
                for row in route_reader:
                    if row not in (None, "", []):
                        # Store full row data (all columns)
                        full_row_data = {}
                        for field_name in fieldnames:
                            full_row_data[field_name.lower()] = get_field(row, field_name, '')
                        self.route_full_data.append(full_row_data)
                        
                        # Store minimal route data for route planner
                        # Neutron format: [System Name, Distance To Arrival, Distance Remaining, Jumps]
                        dist_to_arrival, dist_remaining = get_distance_fields(row)
                        jumps_value = get_field(row, self.jumps_header, "")
                        route_row = [
                            get_field(row, self.system_header),
                            dist_to_arrival,
                            dist_remaining,
                            jumps_value
                        ]
                        self.route.append(route_row)
                        logger.debug(f"[plot_csv] Neutron row: {route_row}")
                        try:
                            jumps_val = get_field(row, self.jumps_header, "0")
                            self.jumps_left += int(jumps_val)
                        except (ValueError, TypeError):
                            pass

            # --- Check for Road to Riches import ---
            if headerline_lower == road2richesimportheader.lower():
                self.roadtoriches = True
                logger.info(f"[plot_csv] Detected Road to Riches route with headers: {fieldnames}")

            # --- simple internal ---
            if headerline_lower in (internalbasicheader1.lower(), internalbasicheader2.lower()):
                for row in route_reader:
                    if row not in (None, "", []):
                        # Store full row data (all columns)
                        full_row_data = {}
                        for field_name in fieldnames:
                            full_row_data[field_name.lower()] = get_field(row, field_name, '')
                        self.route_full_data.append(full_row_data)
                        
                        # Store minimal route data for route planner
                        self.route.append([
                            get_field(row, self.system_header),
                            get_field(row, self.jumps_header, "")
                        ])
                        try:
                            jumps_val = get_field(row, self.jumps_header, "0")
                            self.jumps_left += int(jumps_val)
                        except (ValueError, TypeError):
                            pass

            # --- internal fleetcarrier WITH distances (load after restart) ---
            elif headerline_lower == internalfleetcarrierheader_with_distances.lower():
                self.fleetcarrier = True
                self.has_fuel_used = has_field('Fuel Used')

                for row in route_reader:
                    if row not in (None, "", []):
                        # Store full row data (all columns)
                        full_row_data = {}
                        for field_name in fieldnames:
                            full_row_data[field_name.lower()] = get_field(row, field_name, '')
                        self.route_full_data.append(full_row_data)
                        
                        # Store minimal route data for route planner
                        # Fleet Carrier format: [System Name, Distance, Distance Remaining, Tritium in tank, Tritium in market, Fuel Used, Icy Ring, Pristine, Restock Tritium]
                        dist_to_arrival, dist_remaining = get_distance_fields(row)
                        
                        route_entry = [
                            get_field(row, self.system_header),                    # 0: System Name
                            dist_to_arrival,                                       # 1: Distance
                            dist_remaining,                                        # 2: Distance Remaining
                            get_field(row, 'Tritium in tank', ''),                # 3: Tritium in tank
                            get_field(row, 'Tritium in market', ''),              # 4: Tritium in market
                        ]
                        
                        # Add Fuel Used if present
                        if self.has_fuel_used:
                            fuel_used_raw = get_field(row, 'Fuel Used', '')
                            if fuel_used_raw:
                                try:
                                    val = float(fuel_used_raw)
                                    rounded_val = math.ceil(val * 100) / 100
                                    route_entry.append(f"{rounded_val:.2f}")       # 5: Fuel Used
                                except (ValueError, TypeError):
                                    route_entry.append(fuel_used_raw)
                            else:
                                route_entry.append('')
                        else:
                            route_entry.append('')  # 5: Fuel Used placeholder
                        
                        route_entry.append(get_field(row, 'Icy Ring', ''))        # 6: Icy Ring
                        route_entry.append(get_field(row, 'Pristine', ''))        # 7: Pristine
                        route_entry.append(get_field(row, self.restocktritium_header, ''))  # 8: Restock Tritium
                        
                        self.route.append(route_entry)
                        # For internal format with distances, each row is 1 jump
                        self.jumps_left += 1

            # --- internal fleetcarrier (legacy, no distances) ---
            elif headerline_lower == internalfleetcarrierheader.lower():
                self.fleetcarrier = True
                self.has_fuel_used = has_field('Fuel Used')

                for row in route_reader:
                    if row not in (None, "", []):
                        # Store full row data (all columns)
                        full_row_data = {}
                        for field_name in fieldnames:
                            full_row_data[field_name.lower()] = get_field(row, field_name, '')
                        self.route_full_data.append(full_row_data)
                        
                        # Store minimal route data for route planner
                        # Fleet Carrier format: [System Name, Distance, Distance Remaining, Tritium in tank, Tritium in market, Fuel Used, Icy Ring, Pristine, Restock Tritium]
                        route_entry = [
                            get_field(row, self.system_header),                    # 0: System Name
                            "",                                                    # 1: Distance (placeholder)
                            "",                                                    # 2: Distance Remaining (placeholder)
                            get_field(row, 'Tritium in tank', ''),                # 3: Tritium in tank
                            get_field(row, 'Tritium in market', ''),              # 4: Tritium in market
                        ]
                        
                        # Add Fuel Used if present
                        if self.has_fuel_used:
                            fuel_used_raw = get_field(row, 'Fuel Used', '')
                            if fuel_used_raw:
                                try:
                                    val = float(fuel_used_raw)
                                    rounded_val = math.ceil(val * 100) / 100
                                    route_entry.append(f"{rounded_val:.2f}")       # 5: Fuel Used
                                except (ValueError, TypeError):
                                    route_entry.append(fuel_used_raw)
                            else:
                                route_entry.append('')
                        else:
                            route_entry.append('')  # 5: Fuel Used placeholder
                        
                        route_entry.append(get_field(row, 'Icy Ring', ''))        # 6: Icy Ring
                        route_entry.append(get_field(row, 'Pristine', ''))        # 7: Pristine
                        route_entry.append(get_field(row, self.restocktritium_header, ''))  # 8: Restock Tritium
                        
                        self.route.append(route_entry)
                        # Legacy format, each row is 1 jump
                        self.jumps_left += 1

            # --- EXTERNAL fleetcarrier import (WITH LY SUPPORT) ---
            elif headerline_lower == fleetcarrierimportheader.lower():
                self.fleetcarrier = True
                self.has_fuel_used = has_field('Fuel Used')

                for row in route_reader:
                    if row not in (None, "", []):
                        # Store full row data (all columns)
                        full_row_data = {}
                        for field_name in fieldnames:
                            field_value = get_field(row, field_name, '')
                            # Round distance values if present
                            if field_name.lower() in ["distance to arrival", "distance remaining", "distance"]:
                                if field_value:
                                    try:
                                        val = float(field_value)
                                        rounded_val = math.ceil(val * 100) / 100
                                        field_value = f"{rounded_val:.2f}"
                                    except (ValueError, TypeError):
                                        pass
                            full_row_data[field_name.lower()] = field_value
                        self.route_full_data.append(full_row_data)
                        
                        # Store minimal route data for route planner
                        # Fleet Carrier format: [System Name, Distance, Distance Remaining, Tritium in tank, Tritium in market, Fuel Used, Icy Ring, Pristine, Restock Tritium]
                        dist_to_arrival, dist_remaining = get_distance_fields(row)

                        route_entry = [
                            get_field(row, self.system_header),                    # 0: System Name
                            dist_to_arrival,                                       # 1: Distance
                            dist_remaining,                                        # 2: Distance Remaining
                            get_field(row, 'Tritium in tank', ''),                # 3: Tritium in tank
                            get_field(row, 'Tritium in market', ''),              # 4: Tritium in market
                        ]
                        
                        # Store Fuel Used if present (round UP to nearest hundredth)
                        if self.has_fuel_used:
                            fuel_used_raw = get_field(row, 'Fuel Used', '')
                            if fuel_used_raw:
                                try:
                                    val = float(fuel_used_raw)
                                    rounded_val = math.ceil(val * 100) / 100
                                    route_entry.append(f"{rounded_val:.2f}")       # 5: Fuel Used
                                except (ValueError, TypeError):
                                    route_entry.append(fuel_used_raw)
                            else:
                                route_entry.append('')
                        else:
                            route_entry.append('')  # 5: Fuel Used placeholder
                        
                        # Store Icy Ring and Pristine if present (for route view window)
                        if has_field('Icy Ring'):
                            route_entry.append(get_field(row, 'Icy Ring', ''))    # 6: Icy Ring
                        else:
                            route_entry.append('')
                        
                        if has_field('Pristine'):
                            route_entry.append(get_field(row, 'Pristine', ''))    # 7: Pristine
                        else:
                            route_entry.append('')
                        
                        route_entry.append(get_field(row, self.restocktritium_header, ''))  # 8: Restock Tritium
                        
                        self.route.append(route_entry)
                        self.jumps_left += 1

            # --- galaxy ---
            elif has_field("Refuel") and has_field(self.system_header):
                self.galaxy = True
                self.has_fuel_used = has_field('Fuel Used')
                has_fuel_left = has_field('Fuel Left')

                for row in route_reader:
                    if row not in (None, "", []):
                        # Store full row data (all columns)
                        full_row_data = {}
                        for field_name in fieldnames:
                            field_value = get_field(row, field_name, '')
                            # Round distance values if present
                            if field_name.lower() in ["distance to arrival", "distance remaining", "distance"]:
                                if field_value:
                                    try:
                                        val = float(field_value)
                                        rounded_val = math.ceil(val * 100) / 100
                                        field_value = f"{rounded_val:.2f}"
                                    except (ValueError, TypeError):
                                        pass
                            full_row_data[field_name.lower()] = field_value
                        self.route_full_data.append(full_row_data)
                        
                        # Store minimal route data for route planner
                        dist_to_arrival, dist_remaining = get_distance_fields(row)

                        route_row = [
                            get_field(row, self.system_header, ""),
                            get_field(row, self.refuel_header, "")
                        ]

                        if dist_to_arrival or dist_remaining:
                            route_row.append(dist_to_arrival)
                            route_row.append(dist_remaining)
                            
                            # Store Fuel Left if present at index 4 (round UP to nearest hundredth)
                            if has_fuel_left:
                                fuel_left_raw = get_field(row, 'Fuel Left', '')
                                if fuel_left_raw:
                                    try:
                                        val = float(fuel_left_raw)
                                        rounded_val = math.ceil(val * 100) / 100
                                        route_row.append(f"{rounded_val:.2f}")
                                    except (ValueError, TypeError):
                                        route_row.append(fuel_left_raw)
                                else:
                                    route_row.append('')
                            else:
                                # No Fuel Left column - add empty placeholder
                                route_row.append("")
                        
                        # Store Fuel Used if present at index 5 (round UP to nearest hundredth)
                        if self.has_fuel_used:
                            fuel_used_raw = get_field(row, 'Fuel Used', '')
                            if fuel_used_raw:
                                try:
                                    val = float(fuel_used_raw)
                                    rounded_val = math.ceil(val * 100) / 100
                                    route_row.append(f"{rounded_val:.2f}")
                                except (ValueError, TypeError):
                                    route_row.append(fuel_used_raw)
                            else:
                                route_row.append('')

                        self.route.append(route_row)
                        self.jumps_left += 1

            else:
                # Generic CSV import - check if it's a fleet carrier route with Icy Ring/Pristine
                has_icy_ring_in_file = has_field('Icy Ring')
                has_pristine_in_file = has_field('Pristine')
                if has_icy_ring_in_file or has_pristine_in_file:
                    self.fleetcarrier = True
                
                # Check if Fuel Used column exists
                self.has_fuel_used = has_field('Fuel Used')
                
                for row in route_reader:
                    if row not in (None, "", []):
                        # Store full row data (all columns) - preserve everything
                        full_row_data = {}
                        for field_name in fieldnames:
                            field_value = get_field(row, field_name, '')
                            # Round distance values if present
                            if field_name.lower() in ["distance to arrival", "distance remaining", "distance"]:
                                if field_value:
                                    try:
                                        val = float(field_value)
                                        rounded_val = math.ceil(val * 100) / 100
                                        field_value = f"{rounded_val:.2f}"
                                    except (ValueError, TypeError):
                                        pass
                            full_row_data[field_name.lower()] = field_value
                        self.route_full_data.append(full_row_data)
                        
                        # Store minimal route data for route planner
                        system = get_field(row, self.system_header, "")
                        
                        # For fleet carrier routes, use the new format
                        if self.fleetcarrier:
                            # Fleet Carrier format: [System Name, Distance, Distance Remaining, Tritium in tank, Tritium in market, Fuel Used, Icy Ring, Pristine, Restock Tritium]
                            dist_to_arrival, dist_remaining = get_distance_fields(row)
                            route_entry = [
                                system,                                            # 0: System Name
                                dist_to_arrival if dist_to_arrival else "",        # 1: Distance
                                dist_remaining if dist_remaining else "",          # 2: Distance Remaining
                                get_field(row, 'Tritium in tank', ''),            # 3: Tritium in tank
                                get_field(row, 'Tritium in market', ''),          # 4: Tritium in market
                            ]
                            
                            # Add Fuel Used if present (round UP to nearest hundredth)
                            if self.has_fuel_used:
                                fuel_used_raw = get_field(row, 'Fuel Used', '')
                                if fuel_used_raw:
                                    try:
                                        val = float(fuel_used_raw)
                                        rounded_val = math.ceil(val * 100) / 100
                                        route_entry.append(f"{rounded_val:.2f}")   # 5: Fuel Used
                                    except (ValueError, TypeError):
                                        route_entry.append(fuel_used_raw)
                                else:
                                    route_entry.append('')
                            else:
                                route_entry.append('')  # 5: Fuel Used placeholder
                            
                            # Add Icy Ring and Pristine if present
                            if has_icy_ring_in_file:
                                route_entry.append(get_field(row, 'Icy Ring', ''))  # 6: Icy Ring
                            else:
                                route_entry.append('')
                            
                            if has_pristine_in_file:
                                route_entry.append(get_field(row, 'Pristine', ''))  # 7: Pristine
                            else:
                                route_entry.append('')
                            
                            route_entry.append(get_field(row, self.restocktritium_header, ''))  # 8: Restock Tritium
                            
                            self.route.append(route_entry)
                            self.jumps_left += 1
                        else:
                            # Generic route format: [System, Jumps, Fuel Used?, ...]
                            jumps = get_field(row, self.jumps_header, "")
                            route_entry = [system, jumps]
                            
                            # Add Fuel Used if present (round UP to nearest hundredth)
                            if self.has_fuel_used:
                                fuel_used_raw = get_field(row, 'Fuel Used', '')
                                if fuel_used_raw:
                                    try:
                                        val = float(fuel_used_raw)
                                        rounded_val = math.ceil(val * 100) / 100
                                        route_entry.append(f"{rounded_val:.2f}")
                                    except (ValueError, TypeError):
                                        route_entry.append(fuel_used_raw)
                                else:
                                    route_entry.append('')
                            
                            self.route.append(route_entry)
                            try:
                                self.jumps_left += int(jumps) if jumps else 0
                            except (ValueError, TypeError):
                                pass

            if self.route:
                # Find where we are in the route based on current system location
                self.offset = self.find_current_waypoint_in_route()
                
                self.next_stop = self.route[self.offset][0]
                self.update_bodies_text()  # Update bodies text for Road to Riches routes
                self.compute_distances()
                self.update_gui()
                # Check fleet carrier restock warning
                if self.fleetcarrier and hasattr(self, 'check_fleet_carrier_restock_warning'):
                    self.check_fleet_carrier_restock_warning()

    def _run_plot_route_worker(self, source, dest, efficiency, range_ly, supercharge_multiplier):
        """Worker: run Spansh HTTP + poll + parse off main thread, put result in queue."""
        def put_error(err, source_red=False, dest_red=False):
            self._route_queue.put({
                'ok': False, 'error': err, 'source_red': source_red, 'dest_red': dest_red,
            })

        try:
            job_url = "https://spansh.co.uk/api/route?"
            session = timeout_session.new_session()
            session.headers['User-Agent'] = user_agent + ' GalaxyGPS'
            try:
                results = session.post(
                    job_url,
                    params={
                        "efficiency": efficiency,
                        "range": range_ly,
                        "from": source,
                        "to": dest,
                        "supercharge_multiplier": supercharge_multiplier,
                    },
                    timeout=30,
                )
            except Exception as e:
                logger.warning(f"Failed to submit route query: {e}")
                put_error(self.plot_error)
                return

            if results.status_code != 202:
                logger.warning(
                    f"Failed to query plotted route from Spansh: "
                    f"{results.status_code}; text: {results.text}"
                )
                try:
                    failure = json.loads(results.content)
                except (json.JSONDecodeError, ValueError):
                    failure = {}
                err = failure.get("error", self.plot_error) if results.status_code == 400 else self.plot_error
                source_red = bool(results.status_code == 400 and "error" in failure and "starting system" in failure["error"])
                dest_red = bool(results.status_code == 400 and "error" in failure and "finishing system" in failure["error"])
                put_error(err, source_red, dest_red)
                return

            try:
                response = json.loads(results.content)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse Spansh response: {e}")
                put_error("Invalid response from Spansh. Please try again.")
                return

            job = response.get("job")
            if not job:
                logger.warning("No job ID in Spansh response")
                put_error("Failed to start route calculation. Please try again.")
                return

            tries = 0
            route_response = None
            while tries < 20:
                try:
                    route_response = session.get(
                        f"https://spansh.co.uk/api/results/{job}",
                        timeout=5,
                    )
                except (requests.RequestException, requests.Timeout) as e:
                    logger.warning(f"Error polling Spansh results: {e}")
                    route_response = None
                    break
                if route_response.status_code != 202:
                    break
                tries += 1
                sleep(1)

            if not route_response:
                logger.warning("Query to Spansh timed out")
                put_error("The query to Spansh timed out. Please try again.")
                return

            if route_response.status_code == 200:
                try:
                    response_data = json.loads(route_response.content)
                    if "result" not in response_data or "system_jumps" not in response_data["result"]:
                        logger.warning(f"Unexpected Spansh response structure: {response_data}")
                        put_error("Invalid route data from Spansh. Please try again.")
                        return
                    route = response_data["result"]["system_jumps"]
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.warning(f"Invalid data from Spansh: {e}")
                    put_error(self.plot_error)
                    return

                if not route or len(route) == 0:
                    logger.warning("Empty route returned from Spansh")
                    put_error("No route found between the specified systems.")
                    return

                route_rows = []
                route_full_data = []
                route_fieldnames = ['System Name', 'Jumps', 'Distance To Arrival', 'Distance Remaining']
                jumps_left = 0
                for waypoint in route:
                    system = waypoint.get("system", "")
                    jumps = waypoint.get("jumps", 0)
                    distance_to_arrival = _round_distance(waypoint.get("distance_jumped", ""))
                    distance_remaining = _round_distance(waypoint.get("distance_left", ""))
                    route_rows.append([system, str(jumps), distance_to_arrival, distance_remaining])
                    full_row_data = {
                        'system name': system,
                        'jumps': str(jumps),
                        'distance to arrival': distance_to_arrival,
                        'distance remaining': distance_remaining,
                    }
                    for key, value in waypoint.items():
                        if key not in ['system', 'jumps', 'distance_jumped', 'distance_left']:
                            field_name = key.lower().replace('_', ' ')
                            full_row_data[field_name] = str(value) if value else ''
                            display_name = key.replace('_', ' ').title()
                            if display_name not in route_fieldnames:
                                route_fieldnames.append(display_name)
                    route_full_data.append(full_row_data)
                    try:
                        jumps_left += int(jumps)
                    except (ValueError, TypeError):
                        pass

                if len(route_rows) == 0:
                    put_error("Failed to process route data. Please try again.")
                    return

                self._route_queue.put({
                    'ok': True,
                    'route': route_rows,
                    'route_full_data': route_full_data,
                    'route_fieldnames': route_fieldnames,
                    'jumps_left': jumps_left,
                })
                return

            logger.warning(
                f"Failed final route fetch: {route_response.status_code}; "
                f"text: {route_response.text}"
            )
            try:
                failure = json.loads(route_response.content)
            except (json.JSONDecodeError, ValueError):
                failure = {}
            err = self.plot_error
            source_red = dest_red = False
            if route_response.status_code == 400 and "error" in failure:
                err = failure["error"]
                source_red = "starting system" in failure["error"]
                dest_red = "finishing system" in failure["error"]
            put_error(err, source_red, dest_red)

        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)
            put_error(self.plot_error)

    def _poll_route_result(self):
        """Main-thread polling: when worker puts result, apply it and update UI."""
        if getattr(config, 'shutting_down', False):
            return
        try:
            r = self._route_queue.get_nowait()
        except queue.Empty:
            self.frame.after(200, self._poll_route_result)
            return

        self.enable_plot_gui(True)
        if not r['ok']:
            self.show_error(r['error'])
            if r.get('source_red') and hasattr(self, 'source_ac'):
                self.source_ac["fg"] = "red"
            if r.get('dest_red') and hasattr(self, 'dest_ac'):
                self.dest_ac["fg"] = "red"
            return

        self.clear_route(show_dialog=False)
        self.route = r['route']
        self.route_full_data = r['route_full_data']
        self.route_fieldnames = r['route_fieldnames']
        self.jumps_left = r['jumps_left']

        self.show_plot_gui(False)
        current_system = monitor.state.get('SystemName') if monitor and hasattr(monitor, 'state') else None
        self.offset = (
            1
            if self.route and current_system and self.route[0][0].lower() == current_system.lower()
            else 0
        )
        self.next_stop = self.route[self.offset][0] if self.route else ""
        self.compute_distances()
        self.copy_waypoint()
        self.update_gui()
        self.refresh_route_window_if_open()
        if self.fleetcarrier and hasattr(self, 'check_fleet_carrier_restock_warning'):
            self.check_fleet_carrier_restock_warning()
        self.save_all_route()
        logger.info(f"Route calculated successfully: {len(self.route)} waypoints")

    def plot_route(self):
        self.hide_error()
        source = self.source_ac.get().strip()
        dest = self.dest_ac.get().strip()
        efficiency = self.efficiency_slider.get()

        self.source_ac.hide_list()
        self.dest_ac.hide_list()

        if not source or source == self.source_ac.placeholder:
            self.show_error("Please provide a starting system.")
            return
        if not dest or dest == self.dest_ac.placeholder:
            # LANG: Warning when destination system is missing in route planner
            self.show_error(plugin_tl("Please provide a destination system."))
            return
        try:
            range_ly = float(self.range_entry.get())
        except ValueError:
            self.show_error("Invalid range")
            return

        supercharge_multiplier = 6 if self.supercharge_overcharge.get() else 4
        self.enable_plot_gui(False)
        threading.Thread(
            target=self._run_plot_route_worker,
            args=(source, dest, efficiency, range_ly, supercharge_multiplier),
            daemon=True,
        ).start()
        self.frame.after(200, self._poll_route_result)

    def plot_edts(self, filename):
        try:
            with open(filename, 'r') as txtfile:
                route_txt = txtfile.readlines()
                self.clear_route(False)
                for row in route_txt:
                    if row not in (None, "", []):
                        if row.lstrip().startswith('==='):
                            jumps = int(re.findall(r"\d+ jump", row)[0].rstrip(' jumps'))
                            self.jumps_left += jumps

                            system = row[row.find('>') + 1:]
                            if ',' in system:
                                systems = system.split(',')
                                for system in systems:
                                    self.route.append([system.strip(), jumps])
                                    jumps = 1
                                    self.jumps_left += jumps
                            else:
                                self.route.append([system.strip(), jumps])
        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)
            self.enable_plot_gui(True)
            self.show_error("(2) An error occured while reading the file.")

    def export_route(self):
        if len(self.route) == 0:
            logger.debug("No route to export")
            return

        route_start = self.route[0][0]
        route_end = self.route[-1][0]
        route_name = f"{route_start} to {route_end}"
        #logger.info(f"Route name: {route_name}")

        ftypes = [('TCE Flight Plan files', '*.exp')]
        filename = filedialog.asksaveasfilename(filetypes = ftypes, initialdir=os.path.expanduser('~'), initialfile=f"{route_name}.exp")

        if filename.__len__() > 0:
            try:
                with open(filename, 'w') as csvfile:
                    for row in self.route:
                        csvfile.write(f"{route_name},{row[0]}\n")
            except Exception:
                logger.warning('!! ' + traceback.format_exc(), exc_info=False)
                self.show_error("An error occured while writing the file.")

    def clear_route(self, show_dialog=True):
        # LANG: Confirmation dialog for clearing route
        clear = askyesno(self.parent, "GalaxyGPS", plugin_tl("Are you sure you want to clear the current route?")) if show_dialog else True

        if clear:
            self.offset = 0
            self.route = []
            self.route_full_data = []  # Clear full CSV data
            self.route_fieldnames = []  # Clear fieldnames
            self.next_waypoint = ""
            self.jumps_left = 0
            self.roadtoriches = False
            self.fleetcarrier = False
            self.galaxy = False
            self.neutron = False
            self.original_csv_path = None  # Clear original CSV path reference
            try:
                os.remove(self.save_route_path)
            except (IOError, OSError):
                logger.debug("No route to delete")
            try:
                os.remove(self.offset_file_path)
            except (IOError, OSError):
                logger.debug("No offset file to delete")

            self.update_gui()

    def save_all_route(self):
        self.save_route()
        self.save_offset()

    def save_route(self):
        """
        Save route to CSV cache file.
        Uses route_full_data if available to preserve ALL original columns,
        otherwise falls back to saving self.route with appropriate headers.
        """
        if len(self.route) == 0:
            try:
                os.remove(self.save_route_path)
            except (IOError, OSError):
                pass
            return

        try:
            # PRIORITY 1: Use route_full_data if available (preserves ALL original columns)
            if self.route_full_data and len(self.route_full_data) > 0 and self.route_fieldnames:
                with open(self.save_route_path, 'w', encoding='utf-8-sig', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.route_fieldnames)
                    writer.writeheader()
                    for row_data in self.route_full_data:
                        # Convert lowercase keys back to original fieldnames for writing
                        row_to_write = {}
                        for original_fieldname in self.route_fieldnames:
                            lowercase_key = original_fieldname.lower()
                            row_to_write[original_fieldname] = row_data.get(lowercase_key, '')
                        writer.writerow(row_to_write)
                return

            # FALLBACK: Use self.route with appropriate headers based on route type
            # This path is only used if route_full_data is not available
            
            # --- Road to riches ---
            if self.roadtoriches:
                fieldnames = [
                    self.system_header,
                    self.jumps_header,
                    self.bodyname_header,
                    self.bodysubtype_header
                ]
                with open(self.save_route_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(fieldnames)
                    writer.writerows(self.route)
                return

            # --- Fleet carrier (WITH DISTANCES) ---
            if self.fleetcarrier:
                # Check if route entries have Icy Ring/Pristine data (indices 5 and 6)
                has_icy_ring_in_route = any(len(row) > 5 and row[5] for row in self.route)
                has_pristine_in_route = any(len(row) > 6 and row[6] for row in self.route)
                
                fieldnames = [
                    self.system_header,
                    self.jumps_header,
                    "Distance To Arrival",
                    "Distance Remaining",
                    self.restocktritium_header
                ]
                if has_icy_ring_in_route:
                    fieldnames.append("Icy Ring")
                if has_pristine_in_route:
                    fieldnames.append("Pristine")
                
                with open(self.save_route_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(fieldnames)
                    for row in self.route:
                        writerow_data = [
                            row[0],
                            row[1],
                            row[2] if len(row) > 2 else "",
                            row[3] if len(row) > 3 else "",
                            row[4] if len(row) > 4 else ""
                        ]
                        if has_icy_ring_in_route:
                            writerow_data.append(row[5] if len(row) > 5 else "")
                        if has_pristine_in_route:
                            writerow_data.append(row[6] if len(row) > 6 else "")
                        writer.writerow(writerow_data)
                return

            # --- Galaxy ---
            if self.galaxy:
                fieldnames = [
                    self.system_header,
                    self.refuel_header,
                    "Distance To Arrival",
                    "Distance Remaining"
                ]
                with open(self.save_route_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(fieldnames)
                    for row in self.route:
                        writer.writerow([
                            row[0],
                            row[1],
                            row[2] if len(row) > 2 else "",
                            row[3] if len(row) > 3 else ""
                        ])
                return

            # --- Standard route (from Spansh API) ---
            # Default format for routes calculated via API - has System Name, Jumps, Distance To Arrival, Distance Remaining
            if len(self.route) > 0 and len(self.route[0]) >= 2:
                # Check if this is a neutron route format (5 columns) or standard API route (4 columns)
                is_neutron_format = len(self.route[0]) >= 5
                
                if is_neutron_format:
                    # Neutron route format
                    fieldnames = [
                        "System Name",
                        "Distance To Arrival",
                        "Distance Remaining",
                        "Neutron Star",
                        "Jumps"
                    ]
                else:
                    # Standard API route format
                    fieldnames = [
                        self.system_header,
                        self.jumps_header,
                        "Distance To Arrival",
                        "Distance Remaining"
                    ]
                
                with open(self.save_route_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(fieldnames)
                    writer.writerows(self.route)
                return
            
            # --- Generic with distances (neutron route format) ---
            if any(len(r) >= 4 for r in self.route):
                fieldnames = [
                    "System Name",
                    "Distance To Arrival",
                    "Distance Remaining",
                    "Neutron Star",
                    "Jumps"
                ]
                with open(self.save_route_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(fieldnames)
                    for row in self.route:
                        writer.writerow([
                            row[0],
                            row[2] if len(row) > 2 else "",
                            row[3] if len(row) > 3 else "",
                            "",
                            row[1]
                        ])
                return

            # --- Fallback ---
            with open(self.save_route_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([self.system_header, self.jumps_header])
                writer.writerows(self.route)

        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)


    def save_offset(self):
        if len(self.route) != 0:
            with open(self.offset_file_path, 'w') as offset_fh:
                offset_fh.write(str(self.offset))
        else:
            try:
                os.remove(self.offset_file_path)
            except (IOError, OSError):
                logger.debug("No offset to delete")

    def update_bodies_text(self):
        if not self.roadtoriches: 
            logger.debug(f"[update_bodies_text] Not a Road to Riches route, skipping")
            return

        # For the bodies to scan use the current system, which is one before the next stop
        lastsystemoffset = self.offset - 1
        if lastsystemoffset < 0:
            lastsystemoffset = 0 # Display bodies of the first system

        logger.debug(f"[update_bodies_text] lastsystemoffset={lastsystemoffset}, route length={len(self.route)}")

        # Validate that the route entry has the required indices for Road to Riches
        # Road to Riches routes should have: [0]=system, [1]=jumps, [2]=bodynames, [3]=bodysubtypes
        # But external Road to Riches CSVs might have a different structure
        if lastsystemoffset >= len(self.route):
            logger.warning(f'[update_bodies_text] lastsystemoffset ({lastsystemoffset}) >= route length ({len(self.route)})')
            return
        
        route_entry = self.route[lastsystemoffset]
        
        # Get the system name to count bodies for
        lastsystem = route_entry[0] if len(route_entry) > 0 else None
        if not lastsystem:
            logger.debug(f"[update_bodies_text] No system name at offset {lastsystemoffset}")
            self.bodies = ""
            return
        
        logger.debug(f"[update_bodies_text] Counting bodies for system: {lastsystem}")
        
        # Count how many rows in the route have the same system name as lastsystem
        body_count = 0
        for row in self.route:
            if len(row) > 0:
                system_name = row[0] if row[0] else ""
                if system_name and system_name.lower() == lastsystem.lower():
                    body_count += 1
        
        logger.debug(f"[update_bodies_text] Body count for {lastsystem}: {body_count}")
        
        # Display the count
        if body_count > 0:
            bodies_text = f"{body_count}"
        else:
            bodies_text = "0"
        
        if len(route_entry) < 4:
            # Road to Riches route entry doesn't have bodynames/bodysubtypes
            # This can happen with external Road to Riches CSVs that have a different structure
            logger.debug(f"[update_bodies_text] Route entry too short ({len(route_entry)}), showing count only")
            self.bodies = bodies_text  # Just show the count
            return

        bodynames = route_entry[2]
        bodysubtypes = route_entry[3]
        
        # Validate that bodynames and bodysubtypes are lists/iterables
        if not isinstance(bodynames, (list, tuple)) or not isinstance(bodysubtypes, (list, tuple)):
            logger.warning(f'[update_bodies_text] bodynames or bodysubtypes are not lists at offset {lastsystemoffset}')
            self.bodies = bodies_text  # Just show the count
            return
        
        # Ensure bodynames and bodysubtypes have the same length
        if len(bodynames) != len(bodysubtypes):
            logger.warning(f'[update_bodies_text] bodynames length ({len(bodynames)}) != bodysubtypes length ({len(bodysubtypes)}) at offset {lastsystemoffset}')
            self.bodies = bodies_text  # Just show the count
            return
        
        # Handle empty lists
        if len(bodynames) == 0 or len(bodysubtypes) == 0:
            self.bodies = f"{bodies_text}\n{lastsystem}: (no bodies)"
            logger.debug(f"[update_bodies_text] No bodies in lists, result: {self.bodies}")
            return
     
        waterbodies = []
        rockybodies = []
        metalbodies = []
        earthlikebodies = []
        unknownbodies = []

        for num, name in enumerate(bodysubtypes):
            # Ensure we don't go out of bounds
            if num >= len(bodynames):
                logger.warning(f'[update_bodies_text] Index {num} >= bodynames length ({len(bodynames)}) at offset {lastsystemoffset}')
                break
            
            try:
                body_name = str(bodynames[num]) if bodynames[num] else ""
                subtype_name = str(name) if name else ""
                shortbodyname = body_name.replace(lastsystem + " ", "")
                
                if subtype_name.lower() == "high metal content world":
                    metalbodies.append(shortbodyname)
                elif subtype_name.lower() == "rocky body": 
                    rockybodies.append(shortbodyname)
                elif subtype_name.lower() == "earth-like world":
                    earthlikebodies.append(shortbodyname)
                elif subtype_name.lower() == "water world": 
                    waterbodies.append(shortbodyname)
                else:
                    unknownbodies.append(shortbodyname)
            except Exception as e:
                logger.warning(f'[update_bodies_text] Error processing body {num} at offset {lastsystemoffset}: {e}', exc_info=False)
                continue

        bodysubtypeandname = ""
        if len(metalbodies) > 0: bodysubtypeandname += f"\n   Metal: " + ', '.join(metalbodies)
        if len(rockybodies) > 0: bodysubtypeandname += f"\n   Rocky: " + ', '.join(rockybodies)
        if len(earthlikebodies) > 0: bodysubtypeandname += f"\n   Earth: " + ', '.join(earthlikebodies)
        if len(waterbodies) > 0: bodysubtypeandname += f"\n   Water: " + ', '.join(waterbodies)
        if len(unknownbodies) > 0: bodysubtypeandname += f"\n   Unknown: " + ', '.join(unknownbodies)

        self.bodies = f"{bodies_text}\n{lastsystem}:{bodysubtypeandname}"
        logger.debug(f"[update_bodies_text] Final self.bodies: {self.bodies[:100]}...")


    def check_range(self, name, index, mode):
        value = self.range_entry.var.get()
        if value.__len__() > 0 and value != self.range_entry.placeholder:
            try:
                float(value)
                self.range_entry.set_error_style(False)
                self.hide_error()
            except ValueError:
                self.show_error("Invalid range")
                self.range_entry.set_error_style()

    def cleanup_old_version(self):
        try:
            if (os.path.exists(os.path.join(self.plugin_dir, "AutoCompleter.py"))
            and os.path.exists(os.path.join(self.plugin_dir, "GalaxyGPS"))):
                files_list = os.listdir(self.plugin_dir)

                for filename in files_list:
                    if (filename != "load.py"
                    and (filename.endswith(".py") or filename.endswith(".pyc") or filename.endswith(".pyo"))):
                        os.remove(os.path.join(self.plugin_dir, filename))
        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)

    def check_for_update(self):
        # Auto-updates enabled
        # GitHub repository configuration
        github_repo = "Fenris159/EDMC_GalaxyGPS"  # Format: "username/repository"
        github_branch = "master"  # Your default branch name (master, main, etc.)
        
        self.cleanup_old_version()
        version_url = f"https://raw.githubusercontent.com/{github_repo}/{github_branch}/version.json"
        try:
            session = timeout_session.new_session()
            session.headers['User-Agent'] = user_agent + ' GalaxyGPS'
            response = session.get(version_url, timeout=2)
            if response.status_code == 200:
                remote_version_content = response.text.strip()
                try:
                    remote_version = json.loads(remote_version_content)
                except json.JSONDecodeError:
                    # Fallback: if it's not valid JSON, treat as plain text (remove quotes if present)
                    remote_version = remote_version_content.strip('"\'')
                if self.plugin_version != remote_version:
                    self.update_available = True
                    self.spansh_updater = SpanshUpdater(remote_version, self.plugin_dir)

            else:
                logger.warning(f"Could not query latest GalaxyGPS version, code: {str(response.status_code)}; text: {response.text}")
        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)

    def install_update(self):
        self.spansh_updater.install()

    #   -- Fleet Carrier CAPI Integration --
    
    def get_fleet_carrier(self, callsign: str):
        """
        Get fleet carrier information by callsign.
        
        Args:
            callsign: Fleet carrier callsign (e.g., "A1A-A1A")
            
        Returns:
            Dictionary with carrier information or None if not found
        """
        if self.fleet_carrier_manager:
            return self.fleet_carrier_manager.get_carrier(callsign)
        return None
    
    def get_all_fleet_carriers(self):
        """
        Get all fleet carriers stored in CSV.
        
        Returns:
            List of carrier dictionaries
        """
        if self.fleet_carrier_manager:
            return self.fleet_carrier_manager.get_all_carriers()
        return []
    
    def update_fleet_carrier_dropdown(self):
        """
        Update the fleet carrier dropdown with available carriers.
        """
        if not self.fleet_carrier_combobox:
            return
        
        try:
            carriers = self.get_all_fleet_carriers()
            if carriers:
                # Create display strings for dropdown
                carrier_options = []
                for carrier in sorted(carriers, key=lambda x: x.get('last_updated', ''), reverse=True):
                    callsign = carrier.get('callsign', 'Unknown')
                    name = carrier.get('name', '')
                    system = carrier.get('current_system', 'Unknown')
                    fuel = carrier.get('fuel', '0')
                    
                    display_name = f"{name} ({callsign})" if name else callsign
                    display_text = f"{display_name} | {system} | Tritium: {fuel}"
                    carrier_options.append(display_text)
                
                self.fleet_carrier_combobox['values'] = carrier_options
                
                # Set default selection to first (most recent) carrier
                if carrier_options:
                    if not self.selected_carrier_callsign:
                        # First time: auto-select first carrier
                        self.fleet_carrier_combobox.current(0)
                        self.on_carrier_selected()
                    else:
                        # Already have a selection: refresh display data for current selection
                        # This ensures system and balance update after CAPI refresh
                        if hasattr(self, 'update_fleet_carrier_system_display'):
                            self.update_fleet_carrier_system_display()
                        if hasattr(self, 'update_fleet_carrier_balance_display'):
                            self.update_fleet_carrier_balance_display()
                        if hasattr(self, 'update_fleet_carrier_tritium_display'):
                            self.update_fleet_carrier_tritium_display()
                        if hasattr(self, 'update_fleet_carrier_rings_status'):
                            self.update_fleet_carrier_rings_status()
                    # Enable Inara button if carrier is selected
                    if self.fleet_carrier_inara_btn:
                        self.fleet_carrier_inara_btn.config(state=tk.NORMAL)
            else:
                self.fleet_carrier_combobox['values'] = ["No carrier data"]
                self.fleet_carrier_combobox.current(0)
                # Disable Inara button if no carrier data
                if self.fleet_carrier_inara_btn:
                    self.fleet_carrier_inara_btn.config(state=tk.DISABLED)
                # Set displays to Unknown when no data
                if hasattr(self, 'update_fleet_carrier_system_display'):
                    self.update_fleet_carrier_system_display()
                if hasattr(self, 'update_fleet_carrier_balance_display'):
                    self.update_fleet_carrier_balance_display()
        except Exception:
            logger.warning('!! Error updating fleet carrier dropdown: ' + traceback.format_exc(), exc_info=False)
            self.fleet_carrier_combobox['values'] = ["Error loading carrier data"]
    
    def on_carrier_selected(self, event=None):
        """
        Handle carrier selection from dropdown.
        After selection, simplifies the displayed text to just the carrier name.
        """
        try:
            selection = self.fleet_carrier_var.get()
            if not selection or selection == "No carrier data" or selection == "Error loading carrier data":
                self.selected_carrier_callsign = None
                # Disable Inara button if no carrier selected
                if self.fleet_carrier_inara_btn:
                    self.fleet_carrier_inara_btn.config(state=tk.DISABLED)
                # Update warning check and system display
                if hasattr(self, 'check_fleet_carrier_restock_warning'):
                    self.check_fleet_carrier_restock_warning()
                if hasattr(self, 'update_fleet_carrier_system_display'):
                    self.update_fleet_carrier_system_display()
                if hasattr(self, 'update_fleet_carrier_rings_status'):
                    self.update_fleet_carrier_rings_status()
                if hasattr(self, 'update_fleet_carrier_balance_display'):
                    self.update_fleet_carrier_balance_display()
                return
            
            # Extract callsign from selection (format: "Name (CALLSIGN) | System | ...")
            # Try to find the callsign in parentheses
            match = re.search(r'\(([A-Z0-9]+-[A-Z0-9]+)\)', selection)
            if match:
                self.selected_carrier_callsign = match.group(1)
            else:
                # Fallback: try to extract from start if no name
                parts = selection.split(' | ')
                if parts:
                    self.selected_carrier_callsign = parts[0].strip()
            
            # Simplify displayed text to just carrier name after selection
            # Extract just the name part (before the first |)
            display_parts = selection.split(' | ')
            if display_parts:
                simple_display = display_parts[0]  # "Name (CALLSIGN)"
                self.fleet_carrier_var.set(simple_display)
            
            # Enable Inara button when carrier is selected
            if self.fleet_carrier_inara_btn and self.selected_carrier_callsign:
                self.fleet_carrier_inara_btn.config(state=tk.NORMAL)
            
                # Update warning check, system display, rings status, Tritium display, and balance display when carrier selection changes
            if hasattr(self, 'check_fleet_carrier_restock_warning'):
                self.check_fleet_carrier_restock_warning()
            if hasattr(self, 'update_fleet_carrier_system_display'):
                self.update_fleet_carrier_system_display()
            if hasattr(self, 'update_fleet_carrier_rings_status'):
                self.update_fleet_carrier_rings_status()
            if hasattr(self, 'update_fleet_carrier_tritium_display'):
                self.update_fleet_carrier_tritium_display()
            if hasattr(self, 'update_fleet_carrier_balance_display'):
                self.update_fleet_carrier_balance_display()
        except Exception:
            logger.warning('!! Error handling carrier selection: ' + traceback.format_exc(), exc_info=False)
    
    # _style_combobox_popup method removed - no longer needed with custom ThemedCombobox widget
    
    def open_selected_carrier_inara(self):
        """
        Open Inara.cz page for the currently selected fleet carrier in the dropdown.
        """
        try:
            if not self.selected_carrier_callsign:
                # LANG: Warning when no fleet carrier selected
                showwarning(self.parent, plugin_tl("No Carrier Selected"), plugin_tl("Please select a fleet carrier first."))
                return
            
            self.open_inara_carrier(self.selected_carrier_callsign)
        except Exception:
            logger.warning('!! Error opening selected carrier Inara page: ' + traceback.format_exc(), exc_info=False)
            # LANG: Error opening Inara website
            showerror(self.parent, plugin_tl("Error"), plugin_tl("Failed to open Inara page."))
    
    def select_carrier_from_details(self, callsign: str, details_window=None):
        """
        Select a carrier from the details window and update the dropdown.
        
        Args:
            callsign: The callsign of the carrier to select
            details_window: Optional reference to the details window (to refresh if needed)
        """
        try:
            if not callsign or not self.fleet_carrier_combobox:
                return
            
            # Find the matching carrier option in the dropdown
            dropdown_values = self.fleet_carrier_combobox['values']
            selected_index = None
            
            for idx, option in enumerate(dropdown_values):
                # Extract callsign from option (format: "Name (CALLSIGN) | System | ...")
                match = re.search(r'\(([A-Z0-9]+-[A-Z0-9]+)\)', option)
                if match and match.group(1) == callsign:
                    selected_index = idx
                    break
            
            # If found, select it in the dropdown
            if selected_index is not None:
                self.fleet_carrier_combobox.current(selected_index)
                # Trigger the selection handler
                self.on_carrier_selected()
                logger.info(f"Selected carrier {callsign} from details window")
            else:
                # Fallback: try to set directly by callsign matching
                self.selected_carrier_callsign = callsign
                # Update dropdown if we can find a match
                self.update_fleet_carrier_dropdown()
                # Find and set the current selection
                for idx, option in enumerate(self.fleet_carrier_combobox['values']):
                    match = re.search(r'\(([A-Z0-9]+-[A-Z0-9]+)\)', option)
                    if match and match.group(1) == callsign:
                        self.fleet_carrier_combobox.current(idx)
                        self.on_carrier_selected()
                        break
                
        except Exception:
            logger.warning(f'!! Error selecting carrier {callsign} from details window: ' + traceback.format_exc(), exc_info=False)
    
    def show_carrier_details_window(self):
        """
        Open a window displaying all fleet carriers with details and Inara.cz links.
        """
        try:
            show_carrier_details_window(self)
        except Exception as e:
            logger.error(f"[GalaxyGPS.show_carrier_details_window] ERROR: {e}", exc_info=True)
    
    def open_inara_carrier(self, callsign: str):
        """
        Open Inara.cz page for a fleet carrier.
        
        Args:
            callsign: Fleet carrier callsign (may contain spaces or special characters)
        
        Note: urllib.parse.quote() properly URL-encodes spaces (%20) and special characters
        """
        try:
            # Inara fleet carrier search URL format
            # Fleet carriers are accessed via the station search endpoint
            # urllib.parse.quote() handles spaces, special chars, and unicode properly
            # e.g., "My Carrier" becomes "My%20Carrier"
            encoded_callsign = urllib.parse.quote(callsign)
            url = f"https://inara.cz/elite/station/?search={encoded_callsign}"
            webbrowser.open(url)
        except Exception:
            logger.warning(f'!! Error opening Inara carrier page for {callsign}: ' + traceback.format_exc(), exc_info=False)
    
    def open_inara_system(self, system_name: str):
        """
        Open Inara.cz page for a system.
        
        Args:
            system_name: System name (may contain spaces or special characters)
        
        Note: urllib.parse.quote() properly URL-encodes spaces (%20) and special characters
        """
        try:
            # Inara system URL format: https://inara.cz/elite/starsystem/?search=SYSTEMNAME
            # urllib.parse.quote() handles spaces, special chars, and unicode properly
            # e.g., "Sol" stays "Sol", "Alpha Centauri" becomes "Alpha%20Centauri"
            encoded_name = urllib.parse.quote(system_name)
            url = f"https://inara.cz/elite/starsystem/?search={encoded_name}"
            webbrowser.open(url)
        except Exception:
            logger.warning(f'!! Error opening Inara system page for {system_name}: ' + traceback.format_exc(), exc_info=False)
    
    def open_edsm_system(self, system_name: str):
        """
        Open EDSM.net page for a system.
        
        Args:
            system_name: System name (may contain spaces or special characters)
        
        Note: urllib.parse.quote() properly URL-encodes spaces (%20) and special characters
        """
        try:
            # EDSM system URL format: https://www.edsm.net/en/system?systemName=SYSTEMNAME
            # urllib.parse.quote() handles spaces, special chars, and unicode properly
            encoded_name = urllib.parse.quote(system_name)
            url = f"https://www.edsm.net/en/system?systemName={encoded_name}"
            webbrowser.open(url)
        except Exception:
            logger.warning(f'!! Error opening EDSM system page for {system_name}: ' + traceback.format_exc(), exc_info=False)
    
    def check_fleet_carrier_restock_warning(self):
        """
        Check if the current waypoint in the route requires Tritium restock.
        Shows warning and "Find Trit" button if the current waypoint has "Restock Tritium" = "Yes".
        """
        if not self.fleetcarrier or not self.route:
            self.fleetrestock_lbl.grid_remove()
            self.find_trit_btn.grid_remove()
            return
        
        # Check if we have a valid offset
        if self.offset < 0 or self.offset >= len(self.route):
            self.fleetrestock_lbl.grid_remove()
            self.find_trit_btn.grid_remove()
            return
        
        # Get the current waypoint from the route
        current_waypoint = self.route[self.offset]
        
        logger.debug(f"[check_fleet_carrier_restock_warning] Checking waypoint at offset {self.offset}, length: {len(current_waypoint)}")
        
        # Check if this route entry has "Restock Tritium" = "Yes"
        # For fleet carrier routes: [System Name, Distance, Distance Remaining, Tritium in tank, Tritium in market, Fuel Used, Icy Ring, Pristine, Restock Tritium]
        # Restock Tritium is at index 8
        if len(current_waypoint) > 8:
            restock_value = current_waypoint[8].strip().lower() if current_waypoint[8] else ""
            logger.debug(f"[check_fleet_carrier_restock_warning] Restock Tritium value at offset {self.offset}: '{restock_value}'")
            if restock_value == "yes":
                # Show warning
                logger.debug(f"[check_fleet_carrier_restock_warning] Showing restock warning")
                self.fleetrestock_lbl["text"] = plugin_tl("Restock Tritium Now")
                self.fleetrestock_lbl.grid()
                self.find_trit_btn.grid()
                return
        else:
            logger.debug(f"[check_fleet_carrier_restock_warning] Route entry length {len(current_waypoint)} <= 8")
        
        # Hide if no restock needed at current waypoint
        logger.debug(f"[check_fleet_carrier_restock_warning] No restock needed, hiding warning")
        self.fleetrestock_lbl.grid_remove()
        self.find_trit_btn.grid_remove()
    
    def find_tritium_on_inara(self):
        """
        Open Inara.cz commodity search for Tritium near the carrier's current system.
        """
        try:
            # Get the currently selected carrier's system
            carrier_system = None
            if self.selected_carrier_callsign and self.fleet_carrier_manager:
                carrier = self.fleet_carrier_manager.get_carrier(self.selected_carrier_callsign)
                if carrier:
                    carrier_system = carrier.get('current_system', '').strip()
            
            # If no carrier selected, try to get the first/primary carrier
            if not carrier_system:
                carriers = self.get_all_fleet_carriers()
                if carriers:
                    sorted_carriers = sorted(
                        carriers,
                        key=lambda x: x.get('last_updated', ''),
                        reverse=True
                    )
                    carrier_system = sorted_carriers[0].get('current_system', '').strip()
            
            if not carrier_system:
                # LANG: Warning when carrier system unknown
                showwarning(self.parent, plugin_tl("No System"), plugin_tl("Could not determine carrier's current system."))
                return
            
            # Inara.cz commodity search URL format
            # https://inara.cz/elite/commodities/?pi2=10269&ps1=SYSTEMNAME
            encoded_system = urllib.parse.quote(carrier_system)
            url = f"https://inara.cz/elite/commodities/?pi2=10269&ps1={encoded_system}"
            webbrowser.open(url)
            
        except Exception:
            logger.warning('!! Error opening Inara Tritium search: ' + traceback.format_exc(), exc_info=False)
            # LANG: Error opening Inara tritium search
            showerror(self.parent, plugin_tl("Error"), plugin_tl("Failed to open Inara Tritium search."))
    
    def fleet_carrier_system_url(self, system: str) -> str | None:
        """
        Generate URL for fleet carrier's current system.
        Uses the configured system provider (EDSM/Inara/Spansh).
        """
        if not self.current_fc_system:
            return None
        
        try:
            import plug  # type: ignore
            from config import config  # type: ignore
            
            # Use the same provider as main EDMC system display
            provider = config.get_str('system_provider', default='EDSM')
            url = plug.invoke(provider, 'EDSM', 'system_url', self.current_fc_system)
            return url
        except Exception as e:
            logger.warning(f'!! Error generating FC system URL: {e}')
            return None
    
    def update_fleet_carrier_system_display(self):
        """
        Display the current system for the selected fleet carrier.
        Reads directly from FleetCarrierManager cache.
        """
        if not self.fleet_carrier_system_label:
            return
        
        try:
            # If no carrier selected, try to use the most recent one
            callsign = self.selected_carrier_callsign
            
            if not callsign:
                # No selection - try to get most recent carrier
                carriers = self.get_all_fleet_carriers()
                if carriers:
                    sorted_carriers = sorted(carriers, key=lambda x: x.get('last_updated', ''), reverse=True)
                    callsign = sorted_carriers[0].get('callsign', '') if sorted_carriers else None
            
            if not callsign:
                self.current_fc_system = None
                self.fleet_carrier_system_name['text'] = "Unknown"
                self.fleet_carrier_system_name['url'] = None
                return
            
            # Get carrier data directly from manager
            if self.fleet_carrier_manager:
                carrier = self.fleet_carrier_manager.get_carrier(callsign)
                if carrier:
                    system = carrier.get('current_system', '').strip()
                    if system:
                        # Store system name for URL generation
                        self.current_fc_system = system
                        # Update the hyperlink label with the system name
                        self.fleet_carrier_system_name['text'] = system
                        self.fleet_carrier_system_name['url'] = self.fleet_carrier_system_url
                    else:
                        self.current_fc_system = None
                        self.fleet_carrier_system_name['text'] = "Unknown"
                        self.fleet_carrier_system_name['url'] = None
                else:
                    self.current_fc_system = None
                    self.fleet_carrier_system_name['text'] = "Unknown"
                    self.fleet_carrier_system_name['url'] = None
            else:
                self.current_fc_system = None
                self.fleet_carrier_system_name['text'] = "Unknown"
                self.fleet_carrier_system_name['url'] = None
        except Exception:
            logger.warning('!! Error updating fleet carrier system display: ' + traceback.format_exc(), exc_info=False)
            self.current_fc_system = None
            self.fleet_carrier_system_name['text'] = "Unknown"
            self.fleet_carrier_system_name['url'] = None
    
    def find_tritium_near_current_system(self):
        """
        Open Inara.cz commodity search for Tritium near the selected fleet carrier's current system.
        Uses the same data source as the "View All" window (CSV data).
        """
        try:
            # Get all carriers from CSV (same as "View All" window)
            carriers = self.get_all_fleet_carriers()
            if not carriers:
                # LANG: Warning when no carrier data available
                showwarning(self.parent, plugin_tl("No Carrier Data"), plugin_tl("No fleet carrier data available."))
                return
            
            # Find the selected carrier by callsign
            carrier = None
            if self.selected_carrier_callsign:
                for c in carriers:
                    if c.get('callsign', '').strip() == self.selected_carrier_callsign.strip():
                        carrier = c
                        break
            
            # If no carrier selected, use the most recently updated carrier
            if not carrier:
                try:
                    sorted_carriers = sorted(
                        carriers,
                        key=lambda x: str(x.get('last_updated', '')),
                        reverse=True
                    )
                    if sorted_carriers:
                        carrier = sorted_carriers[0]
                except (KeyError, IndexError, TypeError):
                    # If sorting fails, just use first carrier
                    if carriers:
                        carrier = carriers[0]
            
            # Get carrier's current system
            if carrier:
                carrier_system = carrier.get('current_system', '').strip()
                if not carrier_system:
                    # LANG: Warning when carrier system location unknown
                    showwarning(self.parent, plugin_tl("No System"), plugin_tl("Could not determine carrier's current system location."))
                    return
            else:
                # LANG: Warning when no carrier selected
                showwarning(self.parent, plugin_tl("No Carrier"), plugin_tl("No fleet carrier selected."))
                return
            
            # Inara.cz commodity search URL format
            # https://inara.cz/elite/commodities/?pi2=10269&ps1=SYSTEMNAME
            encoded_system = urllib.parse.quote(carrier_system)
            url = f"https://inara.cz/elite/commodities/?pi2=10269&ps1={encoded_system}"
            webbrowser.open(url)
            
        except Exception:
            logger.warning('!! Error opening Inara Tritium search near carrier system: ' + traceback.format_exc(), exc_info=False)
            # LANG: Error opening Inara tritium search
            showerror(self.parent, plugin_tl("Error"), plugin_tl("Failed to open Inara Tritium search."))
    
    def _run_rings_worker(self, callsign, carrier_system, result_queue):
        """Worker: query EDSM for system bodies (icy/pristine rings) off main thread, put result in queue."""
        has_icy_rings = False
        has_pristine = False
        try:
            encoded_system = urllib.parse.quote(carrier_system)
            url = f"https://www.edsm.net/api-system-v1/bodies?systemName={encoded_system}"
            session = timeout_session.new_session()
            session.headers['User-Agent'] = user_agent + ' GalaxyGPS'
            response = session.get(url, timeout=5)
            if response.status_code == 200:
                system_data = response.json()
                if 'bodies' in system_data and isinstance(system_data['bodies'], list):
                    for body in system_data['bodies']:
                        if 'rings' in body and isinstance(body['rings'], list):
                            for ring in body['rings']:
                                ring_type = ring.get('type', '').strip()
                                reserve_level = ring.get('reserveLevel', '').strip()
                                if ring_type.lower() == 'icy':
                                    has_icy_rings = True
                                    if reserve_level.lower() == 'pristine':
                                        has_pristine = True
                                        break
                            if has_icy_rings and has_pristine:
                                break
                if self.fleet_carrier_manager:
                    self.fleet_carrier_manager.update_rings_status(callsign, has_icy_rings, has_pristine)
        except requests.RequestException as e:
            logger.warning(f'!! Error querying EDSM API for system bodies: {e}')
            has_icy_rings = False
            has_pristine = False
        except Exception:
            logger.warning('!! Error checking fleet carrier rings status: ' + traceback.format_exc(), exc_info=False)
            has_icy_rings = False
            has_pristine = False
        result_queue.put({'has_icy_rings': has_icy_rings, 'has_pristine': has_pristine})

    def _poll_rings_result(self, result_queue):
        """Main-thread polling: when rings worker puts result, update vars and redraw toggles."""
        if getattr(config, 'shutting_down', False):
            return
        try:
            r = result_queue.get_nowait()
        except queue.Empty:
            if hasattr(self, 'frame') and self.frame:
                self.frame.after(200, lambda: self._poll_rings_result(result_queue))
            return
        self.fleet_carrier_icy_rings_var.set(r['has_icy_rings'])
        self.fleet_carrier_pristine_var.set(r['has_pristine'])
        self._draw_icy_rings_toggle()
        self._draw_pristine_toggle()

    def update_fleet_carrier_rings_status(self):
        """
        Update the Icy Rings and Pristine checkboxes from CSV data.
        Only queries EDSM API if data is missing from CSV (e.g., after system change or initial load).
        Updates are stored back to the CSV managed by FleetCarrierManager.
        Uses the same data source as the "View All" window (CSV data).
        """
        if not self.fleet_carrier_icy_rings_cb or not self.fleet_carrier_pristine_cb:
            return
        
        try:
            carriers = self.get_all_fleet_carriers()
            if not carriers:
                self.fleet_carrier_icy_rings_var.set(False)
                self.fleet_carrier_pristine_var.set(False)
                self._draw_icy_rings_toggle()
                self._draw_pristine_toggle()
                return
            
            carrier = None
            callsign = None
            if self.selected_carrier_callsign:
                for c in carriers:
                    if c.get('callsign', '').strip() == self.selected_carrier_callsign.strip():
                        carrier = c
                        callsign = c.get('callsign', '').strip()
                        break
            
            if not carrier:
                try:
                    sorted_carriers = sorted(
                        carriers,
                        key=lambda x: str(x.get('last_updated', '')),
                        reverse=True
                    )
                    if sorted_carriers:
                        carrier = sorted_carriers[0]
                        callsign = carrier.get('callsign', '').strip()
                except (KeyError, IndexError, TypeError):
                    if carriers:
                        carrier = carriers[0]
                        callsign = carrier.get('callsign', '').strip()
            
            if not carrier or not callsign:
                self.fleet_carrier_icy_rings_var.set(False)
                self.fleet_carrier_pristine_var.set(False)
                self._draw_icy_rings_toggle()
                self._draw_pristine_toggle()
                return
            
            carrier_system = carrier.get('current_system', '').strip()
            if not carrier_system:
                self.fleet_carrier_icy_rings_var.set(False)
                self.fleet_carrier_pristine_var.set(False)
                self._draw_icy_rings_toggle()
                self._draw_pristine_toggle()
                return
            
            icy_rings_stored = carrier.get('icy_rings', '').strip()
            pristine_stored = carrier.get('pristine', '').strip()
            has_icy_rings = False
            has_pristine = False
            need_api_query = False
            
            if icy_rings_stored.lower() in ['yes', 'no'] and pristine_stored.lower() in ['yes', 'no']:
                has_icy_rings = (icy_rings_stored.lower() == 'yes')
                has_pristine = (pristine_stored.lower() == 'yes')
            else:
                need_api_query = True
                logger.info(f"No stored rings status for carrier {callsign} in system {carrier_system}, querying API")
            
            if need_api_query:
                if not (hasattr(self, 'frame') and self.frame):
                    return
                result_queue = queue.Queue()
                threading.Thread(
                    target=self._run_rings_worker,
                    args=(callsign, carrier_system, result_queue),
                    daemon=True,
                ).start()
                self.frame.after(200, lambda: self._poll_rings_result(result_queue))
                return
            
            self.fleet_carrier_icy_rings_var.set(has_icy_rings)
            self.fleet_carrier_pristine_var.set(has_pristine)
            self._draw_icy_rings_toggle()
            self._draw_pristine_toggle()
                
        except Exception:
            logger.warning('!! Error updating fleet carrier rings status: ' + traceback.format_exc(), exc_info=False)
            self.fleet_carrier_icy_rings_var.set(False)
            self.fleet_carrier_pristine_var.set(False)
            self._draw_icy_rings_toggle()
            self._draw_pristine_toggle()
    
    def update_fleet_carrier_tritium_display(self):
        """
        Update the fleet carrier Tritium display (fuel and cargo) under the system display.
        Uses the same data source as the "View All" window (CSV data).
        """
        if not self.fleet_carrier_tritium_label:
            return
        
        try:
            # Get all carriers from CSV (same as "View All" window)
            carriers = self.get_all_fleet_carriers()
            if not carriers:
                self.fleet_carrier_tritium_label.config(text="Tritium: Unknown", foreground="gray", cursor="")
                return
            
            # Find the selected carrier by callsign
            carrier = None
            if self.selected_carrier_callsign:
                for c in carriers:
                    if c.get('callsign', '').strip() == self.selected_carrier_callsign.strip():
                        carrier = c
                        break
            
            # If no carrier selected, use the most recently updated carrier
            if not carrier:
                try:
                    sorted_carriers = sorted(
                        carriers,
                        key=lambda x: str(x.get('last_updated', '')),
                        reverse=True
                    )
                    if sorted_carriers:
                        carrier = sorted_carriers[0]
                except (KeyError, IndexError, TypeError):
                    # If sorting fails, just use first carrier
                    if carriers:
                        carrier = carriers[0]
            
            # Get Tritium data from carrier (same logic as "View All" window)
            if carrier:
                fuel_raw = carrier.get('fuel')
                tritium_cargo_raw = carrier.get('tritium_in_cargo')
                
                # Check if fuel is missing (same logic as "View All" window)
                fuel_missing = 'fuel' not in carrier or fuel_raw is None or (isinstance(fuel_raw, str) and fuel_raw.strip() == '')
                tritium_cargo_missing = 'tritium_in_cargo' not in carrier or tritium_cargo_raw is None or (isinstance(tritium_cargo_raw, str) and tritium_cargo_raw.strip() == '')
                
                if fuel_missing:
                    self.fleet_carrier_tritium_label.config(text="Tritium: Unknown", foreground="gray", cursor="")
                else:
                    # Format the display (same as "View All" window)
                    fuel = fuel_raw if fuel_raw is not None else '0'
                    tritium_cargo = tritium_cargo_raw if tritium_cargo_raw is not None else '0'
                    
                    if not tritium_cargo_missing and tritium_cargo and tritium_cargo != '0':
                        try:
                            fuel_int = int(fuel) if fuel else 0
                            tritium_cargo_int = int(tritium_cargo) if tritium_cargo else 0
                            display_text = f"Tritium: {fuel_int} (In Cargo: {tritium_cargo_int})"
                        except (ValueError, TypeError):
                            display_text = f"Tritium: {fuel} (In Cargo: {tritium_cargo})"
                    else:
                        try:
                            fuel_int = int(fuel) if fuel else 0
                            display_text = f"Tritium: {fuel_int}"
                        except (ValueError, TypeError):
                            display_text = f"Tritium: {fuel}"
                    
                    self.fleet_carrier_tritium_label.config(text=display_text, foreground="blue", cursor="hand2")
            else:
                self.fleet_carrier_tritium_label.config(text="Tritium: Unknown", foreground="gray", cursor="")
        except Exception:
            logger.warning('!! Error updating fleet carrier Tritium display: ' + traceback.format_exc(), exc_info=False)
            self.fleet_carrier_tritium_label.config(text="Tritium: Unknown", foreground="gray", cursor="")
    
    def _on_tritium_click(self):
        """Handle click on Tritium label - only if data is available"""
        if self.fleet_carrier_tritium_label:
            current_fg = self.fleet_carrier_tritium_label.cget('foreground')
            logger.debug(f"[_on_tritium_click] Current foreground color: '{current_fg}'")
            # Allow click if foreground is blue or darkblue (data available), not gray (unknown)
            if current_fg in ('blue', 'darkblue'):
                logger.info("[_on_tritium_click] Opening tritium search on Inara")
                self.find_tritium_near_current_system()
            else:
                logger.debug(f"[_on_tritium_click] Click ignored - foreground is '{current_fg}', not blue/darkblue")
    
    def _on_tritium_enter(self):
        """Handle mouse enter on Tritium label - only if data is available"""
        if self.fleet_carrier_tritium_label:
            # Only show hover effect if foreground is blue (data available), not gray (unknown)
            if self.fleet_carrier_tritium_label.cget('foreground') == 'blue':
                self.fleet_carrier_tritium_label.config(fg="darkblue")
    
    def _on_tritium_leave(self):
        """Handle mouse leave on Tritium label - only if data is available"""
        if self.fleet_carrier_tritium_label:
            # Only restore normal state if foreground was blue (data available), not gray (unknown)
            if self.fleet_carrier_tritium_label.cget('foreground') in ('blue', 'darkblue'):
                self.fleet_carrier_tritium_label.config(fg="blue")
    
    def update_fleet_carrier_balance_display(self):
        """
        Display the credit balance for the selected fleet carrier.
        Reads directly from FleetCarrierManager cache.
        """
        if not hasattr(self, 'fleet_carrier_balance_value') or not self.fleet_carrier_balance_value:
            return
        
        try:
            # If no carrier selected, try to use the most recent one
            callsign = self.selected_carrier_callsign
            
            if not callsign:
                # No selection - try to get most recent carrier
                carriers = self.get_all_fleet_carriers()
                if carriers:
                    sorted_carriers = sorted(carriers, key=lambda x: x.get('last_updated', ''), reverse=True)
                    callsign = sorted_carriers[0].get('callsign', '') if sorted_carriers else None
            
            if not callsign:
                self.fleet_carrier_balance_value.config(text="Unknown", foreground="gray")
                return
            
            # Get carrier data directly from manager
            if self.fleet_carrier_manager:
                carrier = self.fleet_carrier_manager.get_carrier(callsign)
                if carrier:
                    balance_raw = carrier.get('balance', '').strip()
                    if balance_raw:
                        try:
                            balance_int = int(balance_raw)
                            balance_formatted = f"{balance_int:,}"
                            # Always green for valid balance
                            self.fleet_carrier_balance_value.config(text=f"{balance_formatted} cr", foreground="green")
                        except (ValueError, TypeError):
                            self.fleet_carrier_balance_value.config(text=f"{balance_raw} cr", foreground="gray")
                    else:
                        self.fleet_carrier_balance_value.config(text="Unknown", foreground="gray")
                else:
                    self.fleet_carrier_balance_value.config(text="Unknown", foreground="gray")
            else:
                self.fleet_carrier_balance_value.config(text="Unknown", foreground="gray")
        except Exception:
            logger.warning('!! Error updating fleet carrier balance display: ' + traceback.format_exc(), exc_info=False)
            if hasattr(self, 'fleet_carrier_balance_value') and self.fleet_carrier_balance_value:
                self.fleet_carrier_balance_value.config(text="Unknown", foreground="gray")
    
    def show_route_window(self):
        """
        Open a window displaying the current route as an easy-to-read list.
        System names are hyperlinked to Inara.cz.
        Shows all columns based on route type with checkboxes for yes/no fields.
        Highlights the current next waypoint row.
        """
        logger.info(f"[GalaxyGPS.show_route_window] Button clicked! Calling windows.show_route_window()")
        try:
            show_route_window(self)
        except Exception as e:
            logger.error(f"[GalaxyGPS.show_route_window] EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"[GalaxyGPS.show_route_window] TRACEBACK:\n{traceback.format_exc()}")
    
    def refresh_route_window_if_open(self):
        """
        Refresh the route window if it's currently open.
        This is called when the next waypoint changes to update the highlight.
        Uses the seamless refresh from windows.py that preserves scroll position.
        """
        refresh_route_window_if_open(self)
