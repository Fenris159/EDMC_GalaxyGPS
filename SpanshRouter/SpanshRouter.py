import ast
import csv
import json
import logging
import os
import re
import subprocess
import sys
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as confirmDialog
import traceback
import webbrowser
from time import sleep
from tkinter import *

import requests  # type: ignore
from config import appname  # type: ignore
from monitor import monitor  # type: ignore

from . import AutoCompleter, PlaceHolder
from .updater import SpanshUpdater

# We need a name of plugin dir, not SpanshRouter.py dir
plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
logger = logging.getLogger(f'{appname}.{plugin_name}')


class SpanshRouter():
    def __init__(self, plugin_dir):
        version_file = os.path.join(plugin_dir, "version.json")
        with open(version_file, 'r') as version_fd:
            self.plugin_version = version_fd.read()

        self.update_available = False
        self.roadtoriches = False
        self.fleetcarrier = False
        self.galaxy = False
        self.next_stop = "No route planned"
        self.route = []
        self.next_wp_label = "Next waypoint: "
        self.jumpcountlbl_txt = "Estimated jumps left: "
        self.bodieslbl_txt = "Bodies to scan at: "
        self.fleetstocklbl_txt = "Time to restock Tritium"
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
        # Supercharge mode (Spansh neutron routing)
        # False = normal supercharge (x4)
        # True  = overcharge supercharge (x6)
        self.supercharge_overcharge = tk.BooleanVar(value=False)

    #   -- GUI part --
    def init_gui(self, parent):
        self.parent = parent
        self.frame = tk.Frame(parent, borderwidth=2)
        self.frame.grid(sticky=tk.NSEW, columnspan=2)

        # Route info
        self.waypoint_prev_btn = tk.Button(self.frame, text="^", command=self.goto_prev_waypoint)
        self.waypoint_btn = tk.Button(self.frame, text=self.next_wp_label + '\n' + self.next_stop, command=self.copy_waypoint)
        self.waypoint_next_btn = tk.Button(self.frame, text="v", command=self.goto_next_waypoint)
        self.jumpcounttxt_lbl = tk.Label(self.frame, text=self.jumpcountlbl_txt + str(self.jumps_left))
        self.dist_prev_lbl = tk.Label(self.frame, text="")
        self.dist_next_lbl = tk.Label(self.frame, text="")
        self.dist_remaining_lbl = tk.Label(self.frame, text="")
        self.bodies_lbl = tk.Label(self.frame, justify=LEFT, text=self.bodieslbl_txt + self.bodies)
        self.fleetrestock_lbl = tk.Label(self.frame, justify=LEFT, text=self.fleetstocklbl_txt)
        self.refuel_lbl = tk.Label(self.frame, justify=LEFT, text=self.refuellbl_txt)
        self.error_lbl = tk.Label(self.frame, textvariable=self.error_txt)

        # Plotting GUI
        self.source_ac = AutoCompleter(self.frame, "Source System", width=30)
        self.dest_ac = AutoCompleter(self.frame, "Destination System", width=30)
        self.range_entry = PlaceHolder(self.frame, "Range (LY)", width=10)
        self.supercharge_cb = tk.Checkbutton(self.frame, text="Supercharge", variable=self.supercharge_overcharge)

        self.efficiency_slider = tk.Scale(self.frame, from_=1, to=100, orient=tk.HORIZONTAL, label="Efficiency (%)")
        self.efficiency_slider.set(60)
        self.plot_gui_btn = tk.Button(self.frame, text="Plot route", command=self.show_plot_gui)
        self.plot_route_btn = tk.Button(self.frame, text="Calculate", command=self.plot_route)
        self.cancel_plot = tk.Button(self.frame, text="Cancel", command=lambda: self.show_plot_gui(False))

        self.csv_route_btn = tk.Button(self.frame, text="Import file", command=self.plot_file)
        self.export_route_btn = tk.Button(self.frame, text="Export for TCE", command=self.export_route)
        self.clear_route_btn = tk.Button(self.frame, text="Clear route", command=self.clear_route)

        row = 0
        self.waypoint_prev_btn.grid(row=row, column=0, columnspan=2, padx=5, pady=10)
        self.dist_remaining_lbl.grid(row=row, column=2, padx=5, pady=10, sticky=tk.W)
        row += 1
        self.waypoint_btn.grid(row=row, column=0, columnspan=2, padx=5, pady=10)
        self.dist_prev_lbl.grid(row=row, column=2, padx=5, pady=10, sticky=tk.W)
        row += 1
        self.waypoint_next_btn.grid(row=row, column=0, columnspan=2, padx=5, pady=10)
        self.dist_next_lbl.grid(row=row, column=2, padx=5, pady=10, sticky=tk.W)
        row += 1
        self.bodies_lbl.grid(row=row, columnspan=2, sticky=tk.W)
        row += 1
        self.fleetrestock_lbl.grid(row=row, columnspan=2, sticky=tk.W)
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
        self.csv_route_btn.grid(row=row, pady=10, padx=0)
        self.plot_route_btn.grid(row=row, pady=10, padx=0)
        self.plot_gui_btn.grid(row=row, column=1, pady=10, padx=5, sticky=tk.W)
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

        return self.frame

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
            self.dist_prev_lbl, self.dist_next_lbl, self.dist_remaining_lbl
        ]
        
        plotting_widgets = [
            self.source_ac, self.dest_ac, self.range_entry,
            self.supercharge_cb, self.efficiency_slider,
            self.plot_route_btn, self.cancel_plot
        ]
        
        basic_controls = [
            self.plot_gui_btn, self.csv_route_btn
        ]
        
        info_labels = [
            self.bodies_lbl, self.fleetrestock_lbl, self.refuel_lbl
        ]
        
        # Hide all widgets first
        for widget in route_widgets + plotting_widgets + basic_controls + info_labels:
            widget.grid_remove()
        
        # Show widgets based on state
        if state == 'plotting':
            # Show plotting interface
            for widget in plotting_widgets:
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
            for widget in route_widgets:
                widget.grid()
            
            # Update waypoint button text
            self.waypoint_btn["text"] = self.next_wp_label + '\n' + self.next_stop
            
            # Update distance labels
            if self.jumps_left > 0:
                self.jumpcounttxt_lbl["text"] = self.jumpcountlbl_txt + str(self.jumps_left)
                self.dist_prev_lbl["text"] = self.dist_prev
                self.dist_next_lbl["text"] = self.dist_next
                self.dist_remaining_lbl["text"] = self.dist_remaining
            else:
                self.jumpcounttxt_lbl.grid_remove()
                self.dist_prev_lbl.grid_remove()
                self.dist_next_lbl.grid_remove()
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
            
            if self.fleetcarrier and self.offset > 0:
                prev_waypoint = self.route[self.offset - 1]
                if len(prev_waypoint) > 2:
                    restock = prev_waypoint[-1]
                    if restock and restock.lower() == "yes":
                        self.fleetrestock_lbl["text"] = f"At: {prev_waypoint[0]}\n   {self.fleetstocklbl_txt}"
                        self.fleetrestock_lbl.grid()
            
            if self.galaxy and self.pleaserefuel:
                self.refuel_lbl['text'] = self.refuellbl_txt
                self.refuel_lbl.grid()
        
        # Always show basic controls when not plotting
        if state != 'plotting':
            for widget in basic_controls:
                widget.grid()

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

        if not (0 <= self.offset < len(self.route)):
            return

        def safe_flt(x):
            try:
                return float(x)
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
        else:
            self.dist_next = ""

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
                    # Check if we're already in the first waypoint system
                    # If so, automatically advance to the next waypoint
                    current_system = monitor.state.get('SystemName')
                    if self.route and current_system and self.route[0][0].lower() == current_system.lower():
                        self.offset = 1 if len(self.route) > 1 else 0
                        # Update jumps_left to account for skipping the first waypoint
                        if self.offset > 0 and len(self.route[0]) > 1:
                            if self.route[0][1] not in [None, "", []]:
                                if not self.galaxy:
                                    try:
                                        self.jumps_left -= int(self.route[0][1])
                                    except (ValueError, TypeError):
                                        pass
                                else:
                                    self.jumps_left -= 1
                    else:
                        self.offset = 0
                    
                    self.next_stop = self.route[self.offset][0] if self.route else ""
                    if self.galaxy:
                        self.pleaserefuel = self.route[self.offset][1] == "Yes" if self.route and len(self.route[self.offset]) > 1 else False
                    self.update_bodies_text()
                    self.compute_distances()
                    self.copy_waypoint()
                    self.update_gui()
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
                return dist_to_arrival, dist_remaining

            # --- neutron import ---
            if headerline_lower == neutronimportheader.lower():
                for row in route_reader:
                    if row not in (None, "", []):
                        self.route.append([
                            get_field(row, self.system_header),
                            get_field(row, self.jumps_header, ""),
                            get_field(row, "Distance To Arrival", ""),
                            get_field(row, "Distance Remaining", "")
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
                        self.route.append([
                            get_field(row, self.system_header),
                            get_field(row, self.jumps_header),
                            get_field(row, "Distance To Arrival", ""),
                            get_field(row, "Distance Remaining", ""),
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

                for row in route_reader:
                    if row not in (None, "", []):
                        dist_to_arrival, dist_remaining = get_distance_fields(row)

                        self.route.append([
                            get_field(row, self.system_header),
                            1,  # every row = one carrier jump
                            dist_to_arrival,
                            dist_remaining,
                            get_field(row, self.restocktritium_header, "")
                        ])
                        self.jumps_left += 1

            # --- galaxy ---
            elif has_field("Refuel") and has_field(self.system_header):
                self.galaxy = True

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

                        self.route.append(route_row)
                        self.jumps_left += 1

            else:
                for row in route_reader:
                    if row not in (None, "", []):
                        system = get_field(row, self.system_header, "")
                        jumps = get_field(row, self.jumps_header, "")
                        self.route.append([system, jumps])
                        try:
                            self.jumps_left += int(jumps) if jumps else 0
                        except (ValueError, TypeError):
                            pass

            if self.route:
                # Check if we're already in the first waypoint system
                # If so, automatically advance to the next waypoint
                current_system = monitor.state.get('SystemName')
                if current_system and self.route[0][0].lower() == current_system.lower():
                    self.offset = 1 if len(self.route) > 1 else 0
                    # Update jumps_left to account for skipping the first waypoint
                    if self.offset > 0 and len(self.route[0]) > 1:
                        if self.route[0][1] not in [None, "", []]:
                            if not self.galaxy:
                                try:
                                    self.jumps_left -= int(self.route[0][1])
                                except (ValueError, TypeError):
                                    pass
                            else:
                                self.jumps_left -= 1
                else:
                    self.offset = 0
                
                self.next_stop = self.route[self.offset][0]
                self.compute_distances()
                self.update_gui()

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
                fieldnames = [
                    self.system_header,
                    self.jumps_header,
                    "Distance To Arrival",
                    "Distance Remaining",
                    self.restocktritium_header
                ]
                with open(self.save_route_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(fieldnames)
                    for row in self.route:
                        writer.writerow([
                            row[0],
                            row[1],
                            row[2] if len(row) > 2 else "",
                            row[3] if len(row) > 3 else "",
                            row[4] if len(row) > 4 else ""
                        ])
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
        return  # Autoupdates is disabled
        self.cleanup_old_version()
        version_url = "https://raw.githubusercontent.com/CMDR-Kiel42/EDMC_SpanshRouter/master/version.json"
        try:
            response = requests.get(version_url, timeout=2)
            if response.status_code == 200:
                if self.plugin_version != response.text:
                    self.update_available = True
                    self.spansh_updater = SpanshUpdater(response.text, self.plugin_dir)

            else:
                logger.warning(f"Could not query latest SpanshRouter version, code: {str(response.status_code)}; text: {response.text}")
        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)

    def install_update(self):
        self.spansh_updater.install()
