import ast
import csv
import json
import logging
import math
import os
import re
import subprocess
import sys
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as confirmDialog
import tkinter.ttk as ttk
import traceback
import urllib.parse
import webbrowser
from time import sleep
from tkinter import *

import requests  # type: ignore
from config import appname  # type: ignore
from monitor import monitor  # type: ignore

from . import AutoCompleter, PlaceHolder
from .updater import SpanshUpdater
from .FleetCarrierManager import FleetCarrierManager

# We need a name of plugin dir, not SpanshRouter.py dir
plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
logger = logging.getLogger(f'{appname}.{plugin_name}')


class SpanshRouter():
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
        self.roadtoriches = False
        self.fleetcarrier = False
        self.galaxy = False
        self.next_stop = "No route planned"
        self.route = []
        self.next_wp_label = "Next waypoint: "
        self.jumpcountlbl_txt = "Estimated jumps left: "
        self.bodieslbl_txt = "Bodies to scan at: "
        self.fleetstocklbl_txt = "Warning: Restock Tritium"
        self.refuellbl_txt = "Time to scoop some fuel"
        self.bodies = ""
        self.parent = None
        self.plugin_dir = plugin_dir
        self.save_route_path = os.path.join(plugin_dir, 'route.csv')
        self.export_route_path = os.path.join(plugin_dir, 'Export for TCE.exp')
        self.offset_file_path = os.path.join(plugin_dir, 'offset')
        self.offset = 0
        self.jumps_left = 0
        self.error_txt = tk.StringVar()
        self.plot_error = "Error while trying to plot a route, please try again."
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
            self.fleet_carrier_system_label = None
            self.fleet_carrier_icy_rings_label = None
            self.fleet_carrier_icy_rings_cb = None
            self.fleet_carrier_pristine_label = None
            self.fleet_carrier_pristine_cb = None
            self.fleet_carrier_tritium_label = None
            self.fleet_carrier_balance_label = None
            self.fleet_carrier_separator = None
            
            # Create frame fresh
            self.frame = tk.Frame(parent, borderwidth=2)
            self.frame.grid(sticky=tk.NSEW, columnspan=2)
            
            # Fleet carrier status display (compact, at top)
            # Create all widgets fresh
            self.fleet_carrier_status_label = tk.Label(self.frame, text="Fleet Carrier:")
            self.fleet_carrier_combobox = ttk.Combobox(
                self.frame, 
                textvariable=self.fleet_carrier_var,
                state="readonly",
                width=40
            )
            self.fleet_carrier_combobox.bind("<<ComboboxSelected>>", self.on_carrier_selected)
            self.fleet_carrier_details_btn = tk.Button(
                self.frame, 
                text="View All", 
                command=self.show_carrier_details_window,
                width=8
            )
            self.fleet_carrier_inara_btn = tk.Button(
                self.frame,
                text="Inara",
                command=self.open_selected_carrier_inara,
                width=8,
                fg="blue",
                cursor="hand2",
                state=tk.DISABLED
            )
            self.fleet_carrier_system_label = tk.Label(self.frame, text="System:", foreground="gray")
            # Icy Rings and Pristine status - circular toggle buttons (radio-button style)
            self.fleet_carrier_icy_rings_var = tk.BooleanVar(value=False)
            
            # Icy Rings toggle button
            icy_rings_frame = tk.Frame(self.frame, bg=self.frame.cget('bg'))
            frame_bg = self.frame.cget('bg')
            self.fleet_carrier_icy_rings_canvas = tk.Canvas(
                icy_rings_frame,
                width=20,
                height=20,
                highlightthickness=0,
                bg=frame_bg
            )
            self.fleet_carrier_icy_rings_canvas.pack(side=tk.LEFT, padx=(0, 5))
            # No click binding - read-only display
            self.fleet_carrier_icy_rings_label = tk.Label(
                icy_rings_frame,
                text="Icy Rings:",
                foreground="gray",
                bg=frame_bg
            )
            self.fleet_carrier_icy_rings_label.pack(side=tk.LEFT)
            self.fleet_carrier_icy_rings_cb = icy_rings_frame
            
            # Pristine toggle button
            pristine_frame = tk.Frame(self.frame, bg=frame_bg)
            self.fleet_carrier_pristine_var = tk.BooleanVar(value=False)
            self.fleet_carrier_pristine_canvas = tk.Canvas(
                pristine_frame,
                width=20,
                height=20,
                highlightthickness=0,
                bg=frame_bg
            )
            self.fleet_carrier_pristine_canvas.pack(side=tk.LEFT, padx=(0, 5))
            # No click binding - read-only display
            self.fleet_carrier_pristine_label = tk.Label(
                pristine_frame,
                text="Pristine:",
                foreground="gray",
                bg=frame_bg
            )
            self.fleet_carrier_pristine_label.pack(side=tk.LEFT)
            self.fleet_carrier_pristine_cb = pristine_frame
            self.fleet_carrier_tritium_label = tk.Label(
                self.frame, 
                text="Tritium:", 
                foreground="blue", 
                cursor="hand2"
            )
            self.fleet_carrier_balance_label = tk.Label(self.frame, text="Balance:", foreground="gray")

            # Route info
            self.waypoint_prev_btn = tk.Button(self.frame, text="^", command=self.goto_prev_waypoint)
            self.waypoint_btn = tk.Button(self.frame, text=self.next_wp_label + '\n' + self.next_stop, command=self.copy_waypoint)
            self.waypoint_next_btn = tk.Button(self.frame, text="v", command=self.goto_next_waypoint)
            self.jumpcounttxt_lbl = tk.Label(self.frame, text=self.jumpcountlbl_txt + str(self.jumps_left))
            self.dist_prev_lbl = tk.Label(self.frame, text="")
            self.dist_next_lbl = tk.Label(self.frame, text="")
            self.fuel_used_lbl = tk.Label(self.frame, text="")
            self.dist_remaining_lbl = tk.Label(self.frame, text="")
            self.bodies_lbl = tk.Label(self.frame, justify=LEFT, text=self.bodieslbl_txt + self.bodies)
            self.fleetrestock_lbl = tk.Label(self.frame, justify=LEFT, text=self.fleetstocklbl_txt, fg="red")
            self.find_trit_btn = tk.Button(self.frame, text="Find Trit", command=self.find_tritium_on_inara, width=10)
            self.refuel_lbl = tk.Label(self.frame, justify=LEFT, text=self.refuellbl_txt)
            self.error_lbl = tk.Label(self.frame, textvariable=self.error_txt)

            # Plotting GUI
            self.source_ac = AutoCompleter(self.frame, "Source System", width=30)
            self.dest_ac = AutoCompleter(self.frame, "Destination System", width=30)
            self.range_entry = PlaceHolder(self.frame, "Range (LY)", width=10)
            # Supercharge toggle button - circular radio-button style that toggles like a checkbox
            # Create a frame to hold the toggle button and label
            supercharge_frame = tk.Frame(self.frame, bg=self.frame.cget('bg'))
            # Create a custom toggle button using a canvas to draw a circle
            frame_bg = self.frame.cget('bg')
            self.supercharge_toggle_canvas = tk.Canvas(
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
            
            # Create label for the text
            self.supercharge_label = tk.Label(
                supercharge_frame,
                text="Supercharge",
                foreground="orange",
                font=("TkDefaultFont", 12),
                bg=frame_bg,
                cursor="hand2"
            )
            self.supercharge_label.pack(side=tk.LEFT)
            self.supercharge_label.bind("<Button-1>", self._toggle_supercharge)
            
            # Store reference to the frame for grid positioning
            self.supercharge_cb = supercharge_frame
            
            # Draw the initial circles (unchecked state) - do this after all setup
            # Use after_idle to ensure canvas is ready
            self.frame.after_idle(self._draw_supercharge_toggle)
            self.frame.after_idle(self._draw_icy_rings_toggle)
            self.frame.after_idle(self._draw_pristine_toggle)

            self.efficiency_slider = tk.Scale(self.frame, from_=1, to=100, orient=tk.HORIZONTAL, label="Efficiency (%)")
            self.efficiency_slider.set(60)
            self.plot_gui_btn = tk.Button(self.frame, text="Plot route", command=self.show_plot_gui)
            self.plot_route_btn = tk.Button(self.frame, text="Calculate", command=self.plot_route)
            self.cancel_plot = tk.Button(self.frame, text="Cancel", command=lambda: self.show_plot_gui(False))

            self.csv_route_btn = tk.Button(self.frame, text="Import file", command=self.plot_file)
            self.view_route_btn = tk.Button(self.frame, text="View Route", command=self.show_route_window)
            self.export_route_btn = tk.Button(self.frame, text="Export for TCE", command=self.export_route)
            self.clear_route_btn = tk.Button(self.frame, text="Clear route", command=self.clear_route)

            row = 0
            # Fleet carrier status at the top
            # Store grid positions to prevent accidental repositioning
            self.fleet_carrier_status_label.grid(row=row, column=0, padx=5, pady=2, sticky=tk.W)
            self.fleet_carrier_combobox.grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)
            self.fleet_carrier_details_btn.grid(row=row, column=2, padx=2, pady=2, sticky=tk.W)
            self.fleet_carrier_inara_btn.grid(row=row, column=3, padx=2, pady=2, sticky=tk.W)
            # Store grid info to prevent repositioning
            self._fleet_carrier_row_start = row
            self.update_fleet_carrier_dropdown()
            row += 1
            # Fleet carrier system location
            self.fleet_carrier_system_label.grid(row=row, column=0, columnspan=2, padx=5, pady=2, sticky=tk.W)
            self.update_fleet_carrier_system_display()
            row += 1
            # Fleet carrier Icy Rings and Pristine status
            # Note: icy_rings_cb and pristine_cb are frames containing canvas and label, so grid the frames
            self.fleet_carrier_icy_rings_cb.grid(row=row, column=0, padx=5, pady=2, sticky=tk.W)
            self.fleet_carrier_pristine_cb.grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)
            self.update_fleet_carrier_rings_status()
            row += 1
            # Fleet carrier Tritium display (clickable to search Inara)
            self.fleet_carrier_tritium_label.grid(row=row, column=0, columnspan=2, padx=5, pady=2, sticky=tk.W)
            self.fleet_carrier_tritium_label.bind("<Button-1>", lambda e: self.find_tritium_near_current_system())
            self.fleet_carrier_tritium_label.bind("<Enter>", lambda e, lbl=self.fleet_carrier_tritium_label: lbl.config(fg="darkblue", underline=True))
            self.fleet_carrier_tritium_label.bind("<Leave>", lambda e, lbl=self.fleet_carrier_tritium_label: lbl.config(fg="blue", underline=False))
            self.update_fleet_carrier_tritium_display()
            row += 1
            # Fleet carrier Balance display
            self.fleet_carrier_balance_label.grid(row=row, column=0, columnspan=2, padx=5, pady=2, sticky=tk.W)
            self.update_fleet_carrier_balance_display()
            row += 1
            # Separator line
            self.fleet_carrier_separator = tk.Frame(self.frame, height=1, bg="gray")
            self.fleet_carrier_separator.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=2)
            self._fleet_carrier_row_end = row  # Store end row for fleet carrier section
            row += 1
            # Route waypoint controls
            self.waypoint_prev_btn.grid(row=row, column=0, columnspan=2, padx=5, pady=10)
            self.dist_remaining_lbl.grid(row=row, column=2, padx=5, pady=10, sticky=tk.W)
            row += 1
            self.waypoint_btn.grid(row=row, column=0, columnspan=2, padx=5, pady=10)
            self.dist_prev_lbl.grid(row=row, column=2, padx=5, pady=10, sticky=tk.W)
            row += 1
            self.waypoint_next_btn.grid(row=row, column=0, columnspan=2, padx=5, pady=10)
            self.dist_next_lbl.grid(row=row, column=2, padx=5, pady=10, sticky=tk.W)
            row += 1
            self.fuel_used_lbl.grid(row=row, column=2, padx=5, pady=2, sticky=tk.W)
            row += 1
            self.bodies_lbl.grid(row=row, columnspan=2, sticky=tk.W)
            row += 1
            self.fleetrestock_lbl.grid(row=row, column=0, sticky=tk.W)
            self.find_trit_btn.grid(row=row, column=1, padx=5, sticky=tk.W)
            row += 1
            self.refuel_lbl.grid(row=row,columnspan=2, sticky=tk.W)
            row += 1
            self.source_ac.grid(row=row,columnspan=2, pady=(10,0)) # The AutoCompleter takes two rows to show the list when needed, so we skip one
            row += 2
            self.dest_ac.grid(row=row,columnspan=2, pady=(10,0))
            row += 2
            self.range_entry.grid(row=row, column=0, pady=10, sticky=tk.W)
            self.supercharge_cb.grid(row=row, column=1, padx=10, pady=10, sticky=tk.W)
            row += 1
            self.efficiency_slider.grid(row=row, pady=10, columnspan=2, sticky=tk.EW)
            row += 1
            # Basic controls - always visible, positioned in sequential columns
            self.csv_route_btn.grid(row=row, column=0, pady=10, padx=0)
            self.view_route_btn.grid(row=row, column=1, pady=10, padx=0)
            self.plot_gui_btn.grid(row=row, column=2, pady=10, padx=0)
            # Plotting controls - shown/hidden based on state
            self.plot_route_btn.grid(row=row, column=0, pady=10, padx=0)
            self.cancel_plot.grid(row=row, column=1, pady=10, padx=5, sticky=tk.E)
            row += 1
            self.export_route_btn.grid(row=row, pady=10, padx=0)
            self.clear_route_btn.grid(row=row, column=1, pady=10, padx=5, sticky=tk.W)
            row += 1
            self.jumpcounttxt_lbl.grid(row=row, pady=5, sticky=tk.W)
            row += 1
            self.error_lbl.grid(row=row, columnspan=2)
            self.error_lbl.grid_remove()
            row += 1

            # Check if we're having a valid range on the fly
            self.range_entry.var.trace('w', self.check_range)

            # Initialize GUI to appropriate state
            self.update_gui()
            
            # Mark GUI as initialized
            self._gui_initialized = True

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
        Shows filled circle when checked, empty circle when unchecked.
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
            self.fleet_carrier_icy_rings_canvas.create_oval(
                2, 2, 18, 18,
                outline="gray",
                width=2,
                fill=bg_color if not is_checked else "gray"
            )
            
            # If checked, draw inner filled circle
            if is_checked:
                self.fleet_carrier_icy_rings_canvas.create_oval(
                    6, 6, 14, 14,
                    outline="gray",
                    fill="gray",
                    width=1
                )
        except Exception:
            pass
    
    def _draw_pristine_toggle(self):
        """
        Draw the circular toggle button for Pristine (read-only display).
        Shows filled circle when checked, empty circle when unchecked.
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
            self.fleet_carrier_pristine_canvas.create_oval(
                2, 2, 18, 18,
                outline="gray",
                width=2,
                fill=bg_color if not is_checked else "gray"
            )
            
            # If checked, draw inner filled circle
            if is_checked:
                self.fleet_carrier_pristine_canvas.create_oval(
                    6, 6, 14, 14,
                    outline="gray",
                    fill="gray",
                    width=1
                )
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
            self.jumpcounttxt_lbl, self.export_route_btn, self.clear_route_btn,
            self.dist_prev_lbl, self.dist_next_lbl, self.fuel_used_lbl, self.dist_remaining_lbl
        ]
        
        plotting_widgets = [
            self.source_ac, self.dest_ac, self.range_entry,
            self.supercharge_cb, self.efficiency_slider,
            self.plot_route_btn, self.cancel_plot
        ]
        
        basic_controls = [
            self.plot_gui_btn, self.csv_route_btn, self.view_route_btn
        ]
        
        info_labels = [
            self.bodies_lbl, self.fleetrestock_lbl, self.refuel_lbl, self.find_trit_btn
        ]
        
        # Hide all widgets first (except fleet carrier status and basic controls which are always visible)
        # Fleet carrier widgets should never be hidden or repositioned
        fleet_carrier_widgets = [
            self.fleet_carrier_status_label, self.fleet_carrier_combobox, 
            self.fleet_carrier_details_btn, self.fleet_carrier_inara_btn, 
            self.fleet_carrier_system_label, self.fleet_carrier_icy_rings_label, 
            self.fleet_carrier_icy_rings_cb, self.fleet_carrier_pristine_label, 
            self.fleet_carrier_pristine_cb, self.fleet_carrier_tritium_label, 
            self.fleet_carrier_balance_label
        ]
        
        # Also include the separator in the always-visible list
        if hasattr(self, 'fleet_carrier_separator'):
            fleet_carrier_widgets.append(self.fleet_carrier_separator)
        
        # Basic controls should also always be visible (they're positioned in init_gui)
        always_visible = fleet_carrier_widgets + basic_controls
        
        for widget in route_widgets + plotting_widgets + info_labels:
            if widget not in always_visible:
                widget.grid_remove()
        
        # Show widgets based on state
        if state == 'plotting':
            # Show plotting interface
            # IMPORTANT: Only call grid() on widgets that were grid_remove()d
            # Never call grid() on fleet carrier widgets - they're always visible
            for widget in plotting_widgets:
                if widget not in always_visible:
                    widget.grid()
            # Prefill source if needed
            if not self.source_ac.var.get() or self.source_ac.var.get() == self.source_ac.placeholder:
                current_system = monitor.state.get('SystemName')
                if current_system:
                    self.source_ac.set_text(current_system, placeholder_style=False)
                else:
                    self.source_ac.put_placeholder()
        elif state == 'route' and len(self.route) > 0:
            # Show route navigation interface
            # IMPORTANT: Only call grid() on widgets that were grid_remove()d
            # Never call grid() on fleet carrier widgets - they're always visible
            for widget in route_widgets:
                if widget not in always_visible:
                    widget.grid()
            
            # Update waypoint button text
            self.waypoint_btn["text"] = self.next_wp_label + '\n' + self.next_stop
            
            # Update distance labels
            if self.jumps_left > 0:
                self.jumpcounttxt_lbl["text"] = self.jumpcountlbl_txt + str(self.jumps_left)
                self.dist_prev_lbl["text"] = self.dist_prev
                self.dist_next_lbl["text"] = self.dist_next
                self.dist_remaining_lbl["text"] = self.dist_remaining
                # Update fuel used display (only if CSV has this column)
                if self.has_fuel_used and self.fuel_used:
                    self.fuel_used_lbl["text"] = f"Fuel Used: {self.fuel_used}"
                    self.fuel_used_lbl.grid()
                else:
                    self.fuel_used_lbl.grid_remove()
            else:
                self.jumpcounttxt_lbl.grid_remove()
                self.dist_prev_lbl.grid_remove()
                self.dist_next_lbl.grid_remove()
                self.fuel_used_lbl.grid_remove()
                self.dist_remaining_lbl.grid_remove()
            
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
        
        # Always ensure basic controls are visible
        # These widgets should always be visible regardless of state
        # They're positioned in init_gui() and should never be grid_remove()d
        # Explicitly ensure they're shown (in case they were accidentally hidden)
        for widget in basic_controls:
            if widget:
                try:
                    # Ensure widget is visible - grid() will restore it if it was grid_remove()d
                    # Tkinter remembers the original grid position when grid_remove() is called
                    widget.grid()
                except Exception:
                    pass

    def update_gui(self):
        """Update the GUI based on current state"""
        if len(self.route) > 0:
            self._update_widget_visibility('route')
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
            self.plot_route_btn.config(state=tk.NORMAL, text="Calculate")
            self.plot_route_btn.update_idletasks()
            self.cancel_plot.config(state=tk.NORMAL)
            self.cancel_plot.update_idletasks()
            self.supercharge_cb.config(state=tk.NORMAL)
            self.supercharge_cb.update_idletasks()
        else:
            self.source_ac.config(state=tk.DISABLED)
            self.source_ac.update_idletasks()
            self.dest_ac.config(state=tk.DISABLED)
            self.dest_ac.update_idletasks()
            self.efficiency_slider.config(state=tk.DISABLED)
            self.efficiency_slider.update_idletasks()
            self.range_entry.config(state=tk.DISABLED)
            self.range_entry.update_idletasks()
            self.plot_route_btn.config(state=tk.DISABLED, text="Computing...")
            self.plot_route_btn.update_idletasks()
            self.cancel_plot.config(state=tk.DISABLED)
            self.cancel_plot.update_idletasks()
            self.supercharge_cb.config(state=tk.DISABLED)
            self.supercharge_cb.update_idletasks()

    #   -- END GUI part --


    def open_last_route(self):
        try:
            has_headers = False
            with open(self.save_route_path, 'r', newline='') as csvfile:
                # Check if the file has a header for compatibility with previous versions
                dict_route_reader = csv.DictReader(csvfile)
                if dict_route_reader.fieldnames[0] == self.system_header:
                    has_headers = True

            if has_headers:
                self.plot_csv(self.save_route_path, clear_previous_route=False)
            else:
                with open(self.save_route_path, 'r', newline='') as csvfile:
                    route_reader = csv.reader(csvfile)

                    for row in route_reader:
                        if row not in (None, "", []):
                            self.route.append(row)

            try:
                with open(self.offset_file_path, 'r') as offset_fh:
                    self.offset = int(offset_fh.readline())

            except (IOError, OSError, ValueError):
                self.offset = 0

            self.jumps_left = 0
            for row in self.route[self.offset:]:
                if row[1] not in [None, "", []]:
                    if not self.galaxy: # galaxy type doesn't have a jumps column

                        self.jumps_left += int(row[1])
                    else:
                        self.jumps_left += 1
                    

            self.next_stop = self.route[self.offset][0]
            self.update_bodies_text()
            self.compute_distances()
            self.copy_waypoint()
            self.update_gui()

        except IOError:
            logger.info("No previously saved route")
        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)

    def copy_waypoint(self):
        if sys.platform == "linux":
            clipboard_cli = os.getenv("EDMC_SPANSH_ROUTER_XCLIP") or "xclip -selection c"
            clipboard_cli = clipboard_cli.split()
            command = subprocess.Popen(["echo", "-n", self.next_stop], stdout=subprocess.PIPE)
            subprocess.Popen(clipboard_cli, stdin=command.stdout)
        else:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(self.next_stop)
            self.parent.update()

    def goto_next_waypoint(self):
        # allow manual navigation even if offset wasn't set by journal events yet
        if len(self.route) == 0:
            return

        if not hasattr(self, "offset") or self.offset is None:
            self.offset = 0

        if self.offset < len(self.route) - 1:
            self.update_route(1)

    def goto_prev_waypoint(self):
        # allow manual navigation even if offset wasn't set by journal events yet
        if len(self.route) == 0:
            return

        if not hasattr(self, "offset") or self.offset is None:
            self.offset = 0

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

        # --- LY from previous ---
        # If current row has distance_to_arrival (index >=3? actually index 2 zero-based),
        # that's the distance from previous -> current.
        if len(cur) >= 3:
            pv = safe_flt(cur[2])
            if pv is not None:
                self.dist_prev = f"Jump LY: {pv:.2f}"
            else:
                # fallback: try jumps value (index 1)
                pv2 = safe_flt(cur[1])
                if pv2 is not None:
                    self.dist_prev = f"Number of Jumps: {pv2:.2f}"
        else:
            # no explicit distance columns — try best-effort from jumps on prev row
            if self.offset > 0:
                prev = self.route[self.offset - 1]
                pj = safe_flt(prev[1])
                if pj is not None:
                    self.dist_prev = f"Number of Jumps: {pj:.2f}"
                else:
                    self.dist_prev = "Start of the journey"
            else:
                self.dist_prev = "Start of the journey"

        # --- LY to next ---
        if self.offset < len(self.route) - 1:
            nxt = self.route[self.offset + 1]
            # prefer distance_to_arrival on the NEXT row (distance from current -> next)
            if len(nxt) >= 3:
                nv = safe_flt(nxt[2])
                if nv is not None:
                    self.dist_next = f"Next jump LY: {nv:.2f}"
                else:
                    nv2 = safe_flt(nxt[1])
                    if nv2 is not None:
                        self.dist_next = f"Next waypoint jumps: {nv2:.2f}"
            else:
                nv2 = safe_flt(nxt[1])
                if nv2 is not None:
                    self.dist_next = f"Next waypoint jumps: {nv2:.2f}"
            
            # Extract Fuel Used from next waypoint if available
            # For fleet carrier routes with has_fuel_used: [System, Jumps, Dist, Dist Rem, Restock Trit, Fuel Used, ...]
            #   Fuel Used is at index 5
            # For galaxy routes with has_fuel_used: [System, Refuel, Dist, Dist Rem, Fuel Used, ...]
            #   Fuel Used is at index 4
            # For generic routes with has_fuel_used: [System, Jumps, Fuel Used, ...]
            #   Fuel Used is at index 2
            if self.has_fuel_used:
                fuel_used_value = None
                if self.fleetcarrier and len(nxt) > 5:
                    # Fleet carrier: Fuel Used is at index 5 (after System, Jumps, Dist, Dist Rem, Restock Trit)
                    fuel_used_value = nxt[5] if nxt[5] else None
                elif self.galaxy and len(nxt) > 4:
                    # Galaxy route: Fuel Used is at index 4 (after System, Refuel, Dist, Dist Rem)
                    fuel_used_value = nxt[4] if nxt[4] else None
                else:
                    # Generic route: Fuel Used might be at index 2 (after System, Jumps)
                    if len(nxt) > 2:
                        fuel_used_value = nxt[2] if nxt[2] else None
                
                if fuel_used_value and fuel_used_value.strip():
                    self.fuel_used = fuel_used_value.strip()
                else:
                    self.fuel_used = ""
        else:
            self.dist_next = ""
            self.fuel_used = ""

        # --- Total remaining ---
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
            self.dist_remaining = f"LY afterwards: {total_rem:.2f}"
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
                self.dist_remaining = f"Remaining jumps afterwards: {s:.2f}"
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
            waypoint_system = waypoint[0] if waypoint and len(waypoint) > 0 else ""
            if waypoint_system and waypoint_system.lower() == current_system_lower:
                # Found a match - we're at this waypoint
                found_index = idx
        
        if found_index >= 0:
            # We're at a waypoint - advance to the next one
            next_index = found_index + 1
            if next_index >= len(self.route):
                # We're at the last waypoint, stay there
                next_index = len(self.route) - 1
            
            # Update jumps_left to account for skipping waypoints we've already passed
            for idx in range(next_index):
                if idx < len(self.route) and len(self.route[idx]) > 1:
                    if self.route[idx][1] not in [None, "", []]:
                        try:
                            if not self.galaxy:
                                self.jumps_left -= int(self.route[idx][1])
                            else:
                                self.jumps_left -= 1
                        except (ValueError, TypeError):
                            pass
            
            return next_index
        else:
            # Not at any waypoint - check if we're between waypoints
            # For now, default to starting from the beginning
            # Could enhance this later to check distance to nearest waypoint
            return 0
    
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
        if self.offset < 0:
            self.offset = 0
        if self.offset >= len(self.route):
            self.offset = len(self.route) - 1

        try:
            if direction > 0:
                # subtract jumps for current offset (if present) then advance
                if self.route[self.offset][1] not in [None, "", []]:
                    if not self.galaxy:
                        self.jumps_left -= int(self.route[self.offset][1])
                    else:
                        self.jumps_left -= 1
                # advance but clamp
                if self.offset < len(self.route) - 1:
                    self.offset += 1
            else:
                # move back, but avoid negative indexes
                if self.offset > 0:
                    self.offset -= 1
                    if self.route[self.offset][1] not in [None, "", []]:
                        if not self.galaxy:
                            self.jumps_left += int(self.route[self.offset][1])
                        else:
                            self.jumps_left += 1
        except Exception:
            # If something odd in route contents, try to recover by resetting offset to 0
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)
            self.offset = max(0, min(self.offset, len(self.route) - 1))

        # Now update next_stop and GUI according to new offset
        if self.offset >= len(self.route):
            self.next_stop = "End of the road!"
            self.update_gui()
        else:
            self.next_stop = self.route[self.offset][0]
            self.update_bodies_text()
            self.compute_distances()

            if self.galaxy:
                self.pleaserefuel = self.route[self.offset][1] == "Yes"
            
            # Update fleet carrier restock warning when route changes
            if self.fleetcarrier:
                self.check_fleet_carrier_restock_warning()

            self.update_gui()
            self.copy_waypoint()

        self.save_offset()

    def goto_changelog_page(self):
        changelog_url = 'https://github.com/CMDR-Kiel42/EDMC_SpanshRouter/blob/master/CHANGELOG.md#'
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

            if clear_previous_route:
                self.clear_route(False)
                self.has_fuel_used = False  # Reset flag when clearing route

            route_reader = csv.DictReader(csvfile)
            fieldnames = route_reader.fieldnames if route_reader.fieldnames else []
            
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
            internalfleetcarrierheader_with_distances = "System Name,Jumps,Distance To Arrival,Distance Remaining,Restock Tritium"
            internalfleetcarrierheader = "System Name,Jumps,Restock Tritium"
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
                for row in route_reader:
                    if row not in (None, "", []):
                        dist_to_arrival, dist_remaining = get_distance_fields(row)
                        self.route.append([
                            get_field(row, self.system_header),
                            get_field(row, self.jumps_header, ""),
                            dist_to_arrival,
                            dist_remaining
                        ])
                        try:
                            jumps_val = get_field(row, self.jumps_header, "0")
                            self.jumps_left += int(jumps_val)
                        except (ValueError, TypeError):
                            pass

            # --- simple internal ---
            elif headerline_lower in (internalbasicheader1.lower(), internalbasicheader2.lower()):
                for row in route_reader:
                    if row not in (None, "", []):
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

                for row in route_reader:
                    if row not in (None, "", []):
                        dist_to_arrival, dist_remaining = get_distance_fields(row)
                        self.route.append([
                            get_field(row, self.system_header),
                            get_field(row, self.jumps_header),
                            dist_to_arrival,
                            dist_remaining,
                            get_field(row, self.restocktritium_header, "")
                        ])
                        try:
                            jumps_val = get_field(row, self.jumps_header, "0")
                            self.jumps_left += int(jumps_val)
                        except (ValueError, TypeError):
                            pass

            # --- internal fleetcarrier (legacy, no distances) ---
            elif headerline_lower == internalfleetcarrierheader.lower():
                self.fleetcarrier = True

                for row in route_reader:
                    if row not in (None, "", []):
                        self.route.append([
                            get_field(row, self.system_header),
                            get_field(row, self.jumps_header),
                            get_field(row, self.restocktritium_header)
                        ])
                        try:
                            jumps_val = get_field(row, self.jumps_header, "0")
                            self.jumps_left += int(jumps_val)
                        except (ValueError, TypeError):
                            pass

            # --- EXTERNAL fleetcarrier import (WITH LY SUPPORT) ---
            elif headerline_lower == fleetcarrierimportheader.lower():
                self.fleetcarrier = True
                self.has_fuel_used = has_field('Fuel Used')

                for row in route_reader:
                    if row not in (None, "", []):
                        dist_to_arrival, dist_remaining = get_distance_fields(row)

                        route_entry = [
                            get_field(row, self.system_header),
                            1,  # every row = one carrier jump
                            dist_to_arrival,
                            dist_remaining,
                            get_field(row, self.restocktritium_header, "")
                        ]
                        # Store Fuel Used if present
                        if self.has_fuel_used:
                            route_entry.append(get_field(row, 'Fuel Used', ''))
                        # Store Icy Ring and Pristine if present (for route view window)
                        if has_field('Icy Ring'):
                            route_entry.append(get_field(row, 'Icy Ring', ''))
                        if has_field('Pristine'):
                            route_entry.append(get_field(row, 'Pristine', ''))
                        
                        self.route.append(route_entry)
                        self.jumps_left += 1

            # --- galaxy ---
            elif has_field("Refuel") and has_field(self.system_header):
                self.galaxy = True
                self.has_fuel_used = has_field('Fuel Used')

                for row in route_reader:
                    if row not in (None, "", []):
                        dist_to_arrival, dist_remaining = get_distance_fields(row)

                        route_row = [
                            get_field(row, self.system_header, ""),
                            get_field(row, self.refuel_header, "")
                        ]

                        if dist_to_arrival or dist_remaining:
                            route_row.append(dist_to_arrival)
                            route_row.append(dist_remaining)
                        
                        # Store Fuel Used if present (typically after Fuel Left)
                        if self.has_fuel_used:
                            route_row.append(get_field(row, 'Fuel Used', ''))

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
                        system = get_field(row, self.system_header, "")
                        jumps = get_field(row, self.jumps_header, "")
                        route_entry = [system, jumps]
                        
                        # Add Fuel Used if present (before Icy Ring/Pristine to maintain consistent order)
                        if self.has_fuel_used:
                            route_entry.append(get_field(row, 'Fuel Used', ''))
                        
                        # Add Icy Ring and Pristine if present
                        if has_icy_ring_in_file:
                            route_entry.append(get_field(row, 'Icy Ring', ''))
                        if has_pristine_in_file:
                            route_entry.append(get_field(row, 'Pristine', ''))
                        
                        self.route.append(route_entry)
                        try:
                            self.jumps_left += int(jumps) if jumps else 0
                        except (ValueError, TypeError):
                            pass

            if self.route:
                # Find where we are in the route based on current system location
                self.offset = self.find_current_waypoint_in_route()
                
                self.next_stop = self.route[self.offset][0]
                self.compute_distances()
                self.update_gui()
                # Check fleet carrier restock warning
                if self.fleetcarrier and hasattr(self, 'check_fleet_carrier_restock_warning'):
                    self.check_fleet_carrier_restock_warning()

    def plot_route(self):
        self.hide_error()
        try:
            source = self.source_ac.get().strip()
            dest = self.dest_ac.get().strip()
            efficiency = self.efficiency_slider.get()

            # Hide autocomplete lists
            self.source_ac.hide_list()
            self.dest_ac.hide_list()

            # Validate inputs
            if not source or source == self.source_ac.placeholder:
                self.show_error("Please provide a starting system.")
                return
            if not dest or dest == self.dest_ac.placeholder:
                self.show_error("Please provide a destination system.")
                return

            # Range
            try:
                range_ly = float(self.range_entry.get())
            except ValueError:
                self.show_error("Invalid range")
                return

            job_url = "https://spansh.co.uk/api/route?"

            # Submit plot request
            try:
                supercharge_multiplier = 6 if self.supercharge_overcharge.get() else 4

                results = requests.post(
                    job_url,
                    params={
                        "efficiency": efficiency,
                        "range": range_ly,
                        "from": source,
                        "to": dest,
                        # Spansh neutron routing:
                        # 4 = normal supercharge
                        # 6 = overcharge supercharge
                        "supercharge_multiplier": supercharge_multiplier
                    },
                    headers={'User-Agent': "EDMC_SpanshRouter 1.0"}
                )
            except Exception as e:
                logger.warning(f"Failed to submit route query: {e}")
                self.show_error(self.plot_error)
                return

            # Spansh returned immediate error
            if results.status_code != 202:
                logger.warning(
                    f"Failed to query plotted route from Spansh: "
                    f"{results.status_code}; text: {results.text}"
                )

                try:
                    failure = json.loads(results.content)
                except (json.JSONDecodeError, ValueError):
                    failure = {}

                if results.status_code == 400 and "error" in failure:
                    self.show_error(failure["error"])
                    if "starting system" in failure["error"]:
                        self.source_ac["fg"] = "red"
                    if "finishing system" in failure["error"]:
                        self.dest_ac["fg"] = "red"
                else:
                    self.show_error(self.plot_error)
                return

            # Otherwise: accepted, poll job state
            self.enable_plot_gui(False)
            response = json.loads(results.content)
            job = response.get("job")
            tries = 0
            route_response = None

            while tries < 20:
                results_url = f"https://spansh.co.uk/api/results/{job}"

                try:
                    route_response = requests.get(results_url, timeout=5)
                except (requests.RequestException, requests.Timeout):
                    route_response = None
                    break

                if route_response.status_code != 202:
                    break

                tries += 1
                sleep(1)

            # Did we get a real final response?
            if not route_response:
                logger.warning("Query to Spansh timed out")
                self.enable_plot_gui(True)
                self.show_error("The query to Spansh timed out. Please try again.")
                return

            # Final response OK
            if route_response.status_code == 200:
                try:
                    route = json.loads(route_response.content)["result"]["system_jumps"]
                except Exception as e:
                    logger.warning(f"Invalid data from Spansh: {e}")
                    self.enable_plot_gui(True)
                    self.show_error(self.plot_error)
                    return

                # Clear previous route silently
                self.clear_route(show_dialog=False)

                # Fill route with distance-aware entries (API plot)
                for waypoint in route:
                    system = waypoint.get("system", "")
                    jumps = waypoint.get("jumps", 0)

                    # Map API distance fields to internal format
                    distance_to_arrival = waypoint.get("distance_jumped", "")
                    distance_remaining = waypoint.get("distance_left", "")

                    self.route.append([
                        system,
                        str(jumps),
                        distance_to_arrival,
                        distance_remaining
                    ])

                    try:
                        self.jumps_left += int(jumps)
                    except (ValueError, TypeError):
                        pass

                self.enable_plot_gui(True)
                self.show_plot_gui(False)

                # Compute offset
                current_system = monitor.state.get('SystemName')
                self.offset = (
                    1
                    if self.route and current_system and self.route[0][0].lower() == current_system.lower()
                    else 0
                )
                self.next_stop = self.route[self.offset][0] if self.route else ""

                # Update GUI and persist
                self.compute_distances()
                self.copy_waypoint()
                self.update_gui()
                # Check fleet carrier restock warning
                if self.fleetcarrier and hasattr(self, 'check_fleet_carrier_restock_warning'):
                    self.check_fleet_carrier_restock_warning()
                self.save_all_route()
                return

            # Otherwise: Spansh error on final poll
            logger.warning(
                f"Failed final route fetch: {route_response.status_code}; "
                f"text: {route_response.text}"
            )

            try:
                failure = json.loads(results.content)
            except (json.JSONDecodeError, ValueError):
                failure = {}

            self.enable_plot_gui(True)
            if route_response.status_code == 400 and "error" in failure:
                self.show_error(failure["error"])
                if "starting system" in failure["error"]:
                    self.source_ac["fg"] = "red"
                if "finishing system" in failure["error"]:
                    self.dest_ac["fg"] = "red"
            else:
                self.show_error(self.plot_error)

        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)
            self.enable_plot_gui(True)
            self.show_error(self.plot_error)

    def plot_edts(self, filename):
        try:
            with open(filename, 'r') as txtfile:
                route_txt = txtfile.readlines()
                self.clear_route(False)
                for row in route_txt:
                    if row not in (None, "", []):
                        if row.lstrip().startswith('==='):
                            jumps = int(re.findall("\d+ jump", row)[0].rstrip(' jumps'))
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
            logger.info("No route to export")
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
        clear = confirmDialog.askyesno("SpanshRouter","Are you sure you want to clear the current route?") if show_dialog else True

        if clear:
            self.offset = 0
            self.route = []
            self.next_waypoint = ""
            self.jumps_left = 0
            self.roadtoriches = False
            self.fleetcarrier = False
            self.galaxy = False
            try:
                os.remove(self.save_route_path)
            except (IOError, OSError):
                logger.info("No route to delete")
            try:
                os.remove(self.offset_file_path)
            except (IOError, OSError):
                logger.info("No offset file to delete")

            self.update_gui()

    def save_all_route(self):
        self.save_route()
        self.save_offset()

    def save_route(self):
        if len(self.route) == 0:
            try:
                os.remove(self.save_route_path)
            except (IOError, OSError):
                pass
            return

        try:
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

            # --- Generic with distances ---
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
                logger.info("No offset to delete")

    def update_bodies_text(self):
        if not self.roadtoriches: return

        # For the bodies to scan use the current system, which is one before the next stop
        lastsystemoffset = self.offset - 1
        if lastsystemoffset < 0:
            lastsystemoffset = 0 # Display bodies of the first system

        lastsystem = self.route[lastsystemoffset][0]
        bodynames = self.route[lastsystemoffset][2]
        bodysubtypes = self.route[lastsystemoffset][3]
     
        waterbodies = []
        rockybodies = []
        metalbodies = []
        earthlikebodies = []
        unknownbodies = []

        for num, name in enumerate(bodysubtypes):
            shortbodyname = bodynames[num].replace(lastsystem + " ", "")
            if name.lower() == "high metal content world":
                metalbodies.append(shortbodyname)
            elif name.lower() == "rocky body": 
                rockybodies.append(shortbodyname)
            elif name.lower() == "earth-like world":
                earthlikebodies.append(shortbodyname)
            elif name.lower() == "water world": 
                waterbodies.append(shortbodyname)
            else:
                unknownbodies.append(shortbodyname)

        bodysubtypeandname = ""
        if len(metalbodies) > 0: bodysubtypeandname += f"\n   Metal: " + ', '.join(metalbodies)
        if len(rockybodies) > 0: bodysubtypeandname += f"\n   Rocky: " + ', '.join(rockybodies)
        if len(earthlikebodies) > 0: bodysubtypeandname += f"\n   Earth: " + ', '.join(earthlikebodies)
        if len(waterbodies) > 0: bodysubtypeandname += f"\n   Water: " + ', '.join(waterbodies)
        if len(unknownbodies) > 0: bodysubtypeandname += f"\n   Unknown: " + ', '.join(unknownbodies)

        self.bodies = f"\n{lastsystem}:{bodysubtypeandname}"


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
            and os.path.exists(os.path.join(self.plugin_dir, "SpanshRouter"))):
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
        github_repo = "Fenris159/EDMC_SpanshRouter"  # Format: "username/repository"
        github_branch = "master"  # Your default branch name (master, main, etc.)
        
        self.cleanup_old_version()
        version_url = f"https://raw.githubusercontent.com/{github_repo}/{github_branch}/version.json"
        try:
            response = requests.get(version_url, timeout=2)
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
                logger.warning(f"Could not query latest SpanshRouter version, code: {str(response.status_code)}; text: {response.text}")
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
    
    def get_fleet_carriers_in_system(self, system_name: str):
        """
        Get all fleet carriers in a specific system.
        
        Args:
            system_name: System name to search for
            
        Returns:
            List of carrier dictionaries in that system
        """
        if self.fleet_carrier_manager:
            return self.fleet_carrier_manager.get_carrier_by_system(system_name)
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
                if carrier_options and not self.selected_carrier_callsign:
                    self.fleet_carrier_combobox.current(0)
                    self.on_carrier_selected()
                    # Enable Inara button if carrier is selected
                    if self.fleet_carrier_inara_btn:
                        self.fleet_carrier_inara_btn.config(state=tk.NORMAL)
            else:
                self.fleet_carrier_combobox['values'] = ["No carrier data"]
                self.fleet_carrier_combobox.current(0)
                # Disable Inara button if no carrier data
                if self.fleet_carrier_inara_btn:
                    self.fleet_carrier_inara_btn.config(state=tk.DISABLED)
        except Exception:
            logger.warning('!! Error updating fleet carrier dropdown: ' + traceback.format_exc(), exc_info=False)
            self.fleet_carrier_combobox['values'] = ["Error loading carrier data"]
    
    def on_carrier_selected(self, event=None):
        """
        Handle carrier selection from dropdown.
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
    
    def open_selected_carrier_inara(self):
        """
        Open Inara.cz page for the currently selected fleet carrier in the dropdown.
        """
        try:
            if not self.selected_carrier_callsign:
                confirmDialog.showwarning("No Carrier Selected", "Please select a fleet carrier first.")
                return
            
            self.open_inara_carrier(self.selected_carrier_callsign)
        except Exception:
            logger.warning('!! Error opening selected carrier Inara page: ' + traceback.format_exc(), exc_info=False)
            confirmDialog.showerror("Error", "Failed to open Inara page.")
    
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
            carriers = self.get_all_fleet_carriers()
            if not carriers:
                confirmDialog.showinfo("Fleet Carriers", "No fleet carrier data available.")
                return
            
            # Create new window
            details_window = tk.Toplevel(self.parent)
            details_window.title("Fleet Carrier Details")
            
            # Define headers and column widths first
            headers = ["Select", "Callsign", "Name", "System", "Tritium", "Balance", "Cargo", "State", "Theme", "Icy Rings", "Pristine", "Docking Access", "Notorious Access", "Last Updated"]
            column_widths = [8, 12, 20, 20, 15, 15, 20, 15, 15, 12, 12, 15, 18, 20]
            
            # Calculate required width based on columns
            # More accurate estimate: column_widths * 8-10 pixels per character + padding + separators
            # Account for separators (one between each column, ~2px each)
            num_separators = len(headers) - 1
            separator_width = num_separators * 2
            # Use 9 pixels per character width for more accurate sizing
            total_column_width = sum(column_widths) * 9 + separator_width + 200  # Add padding for buttons/scrollbars/margins
            screen_width = details_window.winfo_screenwidth()
            # Open window wide enough to show all columns, but don't exceed screen width
            # If content is wider than screen, user can scroll horizontally
            window_width = min(total_column_width, screen_width - 20)  # Leave small margin from screen edges
            # Ensure minimum width so content isn't cut off
            window_width = max(window_width, 800)  # At least 800px wide
            
            # Create main container with horizontal and vertical scrolling
            main_frame = tk.Frame(details_window, bg="white")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Create horizontal scrollbar
            h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL)
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            
            # Create vertical scrollbar
            v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL)
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Create canvas with both scrollbars
            canvas = tk.Canvas(main_frame, bg="white", 
                             xscrollcommand=h_scrollbar.set,
                             yscrollcommand=v_scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            h_scrollbar.config(command=canvas.xview)
            v_scrollbar.config(command=canvas.yview)
            
            scrollable_frame = tk.Frame(canvas, bg="white")
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            
            # Update canvas scroll region when frame size changes
            def on_frame_configure(event):
                canvas.configure(scrollregion=canvas.bbox("all"))
                # Update canvas window width to match canvas width for proper horizontal scrolling
                canvas_width = canvas.winfo_width()
                if canvas_width > 1:  # Only update if canvas has been rendered
                    canvas_window_id = canvas.find_all()
                    if canvas_window_id:
                        canvas.itemconfig(canvas_window_id[0], width=canvas_width)
            
            scrollable_frame.bind("<Configure>", on_frame_configure)
            
            # Also bind to canvas resize
            def on_canvas_configure(event):
                canvas_width = event.width
                canvas_window_id = canvas.find_all()
                if canvas_window_id:
                    canvas.itemconfig(canvas_window_id[0], width=canvas_width)
            
            canvas.bind('<Configure>', on_canvas_configure)
            
            # Header
            header_frame = tk.Frame(scrollable_frame, bg="lightgray", relief=tk.RAISED, borderwidth=1)
            header_frame.pack(fill=tk.X, padx=5, pady=5)
            for i, header in enumerate(headers):
                label = tk.Label(header_frame, text=header, font=("Arial", 9, "bold"), bg="lightgray", width=column_widths[i])
                label.grid(row=0, column=i*2, padx=2, pady=5, sticky=tk.W)
                # Add vertical separator after each column (except the last)
                if i < len(headers) - 1:
                    separator = ttk.Separator(header_frame, orient=tk.VERTICAL)
                    separator.grid(row=0, column=i*2+1, padx=0, pady=2, sticky=tk.NS)
            
            # Carrier rows
            for idx, carrier in enumerate(sorted(carriers, key=lambda x: x.get('last_updated', ''), reverse=True)):
                row_frame = tk.Frame(scrollable_frame, relief=tk.RIDGE, borderwidth=1)
                row_frame.pack(fill=tk.X, padx=5, pady=2)
                
                callsign = carrier.get('callsign', 'Unknown')
                name = carrier.get('name', '') or 'Unnamed'
                system = carrier.get('current_system', 'Unknown')
                fuel = carrier.get('fuel', '0')
                tritium_cargo = carrier.get('tritium_in_cargo', '0')
                balance = carrier.get('balance', '0')
                cargo_count = carrier.get('cargo_count', '0')
                cargo_value = carrier.get('cargo_total_value', '0')
                state = carrier.get('state', 'Unknown')
                theme = carrier.get('theme', 'Unknown')
                icy_rings = carrier.get('icy_rings', '')
                pristine = carrier.get('pristine', '')
                docking_access = carrier.get('docking_access', '')
                notorious_access = carrier.get('notorious_access', '')
                last_updated = carrier.get('last_updated', 'Unknown')
                
                # Format balance and cargo value
                try:
                    balance_formatted = f"{int(balance):,}" if balance else "0"
                    cargo_value_formatted = f"{int(cargo_value):,}" if cargo_value else "0"
                except (ValueError, TypeError):
                    balance_formatted = balance
                    cargo_value_formatted = cargo_value
                
                cargo_text = f"{cargo_count} ({cargo_value_formatted} cr)"
                
                # Format Tritium: fuel / cargo (or just fuel if no cargo)
                if tritium_cargo and tritium_cargo != '0':
                    tritium_text = f"{fuel} / {tritium_cargo}"
                else:
                    tritium_text = fuel
                
                # Select button - updates dropdown to select this carrier
                select_btn = tk.Button(
                    row_frame,
                    text="Select",
                    command=lambda c=callsign: self.select_carrier_from_details(c, details_window),
                    width=8,
                    relief=tk.RAISED
                )
                select_btn.grid(row=0, column=0, padx=2, pady=5, sticky=tk.W)
                # Add separator after Select column
                separator0 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator0.grid(row=0, column=1, padx=0, pady=2, sticky=tk.NS)
                
                # Highlight if this is the currently selected carrier
                if callsign == self.selected_carrier_callsign:
                    select_btn.config(bg="lightgreen", text="Selected")
                
                # Callsign (clickable to Inara)
                callsign_label = tk.Label(row_frame, text=callsign, fg="blue", cursor="hand2", width=12, anchor="w")
                callsign_label.grid(row=0, column=2, padx=2, pady=5, sticky=tk.W)
                callsign_label.bind("<Button-1>", lambda e, c=callsign: self.open_inara_carrier(c))
                callsign_label.bind("<Enter>", lambda e, lbl=callsign_label: lbl.config(fg="darkblue", underline=True))
                callsign_label.bind("<Leave>", lambda e, lbl=callsign_label: lbl.config(fg="blue", underline=False))
                separator1 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator1.grid(row=0, column=3, padx=0, pady=2, sticky=tk.NS)
                
                # Name (clickable to Inara)
                name_label = tk.Label(row_frame, text=name, fg="blue", cursor="hand2", width=20, anchor="w")
                name_label.grid(row=0, column=4, padx=2, pady=5, sticky=tk.W)
                name_label.bind("<Button-1>", lambda e, c=callsign: self.open_inara_carrier(c))
                name_label.bind("<Enter>", lambda e, lbl=name_label: lbl.config(fg="darkblue", underline=True))
                name_label.bind("<Leave>", lambda e, lbl=name_label: lbl.config(fg="blue", underline=False))
                separator2 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator2.grid(row=0, column=5, padx=0, pady=2, sticky=tk.NS)
                
                # System (clickable to Inara)
                system_label = tk.Label(row_frame, text=system, fg="blue", cursor="hand2", width=20, anchor="w")
                system_label.grid(row=0, column=6, padx=2, pady=5, sticky=tk.W)
                system_label.bind("<Button-1>", lambda e, s=system: self.open_inara_system(s))
                system_label.bind("<Enter>", lambda e, lbl=system_label: lbl.config(fg="darkblue", underline=True))
                system_label.bind("<Leave>", lambda e, lbl=system_label: lbl.config(fg="blue", underline=False))
                separator3 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator3.grid(row=0, column=7, padx=0, pady=2, sticky=tk.NS)
                
                # Tritium (fuel / cargo)
                tk.Label(row_frame, text=tritium_text, width=15, anchor="w").grid(row=0, column=8, padx=2, pady=5, sticky=tk.W)
                separator4 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator4.grid(row=0, column=9, padx=0, pady=2, sticky=tk.NS)
                
                # Balance
                tk.Label(row_frame, text=balance_formatted, width=15, anchor="w").grid(row=0, column=10, padx=2, pady=5, sticky=tk.W)
                separator5 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator5.grid(row=0, column=11, padx=0, pady=2, sticky=tk.NS)
                
                # Cargo
                tk.Label(row_frame, text=cargo_text, width=20, anchor="w").grid(row=0, column=12, padx=2, pady=5, sticky=tk.W)
                separator6 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator6.grid(row=0, column=13, padx=0, pady=2, sticky=tk.NS)
                
                # State
                tk.Label(row_frame, text=state, width=15, anchor="w").grid(row=0, column=14, padx=2, pady=5, sticky=tk.W)
                separator7 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator7.grid(row=0, column=15, padx=0, pady=2, sticky=tk.NS)
                
                # Theme
                tk.Label(row_frame, text=theme, width=15, anchor="w").grid(row=0, column=16, padx=2, pady=5, sticky=tk.W)
                separator8 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator8.grid(row=0, column=17, padx=0, pady=2, sticky=tk.NS)
                
                # Icy Rings (read-only checkbox)
                icy_rings_value = icy_rings.lower() == 'yes' if icy_rings else False
                icy_rings_var = tk.BooleanVar(value=icy_rings_value)
                icy_rings_cb = tk.Checkbutton(row_frame, variable=icy_rings_var, state=tk.DISABLED, text="", width=12, anchor="w")
                icy_rings_cb.grid(row=0, column=18, padx=2, pady=5, sticky=tk.W)
                separator9 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator9.grid(row=0, column=19, padx=0, pady=2, sticky=tk.NS)
                
                # Pristine (read-only checkbox)
                pristine_value = pristine.lower() == 'yes' if pristine else False
                pristine_var = tk.BooleanVar(value=pristine_value)
                pristine_cb = tk.Checkbutton(row_frame, variable=pristine_var, state=tk.DISABLED, text="", width=12, anchor="w")
                pristine_cb.grid(row=0, column=20, padx=2, pady=5, sticky=tk.W)
                separator10 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator10.grid(row=0, column=21, padx=0, pady=2, sticky=tk.NS)
                
                # Docking Access (read-only checkbox)
                docking_access_value = docking_access.lower() in ['yes', 'all', 'friends', 'squadron'] if docking_access else False
                docking_access_var = tk.BooleanVar(value=docking_access_value)
                docking_access_cb = tk.Checkbutton(row_frame, variable=docking_access_var, state=tk.DISABLED, text="", width=15, anchor="w")
                docking_access_cb.grid(row=0, column=22, padx=2, pady=5, sticky=tk.W)
                separator11 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator11.grid(row=0, column=23, padx=0, pady=2, sticky=tk.NS)
                
                # Notorious Access (read-only checkbox)
                notorious_access_value = notorious_access.lower() in ['true', 'yes', '1'] if isinstance(notorious_access, str) else bool(notorious_access) if notorious_access else False
                notorious_access_var = tk.BooleanVar(value=notorious_access_value)
                notorious_access_cb = tk.Checkbutton(row_frame, variable=notorious_access_var, state=tk.DISABLED, text="", width=18, anchor="w")
                notorious_access_cb.grid(row=0, column=24, padx=2, pady=5, sticky=tk.W)
                separator12 = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator12.grid(row=0, column=25, padx=0, pady=2, sticky=tk.NS)
                
                # Last Updated
                tk.Label(row_frame, text=last_updated, width=20, anchor="w").grid(row=0, column=26, padx=2, pady=5, sticky=tk.W)
            
            # Finalize window setup after all widgets are created
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            # Calculate actual content width after widgets are created
            scrollable_frame.update_idletasks()
            actual_content_width = scrollable_frame.winfo_reqwidth()
            # Use the larger of calculated width or actual content width
            final_width = max(window_width, actual_content_width + 50)  # Add padding
            # Still respect screen bounds
            screen_width = details_window.winfo_screenwidth()
            final_width = min(final_width, screen_width - 20)
            final_width = max(final_width, 800)  # Minimum 800px
            
            # Set window size
            details_window.geometry(f"{final_width}x600")
            details_window.minsize(800, 400)  # Minimum size to show content
            
            # Close button (outside scrollable area)
            close_btn_frame = tk.Frame(details_window, bg="white")
            close_btn_frame.pack(pady=5)
            close_btn = tk.Button(close_btn_frame, text="Close", command=details_window.destroy)
            close_btn.pack()
            
        except Exception:
            logger.warning('!! Error showing carrier details window: ' + traceback.format_exc(), exc_info=False)
            confirmDialog.showerror("Error", "Failed to display carrier details.")
    
    def open_inara_carrier(self, callsign: str):
        """
        Open Inara.cz page for a fleet carrier.
        
        Args:
            callsign: Fleet carrier callsign (may contain spaces or special characters)
        
        Note: urllib.parse.quote() properly URL-encodes spaces (%20) and special characters
        """
        try:
            # Inara fleet carrier search URL format
            # We'll use the search function since direct carrier URLs may vary
            # urllib.parse.quote() handles spaces, special chars, and unicode properly
            # e.g., "My Carrier" becomes "My%20Carrier"
            encoded_callsign = urllib.parse.quote(callsign)
            url = f"https://inara.cz/elite/fleetcarrier/?search={encoded_callsign}"
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
            # Inara system URL format: https://inara.cz/elite/system/?search=SYSTEMNAME
            # urllib.parse.quote() handles spaces, special chars, and unicode properly
            # e.g., "Sol" stays "Sol", "Alpha Centauri" becomes "Alpha%20Centauri"
            encoded_name = urllib.parse.quote(system_name)
            url = f"https://inara.cz/elite/system/?search={encoded_name}"
            webbrowser.open(url)
        except Exception:
            logger.warning(f'!! Error opening Inara system page for {system_name}: ' + traceback.format_exc(), exc_info=False)
    
    def check_fleet_carrier_restock_warning(self):
        """
        Check if the fleet carrier is currently in a system that requires Tritium restock
        based on the route CSV. Shows warning and "Find Trit" button if needed.
        """
        if not self.fleetcarrier or not self.route:
            self.fleetrestock_lbl.grid_remove()
            self.find_trit_btn.grid_remove()
            return
        
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
                # Get the most recently updated carrier
                sorted_carriers = sorted(
                    carriers,
                    key=lambda x: x.get('last_updated', ''),
                    reverse=True
                )
                carrier_system = sorted_carriers[0].get('current_system', '').strip()
        
        # Check if any route entry matches carrier's current system and has "Restock Tritium" = "Yes"
        if carrier_system:
            for route_entry in self.route:
                route_system = route_entry[0].strip() if len(route_entry) > 0 else ""
                
                # Check if system names match (case-insensitive)
                if route_system.lower() == carrier_system.lower():
                    # Check if this route entry has "Restock Tritium" = "Yes"
                    # For fleet carrier routes, the "Restock Tritium" is typically the last column
                    if len(route_entry) > 2:
                        restock_value = route_entry[-1].strip().lower() if route_entry[-1] else ""
                        if restock_value == "yes":
                            # Show warning (without system name, it's shown separately)
                            self.fleetrestock_lbl["text"] = self.fleetstocklbl_txt
                            self.fleetrestock_lbl.grid()
                            self.find_trit_btn.grid()
                            return
        
        # Hide if no match found
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
                confirmDialog.showwarning("No System", "Could not determine carrier's current system.")
                return
            
            # Inara.cz commodity search URL format
            # https://inara.cz/elite/commodities/?search=Tritium&nearstarsystem=SYSTEMNAME
            encoded_system = urllib.parse.quote(carrier_system)
            encoded_commodity = urllib.parse.quote("Tritium")
            url = f"https://inara.cz/elite/commodities/?search={encoded_commodity}&nearstarsystem={encoded_system}"
            webbrowser.open(url)
            
        except Exception:
            logger.warning('!! Error opening Inara Tritium search: ' + traceback.format_exc(), exc_info=False)
            confirmDialog.showerror("Error", "Failed to open Inara Tritium search.")
    
    def update_fleet_carrier_system_display(self):
        """
        Update the fleet carrier system location display under the dropdown.
        """
        if not self.fleet_carrier_system_label:
            return
        
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
                    # Get the most recently updated carrier
                    sorted_carriers = sorted(
                        carriers,
                        key=lambda x: x.get('last_updated', ''),
                        reverse=True
                    )
                    carrier_system = sorted_carriers[0].get('current_system', '').strip()
            
            if carrier_system:
                self.fleet_carrier_system_label.config(text=f"System: {carrier_system}", foreground="")
            else:
                self.fleet_carrier_system_label.config(text="System: Unknown", foreground="gray")
        except Exception:
            logger.warning('!! Error updating fleet carrier system display: ' + traceback.format_exc(), exc_info=False)
            self.fleet_carrier_system_label.config(text="System: Error", foreground="red")
    
    def find_tritium_near_current_system(self):
        """
        Open Inara.cz commodity search for Tritium near the player's current system (from EDMC).
        """
        try:
            # Get the player's current system from EDMC monitor state
            current_system = monitor.state.get('SystemName')
            
            if not current_system:
                confirmDialog.showwarning("No System", "Could not determine your current system location.")
                return
            
            # Inara.cz commodity search URL format
            # https://inara.cz/elite/commodities/?search=Tritium&nearstarsystem=SYSTEMNAME
            encoded_system = urllib.parse.quote(current_system)
            encoded_commodity = urllib.parse.quote("Tritium")
            url = f"https://inara.cz/elite/commodities/?search={encoded_commodity}&nearstarsystem={encoded_system}"
            webbrowser.open(url)
            
        except Exception:
            logger.warning('!! Error opening Inara Tritium search near current system: ' + traceback.format_exc(), exc_info=False)
            confirmDialog.showerror("Error", "Failed to open Inara Tritium search.")
    
    def update_fleet_carrier_rings_status(self):
        """
        Update the Icy Rings and Pristine checkboxes from CSV data.
        Only queries EDSM API if data is missing from CSV (e.g., after system change or initial load).
        Updates are stored back to the CSV managed by FleetCarrierManager.
        """
        if not self.fleet_carrier_icy_rings_cb or not self.fleet_carrier_pristine_cb:
            return
        
        try:
            # Get the currently selected carrier
            carrier = None
            callsign = None
            
            if self.selected_carrier_callsign and self.fleet_carrier_manager:
                callsign = self.selected_carrier_callsign
                carrier = self.fleet_carrier_manager.get_carrier(callsign)
            
            # If no carrier selected, try to get the first/primary carrier
            if not carrier:
                carriers = self.get_all_fleet_carriers()
                if carriers:
                    sorted_carriers = sorted(
                        carriers,
                        key=lambda x: x.get('last_updated', ''),
                        reverse=True
                    )
                    carrier = sorted_carriers[0]
                    callsign = carrier.get('callsign', '')
            
            if not carrier or not callsign:
                # No carrier available, uncheck both
                self.fleet_carrier_icy_rings_var.set(False)
                self.fleet_carrier_pristine_var.set(False)
                self._draw_icy_rings_toggle()
                self._draw_pristine_toggle()
                return
            
            carrier_system = carrier.get('current_system', '').strip()
            if not carrier_system:
                # No system available, uncheck both
                self.fleet_carrier_icy_rings_var.set(False)
                self.fleet_carrier_pristine_var.set(False)
                self._draw_icy_rings_toggle()
                self._draw_pristine_toggle()
                return
            
            # First, check if we have stored data in CSV
            icy_rings_stored = carrier.get('icy_rings', '').strip()
            pristine_stored = carrier.get('pristine', '').strip()
            
            has_icy_rings = False
            has_pristine = False
            need_api_query = False
            
            # Check if we have valid stored data
            if icy_rings_stored.lower() in ['yes', 'no'] and pristine_stored.lower() in ['yes', 'no']:
                # We have stored data, use it
                has_icy_rings = (icy_rings_stored.lower() == 'yes')
                has_pristine = (pristine_stored.lower() == 'yes')
            else:
                # No stored data, need to query API
                need_api_query = True
                logger.info(f"No stored rings status for carrier {callsign} in system {carrier_system}, querying API")
            
            # Query EDSM API only if data is missing
            if need_api_query:
                try:
                    encoded_system = urllib.parse.quote(carrier_system)
                    url = f"https://www.edsm.net/api-system-v1/bodies?systemName={encoded_system}"
                    
                    response = requests.get(url, timeout=5, headers={'User-Agent': 'EDMC_SpanshRouter'})
                    
                    if response.status_code == 200:
                        system_data = response.json()
                        
                        # Check if system data has bodies
                        if 'bodies' in system_data and isinstance(system_data['bodies'], list):
                            for body in system_data['bodies']:
                                # Check if body has rings
                                if 'rings' in body and isinstance(body['rings'], list):
                                    for ring in body['rings']:
                                        ring_type = ring.get('type', '').strip()
                                        reserve_level = ring.get('reserveLevel', '').strip()
                                        
                                        # Check for Icy type (any reserve level)
                                        if ring_type.lower() == 'icy':
                                            has_icy_rings = True
                                            
                                            # Check for Pristine reserve level (only for Icy rings)
                                            if reserve_level.lower() == 'pristine':
                                                has_pristine = True
                                                # Found both Icy and Pristine, can stop here
                                                break
                                    
                                    # If we found both, no need to check more bodies
                                    if has_icy_rings and has_pristine:
                                        break
                        
                        # Store the results back to CSV via FleetCarrierManager
                        if self.fleet_carrier_manager:
                            self.fleet_carrier_manager.update_rings_status(callsign, has_icy_rings, has_pristine)
                    
                except requests.RequestException as e:
                    logger.warning(f'!! Error querying EDSM API for system bodies: {e}')
                    # On error, uncheck both but don't save to CSV
                    has_icy_rings = False
                    has_pristine = False
                except Exception as e:
                    logger.warning('!! Error checking fleet carrier rings status: ' + traceback.format_exc(), exc_info=False)
                    # On error, uncheck both but don't save to CSV
                    has_icy_rings = False
                    has_pristine = False
            
            # Update toggle buttons (from CSV data or API query result)
            self.fleet_carrier_icy_rings_var.set(has_icy_rings)
            self.fleet_carrier_pristine_var.set(has_pristine)
            # Redraw the toggle buttons
            self._draw_icy_rings_toggle()
            self._draw_pristine_toggle()
                
        except Exception:
            logger.warning('!! Error updating fleet carrier rings status: ' + traceback.format_exc(), exc_info=False)
            # On error, uncheck both
            self.fleet_carrier_icy_rings_var.set(False)
            self.fleet_carrier_pristine_var.set(False)
            # Redraw the toggle buttons
            self._draw_icy_rings_toggle()
            self._draw_pristine_toggle()
    
    def update_fleet_carrier_tritium_display(self):
        """
        Update the fleet carrier Tritium display (fuel and cargo) under the system display.
        """
        if not self.fleet_carrier_tritium_label:
            return
        
        try:
            # Get the currently selected carrier's Tritium info
            carrier = None
            if self.selected_carrier_callsign and self.fleet_carrier_manager:
                carrier = self.fleet_carrier_manager.get_carrier(self.selected_carrier_callsign)
            
            # If no carrier selected, try to get the first/primary carrier
            if not carrier:
                carriers = self.get_all_fleet_carriers()
                if carriers:
                    # Get the most recently updated carrier
                    sorted_carriers = sorted(
                        carriers,
                        key=lambda x: x.get('last_updated', ''),
                        reverse=True
                    )
                    carrier = sorted_carriers[0]
            
            if carrier:
                fuel = carrier.get('fuel', '0')
                tritium_cargo = carrier.get('tritium_in_cargo', '0')
                
                # Format the display (keep blue for clickability)
                if tritium_cargo and tritium_cargo != '0':
                    display_text = f"Tritium: {fuel} (In Cargo: {tritium_cargo})"
                else:
                    display_text = f"Tritium: {fuel}"
                
                self.fleet_carrier_tritium_label.config(text=display_text, foreground="blue")
            else:
                self.fleet_carrier_tritium_label.config(text="Tritium: Unknown", foreground="gray")
        except Exception:
            logger.warning('!! Error updating fleet carrier Tritium display: ' + traceback.format_exc(), exc_info=False)
            self.fleet_carrier_tritium_label.config(text="Tritium: Error", foreground="red")
    
    def update_fleet_carrier_balance_display(self):
        """
        Update the fleet carrier credit balance display below the Tritium display.
        """
        if not self.fleet_carrier_balance_label:
            return
        
        try:
            # Get the currently selected carrier's balance info
            carrier = None
            if self.selected_carrier_callsign and self.fleet_carrier_manager:
                carrier = self.fleet_carrier_manager.get_carrier(self.selected_carrier_callsign)
            
            # If no carrier selected, try to get the first/primary carrier
            if not carrier:
                carriers = self.get_all_fleet_carriers()
                if carriers:
                    # Get the most recently updated carrier
                    sorted_carriers = sorted(
                        carriers,
                        key=lambda x: x.get('last_updated', ''),
                        reverse=True
                    )
                    carrier = sorted_carriers[0]
            
            if carrier:
                balance = carrier.get('balance', '0')
                
                # Format balance with commas
                try:
                    balance_formatted = f"{int(balance):,}" if balance else "0"
                    display_text = f"Balance: {balance_formatted} cr"
                except (ValueError, TypeError):
                    display_text = f"Balance: {balance} cr"
                
                self.fleet_carrier_balance_label.config(text=display_text, foreground="")
            else:
                self.fleet_carrier_balance_label.config(text="Balance: Unknown", foreground="gray")
        except Exception:
            logger.warning('!! Error updating fleet carrier balance display: ' + traceback.format_exc(), exc_info=False)
            self.fleet_carrier_balance_label.config(text="Balance: Error", foreground="red")
    
    def show_route_window(self):
        """
        Open a window displaying the current route as an easy-to-read list.
        System names are hyperlinked to Inara.cz.
        Shows all columns based on route type with checkboxes for yes/no fields.
        """
        try:
            if not self.route or len(self.route) == 0:
                confirmDialog.showinfo("View Route", "No route is currently loaded.")
                return
            
            # Read the saved CSV file to get all column data
            route_data = []
            fieldnames = []
            fieldname_map = {}
            
            if os.path.exists(self.save_route_path):
                try:
                    with open(self.save_route_path, 'r', encoding='utf-8-sig', newline='') as csvfile:
                        reader = csv.DictReader(csvfile)
                        fieldnames = reader.fieldnames if reader.fieldnames else []
                        
                        # Create case-insensitive fieldname mapping
                        fieldname_map = {name.lower(): name for name in fieldnames}
                        
                        def get_field(row, field_name, default=""):
                            """Get field value from row using case-insensitive lookup"""
                            key = fieldname_map.get(field_name.lower(), field_name)
                            return row.get(key, default)
                        
                        # Read all rows and store all fields
                        for row in reader:
                            route_entry = {}
                            for field_name in fieldnames:
                                route_entry[field_name.lower()] = get_field(row, field_name, '')
                            route_data.append(route_entry)
                except Exception:
                    logger.warning('!! Error reading route CSV for display: ' + traceback.format_exc(), exc_info=False)
                    confirmDialog.showerror("Error", "Failed to read route CSV file.")
                    return
            else:
                # Fallback: create route data from in-memory route structure
                # This is less ideal but better than nothing
                confirmDialog.showwarning("Route File Not Found", "Route CSV file not found. Please import the route again.")
                return
            
            if not route_data:
                confirmDialog.showinfo("View Route", "No route data to display.")
                return
            
            # Detect route type from CSV columns if not already set
            # Check for Road to Riches by looking for Body Name column
            if not self.roadtoriches and 'body name' in fieldname_map:
                self.roadtoriches = True
            
            # Define columns to exclude based on route type
            exclude_columns = set()
            checkbox_columns = set()
            
            # Fleet Carrier routes: exclude Tritium in tank and Tritium in market
            if self.fleetcarrier:
                exclude_columns.add('tritium in tank')
                exclude_columns.add('tritium in market')
                # Checkbox columns for fleet carrier
                if 'icy ring' in fieldname_map:
                    checkbox_columns.add('icy ring')
                if 'pristine' in fieldname_map:
                    checkbox_columns.add('pristine')
                if 'restock tritium' in fieldname_map:
                    checkbox_columns.add('restock tritium')
            
            # Galaxy routes: Refuel and Neutron Star are checkboxes
            if self.galaxy:
                if 'refuel' in fieldname_map:
                    checkbox_columns.add('refuel')
                if 'neutron star' in fieldname_map:
                    checkbox_columns.add('neutron star')
            
            # Road to Riches: Is Terraformable is checkbox
            if self.roadtoriches:
                if 'is terraformable' in fieldname_map:
                    checkbox_columns.add('is terraformable')
            
            # Neutron routes: Neutron Star is checkbox (if not galaxy and has Neutron Star column)
            if not self.fleetcarrier and not self.galaxy and not self.roadtoriches:
                # Check if this might be a neutron route (has Neutron Star column)
                if 'neutron star' in fieldname_map:
                    checkbox_columns.add('neutron star')
            
            # Build list of columns to display
            display_columns = []
            for field in fieldnames:
                field_lower = field.lower()
                # Always exclude excluded columns
                if field_lower in exclude_columns:
                    continue
                display_columns.append(field)
            
            # For Road to Riches, track previous system name to avoid repetition
            prev_system_name = None
            
            # Create new window
            route_window = tk.Toplevel(self.parent)
            route_window.title("Route View")
            
            # Create main container with horizontal and vertical scrolling
            main_frame = tk.Frame(route_window, bg="white")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Create horizontal scrollbar
            h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL)
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            
            # Create vertical scrollbar
            v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL)
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Create canvas with both scrollbars
            canvas = tk.Canvas(main_frame, bg="white",
                             xscrollcommand=h_scrollbar.set,
                             yscrollcommand=v_scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            h_scrollbar.config(command=canvas.xview)
            v_scrollbar.config(command=canvas.yview)
            
            scrollable_frame = tk.Frame(canvas, bg="white")
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            
            # Update canvas scroll region when frame size changes
            def on_frame_configure(event):
                canvas.configure(scrollregion=canvas.bbox("all"))
                # Update canvas window width to match canvas width for proper horizontal scrolling
                canvas_width = canvas.winfo_width()
                if canvas_width > 1:  # Only update if canvas has been rendered
                    canvas_window_id = canvas.find_all()
                    if canvas_window_id:
                        canvas.itemconfig(canvas_window_id[0], width=canvas_width)
            
            scrollable_frame.bind("<Configure>", on_frame_configure)
            
            # Also bind to canvas resize
            def on_canvas_configure(event):
                canvas_width = event.width
                canvas_window_id = canvas.find_all()
                if canvas_window_id:
                    canvas.itemconfig(canvas_window_id[0], width=canvas_width)
            
            canvas.bind('<Configure>', on_canvas_configure)
            
            # Header
            header_frame = tk.Frame(scrollable_frame, bg="lightgray", relief=tk.RAISED, borderwidth=1)
            header_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # Add step number as first column
            headers = ["#"] + display_columns
            column_widths = [4] + [max(15, len(h)) for h in display_columns]
            
            # Calculate required width based on columns (after column_widths is defined)
            # More accurate estimate: column_widths * 8-10 pixels per character + padding + separators
            # Account for separators (one between each column, ~2px each)
            num_separators = len(headers) - 1
            separator_width = num_separators * 2
            # Use 9 pixels per character width for more accurate sizing
            total_column_width = sum(column_widths) * 9 + separator_width + 200  # Add padding for buttons/scrollbars/margins
            screen_width = route_window.winfo_screenwidth()
            # Open window wide enough to show all columns, but don't exceed screen width
            # If content is wider than screen, user can scroll horizontally
            window_width = min(total_column_width, screen_width - 20)  # Leave small margin from screen edges
            # Ensure minimum width so content isn't cut off
            window_width = max(window_width, 800)  # At least 800px wide
            
            for i, header in enumerate(headers):
                width = column_widths[i] if i < len(column_widths) else 20
                # Cap width at reasonable maximum
                width = min(width, 30) if i > 0 else width
                label = tk.Label(header_frame, text=header, font=("Arial", 9, "bold"), bg="lightgray", width=width)
                label.grid(row=0, column=i*2, padx=2, pady=5, sticky=tk.W)
                # Add vertical separator after each column (except the last)
                if i < len(headers) - 1:
                    separator = ttk.Separator(header_frame, orient=tk.VERTICAL)
                    separator.grid(row=0, column=i*2+1, padx=0, pady=2, sticky=tk.NS)
            
            # Route rows
            for idx, route_entry in enumerate(route_data):
                row_frame = tk.Frame(scrollable_frame, relief=tk.RIDGE, borderwidth=1)
                row_frame.pack(fill=tk.X, padx=5, pady=2)
                
                col_idx = 0
                
                # Step number
                tk.Label(row_frame, text=str(idx + 1), width=4, anchor="w").grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                # Add separator after step number
                separator_step = ttk.Separator(row_frame, orient=tk.VERTICAL)
                separator_step.grid(row=0, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                col_idx += 1
                
                # Display each column
                for field_idx, field_name in enumerate(display_columns):
                    field_lower = field_name.lower()
                    value = route_entry.get(field_lower, '').strip() if isinstance(route_entry.get(field_lower, ''), str) else str(route_entry.get(field_lower, ''))
                    
                    # Special handling for System Name
                    if field_lower == self.system_header.lower():
                        # For Road to Riches, check if system name repeats
                        if self.roadtoriches:
                            current_system = value
                            if current_system and current_system.lower() == prev_system_name:
                                # System name repeats, show empty
                                system_label = tk.Label(row_frame, text="", width=30, anchor="w")
                                system_label.grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                            else:
                                # New system name, display it
                                if current_system:
                                    system_label = tk.Label(row_frame, text=current_system, fg="blue", cursor="hand2", width=30, anchor="w")
                                    system_label.grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                                    system_label.bind("<Button-1>", lambda e, s=current_system: self.open_inara_system(s))
                                    system_label.bind("<Enter>", lambda e, lbl=system_label: lbl.config(fg="darkblue", underline=True))
                                    system_label.bind("<Leave>", lambda e, lbl=system_label: lbl.config(fg="blue", underline=False))
                                else:
                                    tk.Label(row_frame, text="", width=30, anchor="w").grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                            prev_system_name = current_system.lower() if current_system else None
                        else:
                            # Normal system name display (clickable to Inara)
                            if value:
                                system_label = tk.Label(row_frame, text=value, fg="blue", cursor="hand2", width=30, anchor="w")
                                system_label.grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                                system_label.bind("<Button-1>", lambda e, s=value: self.open_inara_system(s))
                                system_label.bind("<Enter>", lambda e, lbl=system_label: lbl.config(fg="darkblue", underline=True))
                                system_label.bind("<Leave>", lambda e, lbl=system_label: lbl.config(fg="blue", underline=False))
                            else:
                                tk.Label(row_frame, text="", width=30, anchor="w").grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                    
                    # Checkbox columns (yes/no fields)
                    elif field_lower in checkbox_columns:
                        checkbox_value = value.lower()
                        checkbox_var = tk.BooleanVar(value=(checkbox_value == 'yes'))
                        checkbox_text = field_name  # Use original field name for display
                        checkbox_cb = tk.Checkbutton(row_frame, variable=checkbox_var, state=tk.DISABLED, text=checkbox_text, width=15, anchor="w")
                        checkbox_cb.grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                    
                    # Regular text columns
                    else:
                        width = min(max(15, len(field_name)), 25)
                        tk.Label(row_frame, text=value if value else "", width=width, anchor="w").grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                    
                    # Add separator after each column (except the last)
                    if field_idx < len(display_columns) - 1:
                        separator = ttk.Separator(row_frame, orient=tk.VERTICAL)
                        separator.grid(row=0, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                    
                    col_idx += 1
            
            # Finalize window setup after all widgets are created
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            # Calculate actual content width after widgets are created
            scrollable_frame.update_idletasks()
            actual_content_width = scrollable_frame.winfo_reqwidth()
            # Use the larger of calculated width or actual content width
            final_width = max(window_width, actual_content_width + 50)  # Add padding
            # Still respect screen bounds
            screen_width = route_window.winfo_screenwidth()
            final_width = min(final_width, screen_width - 20)
            final_width = max(final_width, 800)  # Minimum 800px
            
            # Set window size
            route_window.geometry(f"{final_width}x700")
            route_window.minsize(800, 400)  # Minimum size to show content
            
            # Close button (outside scrollable area)
            close_btn_frame = tk.Frame(route_window, bg="white")
            close_btn_frame.pack(pady=5)
            close_btn = tk.Button(close_btn_frame, text="Close", command=route_window.destroy)
            close_btn.pack()
            
        except Exception:
            logger.warning('!! Error showing route window: ' + traceback.format_exc(), exc_info=False)
            confirmDialog.showerror("Error", "Failed to display route.")
    
    def update_fleet_carrier_status(self):
        """
        Update the fleet carrier status display (legacy method, now uses dropdown).
        """
        self.update_fleet_carrier_dropdown()
        self.update_fleet_carrier_system_display()
        self.update_fleet_carrier_rings_status()
        self.update_fleet_carrier_tritium_display()
        self.update_fleet_carrier_balance_display()
