import csv
import logging
import math
import os
import traceback
from typing import Dict, List, Tuple
from collections import defaultdict

import tkinter as tk
import tkinter.font as tkfont
import tkinter.ttk as ttk

from config import appname  # type: ignore
from theme import theme  # type: ignore
from ttkHyperlinkLabel import HyperlinkLabel  # type: ignore

# Import localization function from load.py
from load import plugin_tl  # type: ignore

from .ui_helpers import ThemeSafeCanvas
from .ui.window_manager import create_themed_window, restore_window_position
from .ui.widget_styler import style_scrollbars
from .ui.message_dialog import showinfo, showwarning, showerror

# Use same logger format as GalaxyGPS.py
plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
logger = logging.getLogger(f'{appname}.{plugin_name}')


def show_carrier_details_window(plugin, skip_refresh_check=False):
    """
    Open a window displaying all fleet carriers with details and Inara.cz links.
    
    Args:
        plugin: The plugin instance
        skip_refresh_check: If True, skip the check for existing window (used by refresh function)
    """
    try:
        logger.warning(f"[show_carrier_details_window] Called with skip_refresh_check={skip_refresh_check}")
        carriers = plugin.get_all_fleet_carriers()
        if not carriers:
            # LANG: Info message when no fleet carrier data available
            showinfo(plugin.parent, plugin_tl("Fleet Carriers"), plugin_tl("No fleet carrier data available."))
            return

        # If window is already open, refresh it seamlessly instead of closing
        if not skip_refresh_check and hasattr(plugin, 'carrier_details_window_ref') and plugin.carrier_details_window_ref:
            try:
                if plugin.carrier_details_window_ref.winfo_exists():
                    # Window exists, refresh it seamlessly
                    logger.warning("[show_carrier_details_window] Window exists, refreshing instead of creating new")
                    _refresh_carrier_details_window(plugin)
                    return
            except Exception:
                # Window was closed, clear reference and create new one
                plugin.carrier_details_window_ref = None

        # Create new window with custom themed title bar
        # Initialize window_positions if it doesn't exist
        if not hasattr(plugin, 'window_positions'):
            plugin.window_positions = {}
        saved_positions = plugin.window_positions
        details_window, content_frame = create_themed_window(
            plugin.parent, 
            plugin_tl("Fleet Carrier Details"),
            saved_positions=saved_positions
        )

        # Store reference to this window for dynamic updates
        plugin.carrier_details_window_ref = details_window

        # Wrap the window manager's close function to also clear our reference
        original_close = details_window._close_func
        def on_window_close():
            if plugin.carrier_details_window_ref == details_window:
                plugin.carrier_details_window_ref = None
            # Call the original close function which saves position and destroys window
            original_close()
        
        # Update the close button's command to use our wrapper
        # Find the close button by searching for the '✕' text in title bar
        try:
            title_bar = details_window.winfo_children()[0]  # First child is title_bar
            for child in title_bar.winfo_children():
                if isinstance(child, tk.Button):
                    try:
                        if child.cget('text') == '✕':
                            child.config(command=on_window_close)
                            break
                    except Exception:
                        pass
        except Exception:
            # Fallback: update the stored function (though button won't use it)
            details_window._close_func = on_window_close

        # Define headers and column widths first - add EDSM button before System
        headers = [
            plugin_tl("Select"), 
            plugin_tl("Callsign"), 
            plugin_tl("Name"), 
            plugin_tl("EDSM"), 
            plugin_tl("System"), 
            plugin_tl("Tritium"), 
            plugin_tl("Balance"), 
            plugin_tl("Cargo"), 
            plugin_tl("Shipyard"), 
            plugin_tl("State"), 
            plugin_tl("Theme"), 
            plugin_tl("Icy Rings"), 
            plugin_tl("Pristine"), 
            plugin_tl("Docking Access"), 
            plugin_tl("Notorious Access"), 
            plugin_tl("Last Updated")
        ]
        
        # Get fonts for accurate width calculation
        header_font = tkfont.Font(family="Arial", size=9, weight="bold")
        data_font = tkfont.Font(family="Arial", size=9)
        
        # Initialize column widths based on header text (in pixels)
        # Add padding (20 pixels per column for comfortable spacing)
        column_widths_px = [header_font.measure(h) + 20 for h in headers]

        # Calculate maximum content width for each column by checking all carrier data
        for carrier in carriers:
            callsign = carrier.get('callsign', 'Unknown')
            name = carrier.get('name', '') or 'Unnamed'
            system = carrier.get('current_system', 'Unknown')

            # Check for missing numerical values
            fuel_raw = carrier.get('fuel')
            tritium_cargo_raw = carrier.get('tritium_in_cargo')
            balance_raw = carrier.get('balance')
            cargo_count_raw = carrier.get('cargo_count')
            cargo_value_raw = carrier.get('cargo_total_value')

            # Check if values are missing (key doesn't exist, None, or empty string)
            # Note: '0' or 0 are valid values, so we only mark as missing if key doesn't exist or value is None/empty
            fuel_missing = 'fuel' not in carrier or fuel_raw is None or (isinstance(fuel_raw, str) and fuel_raw.strip() == '')
            tritium_cargo_missing = 'tritium_in_cargo' not in carrier or tritium_cargo_raw is None or (isinstance(tritium_cargo_raw, str) and tritium_cargo_raw.strip() == '')
            balance_missing = 'balance' not in carrier or balance_raw is None or (isinstance(balance_raw, str) and balance_raw.strip() == '')
            cargo_count_missing = 'cargo_count' not in carrier or cargo_count_raw is None or (isinstance(cargo_count_raw, str) and cargo_count_raw.strip() == '')
            cargo_value_missing = 'cargo_total_value' not in carrier or cargo_value_raw is None or (isinstance(cargo_value_raw, str) and cargo_value_raw.strip() == '')

            # Use raw values or defaults for formatting
            fuel = fuel_raw if fuel_raw is not None else '0'
            tritium_cargo = tritium_cargo_raw if tritium_cargo_raw is not None else '0'
            balance = balance_raw if balance_raw is not None else '0'
            cargo_count = cargo_count_raw if cargo_count_raw is not None else '0'
            cargo_value = cargo_value_raw if cargo_value_raw is not None else '0'

            state = carrier.get('state', 'Unknown')
            theme_name = carrier.get('theme', 'Unknown')
            docking_access = carrier.get('docking_access', '')
            last_updated = carrier.get('last_updated', 'Unknown')
            
            # Convert last_updated to local time with format "MM/DD/YY h:mm a" for width calculation
            last_updated_display = last_updated
            if last_updated and last_updated != 'Unknown':
                try:
                    from datetime import datetime
                    # Parse the ISO timestamp (assumes UTC)
                    dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                    # Convert to local time
                    local_dt = dt.astimezone()
                    # Format as "MM/DD/YY HH:MM AM/PM"
                    formatted = local_dt.strftime('%m/%d/%y %I:%M %p')
                    # Remove leading zero from hour (e.g., "01:30 PM" -> "1:30 PM")
                    # Split by space: ['MM/DD/YY', 'HH:MM', 'AM/PM']
                    parts = formatted.split(' ')
                    hour_min = parts[1]
                    if hour_min.startswith('0'):
                        hour_min = hour_min[1:]
                    last_updated_display = f"{parts[0]} {hour_min} {parts[2]}"
                except Exception:
                    # If parsing fails, use original value
                    last_updated_display = last_updated

            # Format balance - show "Needs Update" if missing, otherwise format with commas (including 0)
            if balance_missing:
                balance_formatted = "Needs Update"
            else:
                try:
                    balance_int = int(balance) if balance else 0
                    balance_formatted = f"{balance_int:,}"
                except (ValueError, TypeError):
                    balance_formatted = str(balance) if balance else "Needs Update"

            # Format cargo value - show "Needs Update" if missing, otherwise format with abbreviated notation
            if cargo_value_missing:
                cargo_value_formatted = "Needs Update"
            else:
                try:
                    cargo_value_int = int(cargo_value) if cargo_value else 0
                    # Format with M/B/T suffix for millions/billions/trillions
                    if cargo_value_int >= 1_000_000_000_000:  # Trillions
                        value_in_units = cargo_value_int / 1_000_000_000_000
                        cargo_value_formatted = f"{value_in_units:,.3f}T".rstrip('0').rstrip('.')
                    elif cargo_value_int >= 1_000_000_000:  # Billions
                        value_in_units = cargo_value_int / 1_000_000_000
                        cargo_value_formatted = f"{value_in_units:,.3f}B".rstrip('0').rstrip('.')
                    elif cargo_value_int >= 1_000_000:  # Millions
                        value_in_units = cargo_value_int / 1_000_000
                        cargo_value_formatted = f"{value_in_units:,.3f}M".rstrip('0').rstrip('.')
                    else:  # Less than a million, show full number
                        cargo_value_formatted = f"{cargo_value_int:,}"
                except (ValueError, TypeError):
                    cargo_value_formatted = str(cargo_value) if cargo_value else "Needs Update"

            # Format cargo text - show "Needs Update" if either count or value is missing
            if cargo_count_missing or cargo_value_missing:
                cargo_text = "Needs Update"
            else:
                try:
                    cargo_count_int = int(cargo_count) if cargo_count else 0
                    cargo_text = f"{cargo_count_int} ({cargo_value_formatted} cr)"
                except (ValueError, TypeError):
                    cargo_text = "Needs Update"

            # Format Tritium - show "Needs Update" if fuel is missing, otherwise show value (including 0)
            if fuel_missing:
                tritium_text = "Needs Update"
            elif not tritium_cargo_missing and tritium_cargo and tritium_cargo != '0':
                try:
                    fuel_int = int(fuel) if fuel else 0
                    tritium_cargo_int = int(tritium_cargo) if tritium_cargo else 0
                    tritium_text = f"{fuel_int} / {tritium_cargo_int}"
                except (ValueError, TypeError):
                    tritium_text = f"{fuel} / {tritium_cargo}" if fuel and tritium_cargo else str(fuel) if fuel else "Needs Update"
            else:
                try:
                    fuel_int = int(fuel) if fuel else 0
                    tritium_text = str(fuel_int)
                except (ValueError, TypeError):
                    tritium_text = str(fuel) if fuel else "Needs Update"

            # Update column widths based on actual pixel measurements (add 20px padding per column)
            column_widths_px[1] = max(column_widths_px[1], data_font.measure(str(callsign)) + 20)  # Callsign
            column_widths_px[2] = max(column_widths_px[2], data_font.measure(str(name)) + 20)      # Name
            column_widths_px[4] = max(column_widths_px[4], data_font.measure(str(system)) + 20)     # System
            column_widths_px[5] = max(column_widths_px[5], data_font.measure(str(tritium_text)) + 20)  # Tritium
            column_widths_px[6] = max(column_widths_px[6], data_font.measure(str(balance_formatted)) + 20)  # Balance
            column_widths_px[7] = max(column_widths_px[7], data_font.measure(str(cargo_text)) + 20)  # Cargo
            column_widths_px[8] = max(column_widths_px[8], data_font.measure("Ships") + 20)  # Ships button
            column_widths_px[9] = max(column_widths_px[9], data_font.measure(str(state)) + 20)       # State
            column_widths_px[10] = max(column_widths_px[10], data_font.measure(str(theme_name)) + 20)      # Theme
            column_widths_px[13] = max(column_widths_px[13], data_font.measure(str(docking_access)) + 20)  # Docking Access
            column_widths_px[15] = max(column_widths_px[15], data_font.measure(str(last_updated_display)) + 20)  # Last Updated (formatted)

        # Calculate required width based on actual pixel measurements
        # Account for separators (one between each column, ~2px each)
        num_separators = len(headers) - 1
        separator_width = num_separators * 2
        # Sum up actual pixel widths plus separators and margins
        total_column_width = sum(column_widths_px) + separator_width + 75  # Add margin to prevent horizontal scrollbar
        screen_width = details_window.winfo_screenwidth()
        # Open window wide enough to show all columns, but don't exceed screen width
        # If content is wider than screen, user can scroll horizontally
        window_width = min(total_column_width, screen_width - 20)  # Leave small margin from screen edges
        # Ensure minimum width so content isn't cut off
        window_width = max(window_width, 800)  # At least 800px wide

        # Create main container with horizontal and vertical scrolling
        # Use content_frame from create_themed_window instead of creating new frame
        main_frame = content_frame

        # Create horizontal scrollbar (initially hidden)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL)
        
        # Create vertical scrollbar (initially hidden)
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL)

        # Wrapper functions to auto-show/hide scrollbars based on whether scrolling is needed
        def safe_h_scrollbar_set(*args):
            h_scrollbar.set(*args)
            # Auto-show/hide horizontal scrollbar
            # args are (first, last) where both are 0.0-1.0
            # If first=0.0 and last=1.0, all content is visible (no scrolling needed)
            # Use larger tolerance (0.98) to account for rounding, pixel alignment, and padding
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    # All content visible, hide scrollbar
                    h_scrollbar.pack_forget()
                else:
                    # Scrolling needed, show scrollbar
                    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X, before=canvas)
        
        def safe_v_scrollbar_set(*args):
            v_scrollbar.set(*args)
            # Auto-show/hide vertical scrollbar
            # Use larger tolerance (0.98) to account for rounding, pixel alignment, and padding
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    # All content visible, hide scrollbar
                    v_scrollbar.pack_forget()
                else:
                    # Scrolling needed, show scrollbar
                    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, before=canvas)

        # Create canvas with both scrollbars
        canvas = ThemeSafeCanvas(main_frame,
                        xscrollcommand=safe_h_scrollbar_set,
                        yscrollcommand=safe_v_scrollbar_set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        theme.update(canvas)

        h_scrollbar.config(command=canvas.xview)
        v_scrollbar.config(command=canvas.yview)

        # Style scrollbars to match EDMC theme
        style_scrollbars(h_scrollbar, v_scrollbar, main_frame)

        scrollable_frame = tk.Frame(canvas)

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        theme.update(scrollable_frame)

        # Update canvas scroll region when frame size changes
        def on_frame_configure(event):
            # Always update scroll region so scrollbars can update during resize
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            # Only update canvas window width if NOT resizing (prevents horizontal thrashing)
            if hasattr(details_window, '_is_resizing') and details_window._is_resizing:
                return
            
            # Only update canvas window width if content is narrower than canvas
            # This allows horizontal scrolling when content is wider than canvas
            canvas_width = canvas.winfo_width()
            if canvas_width > 1:  # Only update if canvas has been rendered
                canvas_window_id = canvas.find_all()
                if canvas_window_id:
                    # Get the actual content width from the scrollable frame
                    content_width = scrollable_frame.winfo_reqwidth()
                    # Only set width if content is narrower than canvas (to fill available space)
                    # If content is wider, let it be wider to enable horizontal scrolling
                    if content_width < canvas_width:
                        canvas.itemconfig(canvas_window_id[0], width=canvas_width)
                    else:
                        # Reset width to allow natural content width
                        canvas.itemconfig(canvas_window_id[0], width=content_width)

        scrollable_frame.bind("<Configure>", on_frame_configure)

        # Also bind to canvas resize
        def on_canvas_configure(event):
            # Always update scroll region so scrollbars can update during resize
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            # Only update canvas window width if NOT resizing (prevents horizontal thrashing)
            if hasattr(details_window, '_is_resizing') and details_window._is_resizing:
                return
            
            canvas_width = event.width
            canvas_window_id = canvas.find_all()
            if canvas_window_id:
                # Get the actual content width from the scrollable frame
                content_width = scrollable_frame.winfo_reqwidth()
                # Only set width if content is narrower than canvas
                if content_width < canvas_width:
                    canvas.itemconfig(canvas_window_id[0], width=canvas_width)
                else:
                    # Reset width to allow natural content width
                    canvas.itemconfig(canvas_window_id[0], width=content_width)

        canvas.bind('<Configure>', on_canvas_configure)

        # Create a single table frame that will contain both header and data rows in one grid
        table_frame = tk.Frame(scrollable_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        theme.update(table_frame)
        # Force update to ensure theme colors are applied before reading background
        table_frame.update_idletasks()
        
        # Configure grid columns to use pixel-based widths for tight, automatic sizing
        for i, width_px in enumerate(column_widths_px):
            # Each data column uses column index i*2 (separators use i*2+1)
            table_frame.grid_columnconfigure(i*2, minsize=width_px, weight=0)
            # Separator columns (if not last column)
            if i < len(column_widths_px) - 1:
                table_frame.grid_columnconfigure(i*2+1, minsize=2, weight=0)

        # Determine which columns should be right-aligned (numeric columns)
        numeric_columns_fleet = set()
        for header_name in headers:
            header_lower = header_name.lower()
            # Right-align numeric columns: Tritium, Balance (but not Cargo which has text)
            if any(keyword in header_lower for keyword in ['tritium', 'balance']) and 'cargo' not in header_lower:
                numeric_columns_fleet.add(header_lower)

        # Header row (row 0) - styled with grey background and bold text
        header_row = 0
        for i, header in enumerate(headers):
            # Right-align numeric columns, left-align text columns, center-align checkbox columns
            header_lower = header.lower()
            # Check if this is an indicator column (Icy Rings, Pristine, Docking Access, Notorious Access, Refuel, Neutron Star, etc.)
            is_indicator_col = any(keyword in header_lower for keyword in ['icy rings', 'pristine', 'docking access', 'notorious access', 'refuel', 'neutron star', 'restock tritium', 'is terraformable'])
            if header_lower == "edsm":  # EDSM button column - center align
                anchor = "c"
                sticky_val = tk.EW
            elif header_lower in numeric_columns_fleet:
                anchor = "e"  # Right-align for numeric columns
                sticky = tk.E
            elif is_indicator_col:
                anchor = "c"  # Center-align for indicator columns (colored dots)
                sticky = tk.EW  # Expand to fill column width for centering
            else:
                anchor = "w"  # Left-align for text columns
                sticky = tk.W
            # Grid column configuration handles width, just create label with proper anchor
            label = tk.Label(table_frame, text=header, font=("Arial", 9, "bold"), anchor=anchor)
            label.grid(row=header_row, column=i*2, padx=2, pady=5, sticky=sticky)
            theme.update(label)
            # Add vertical separator after each column (except the last)
            if i < len(headers) - 1:
                separator = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator.grid(row=header_row, column=i*2+1, padx=0, pady=2, sticky=tk.NS)

        # Carrier data rows (rows 1+) - use same grid as header for perfect alignment
        # Get background color from theme AFTER theme.update() has been applied
        # Force another update to ensure colors are applied
        table_frame.update_idletasks()
        try:
            base_bg = table_frame.cget('bg')
            
            # Detect theme first to determine appropriate base color
            try:
                from config import config  # type: ignore
                current_theme = config.get_int('theme')
                is_dark = current_theme in [1, 2]  # 1 = dark, 2 = transparent (dark)
            except:
                # Fallback: detect from background color
                is_dark = (isinstance(base_bg, str) and 
                          base_bg.lower() in ['black', '#000000', '#1e1e1e', 'systemwindow'])
            
            # Determine base_row_bg based on theme, not just background color
            # For transparent theme (theme=2), base_bg might be 'systemwindow' which we should use
            if base_bg and base_bg.strip():
                # For dark/transparent themes, use the background even if it's 'systemwindow'
                if is_dark:
                    # Dark/transparent theme: use the background color (including 'systemwindow')
                    base_row_bg = base_bg
                else:
                    # Light theme: exclude white/systemwindow
                    if base_bg.lower() not in ['white', '#ffffff', 'systemwindow', 'systembuttonface']:
                        base_row_bg = base_bg
                    else:
                        # Light theme with systemwindow - use white
                        base_row_bg = '#ffffff'
            else:
                # No background color detected - use theme-appropriate default
                base_row_bg = '#1e1e1e' if is_dark else '#ffffff'
            
            # Create alternating color - slightly lighter for dark mode, slightly darker for light mode
            if base_row_bg and base_row_bg != "":
                if is_dark:
                    # Dark mode: alternate with slightly lighter shade
                    try:
                        # Convert hex to RGB, lighten, convert back
                        if base_row_bg.startswith('#'):
                            rgb = tuple(int(base_row_bg[i:i+2], 16) for i in (1, 3, 5))
                            alt_rgb = tuple(min(255, c + 15) for c in rgb)  # Lighten by 15
                            alt_row_bg = f"#{alt_rgb[0]:02x}{alt_rgb[1]:02x}{alt_rgb[2]:02x}"
                        else:
                            # Named color (e.g., 'systemwindow') - use a fixed lighter shade for dark theme
                            alt_row_bg = '#2a2a2a'  # Lighter than typical dark theme background
                    except:
                        alt_row_bg = '#2a2a2a'
                else:
                    # Light mode: alternate with slightly darker shade
                    try:
                        if base_row_bg.startswith('#'):
                            rgb = tuple(int(base_row_bg[i:i+2], 16) for i in (1, 3, 5))
                            alt_rgb = tuple(max(0, c - 15) for c in rgb)  # Darken by 15
                            alt_row_bg = f"#{alt_rgb[0]:02x}{alt_rgb[1]:02x}{alt_rgb[2]:02x}"
                        else:
                            # Named color (e.g., 'systemwindow') - use a fixed darker shade for light theme
                            alt_row_bg = '#e5e5e5'  # Slightly darker than white
                    except:
                        alt_row_bg = '#e5e5e5'
            else:
                alt_row_bg = ""
        except Exception:
            base_row_bg = ""  # Empty string allows theme to handle it
            alt_row_bg = ""
        
        for idx, carrier in enumerate(sorted(carriers, key=lambda x: x.get('last_updated', ''), reverse=True)):
            data_row = idx + 1  # Start from row 1 (row 0 is header)
            
            # Alternate row background color for better readability
            row_bg = base_row_bg if idx % 2 == 0 else alt_row_bg

            callsign = carrier.get('callsign', 'Unknown')
            name = carrier.get('name', '') or 'Unnamed'
            system = carrier.get('current_system', 'Unknown')

            # Check for missing numerical values - use None if key doesn't exist or value is None/empty
            fuel_raw = carrier.get('fuel')
            tritium_cargo_raw = carrier.get('tritium_in_cargo')
            balance_raw = carrier.get('balance')
            cargo_count_raw = carrier.get('cargo_count')
            cargo_value_raw = carrier.get('cargo_total_value')

            # Check if values are missing (key doesn't exist, None, or empty string)
            # Note: '0' or 0 are valid values, so we only mark as missing if key doesn't exist or value is None/empty
            fuel_missing = 'fuel' not in carrier or fuel_raw is None or (isinstance(fuel_raw, str) and fuel_raw.strip() == '')
            tritium_cargo_missing = 'tritium_in_cargo' not in carrier or tritium_cargo_raw is None or (isinstance(tritium_cargo_raw, str) and tritium_cargo_raw.strip() == '')
            balance_missing = 'balance' not in carrier or balance_raw is None or (isinstance(balance_raw, str) and balance_raw.strip() == '')
            cargo_count_missing = 'cargo_count' not in carrier or cargo_count_raw is None or (isinstance(cargo_count_raw, str) and cargo_count_raw.strip() == '')
            cargo_value_missing = 'cargo_total_value' not in carrier or cargo_value_raw is None or (isinstance(cargo_value_raw, str) and cargo_value_raw.strip() == '')

            # Use raw values or defaults for formatting
            fuel = fuel_raw if fuel_raw is not None else '0'
            tritium_cargo = tritium_cargo_raw if tritium_cargo_raw is not None else '0'
            balance = balance_raw if balance_raw is not None else '0'
            cargo_count = cargo_count_raw if cargo_count_raw is not None else '0'
            cargo_value = cargo_value_raw if cargo_value_raw is not None else '0'

            state = carrier.get('state', 'Unknown')
            theme_name = carrier.get('theme', 'Unknown')
            icy_rings = carrier.get('icy_rings', '')
            pristine = carrier.get('pristine', '')
            docking_access = carrier.get('docking_access', '')
            notorious_access = carrier.get('notorious_access', '')
            last_updated = carrier.get('last_updated', 'Unknown')
            
            # Convert last_updated to local time with format "MM/DD/YY h:mm a"
            # Only for display - doesn't change the cached data
            last_updated_display = last_updated
            if last_updated and last_updated != 'Unknown':
                try:
                    from datetime import datetime
                    # Parse the ISO timestamp (assumes UTC)
                    dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                    # Convert to local time
                    local_dt = dt.astimezone()
                    # Format as "MM/DD/YY HH:MM AM/PM"
                    formatted = local_dt.strftime('%m/%d/%y %I:%M %p')
                    # Remove leading zero from hour (e.g., "01:30 PM" -> "1:30 PM")
                    # Split by space: ['MM/DD/YY', 'HH:MM', 'AM/PM']
                    parts = formatted.split(' ')
                    hour_min = parts[1]
                    if hour_min.startswith('0'):
                        hour_min = hour_min[1:]
                    last_updated_display = f"{parts[0]} {hour_min} {parts[2]}"
                except Exception:
                    # If parsing fails, use original value
                    last_updated_display = last_updated

            # Format balance - show "Needs Update" if missing, otherwise format with commas (including 0)
            if balance_missing:
                balance_formatted = "Needs Update"
            else:
                try:
                    balance_int = int(balance) if balance else 0
                    balance_formatted = f"{balance_int:,}"
                except (ValueError, TypeError):
                    balance_formatted = str(balance) if balance else "Needs Update"

            # Format cargo value - show "Needs Update" if missing, otherwise format with commas (including 0)
            if cargo_value_missing:
                cargo_value_formatted = "Needs Update"
            else:
                try:
                    cargo_value_int = int(cargo_value) if cargo_value else 0
                    cargo_value_formatted = f"{cargo_value_int:,}"
                except (ValueError, TypeError):
                    cargo_value_formatted = str(cargo_value) if cargo_value else "Needs Update"

            # Format cargo text - show "Needs Update" if either count or value is missing
            if cargo_count_missing or cargo_value_missing:
                cargo_text = "Needs Update"
            else:
                try:
                    cargo_count_int = int(cargo_count) if cargo_count else 0
                    cargo_text = f"{cargo_count_int} ({cargo_value_formatted} cr)"
                except (ValueError, TypeError):
                    cargo_text = "Needs Update"

            # Format Tritium: fuel / cargo (or just fuel if no cargo)
            # Show "Needs Update" if fuel is missing, otherwise show value (including 0)
            if fuel_missing:
                tritium_text = "Needs Update"
            elif not tritium_cargo_missing and tritium_cargo and tritium_cargo != '0':
                try:
                    fuel_int = int(fuel) if fuel else 0
                    tritium_cargo_int = int(tritium_cargo) if tritium_cargo else 0
                    tritium_text = f"{fuel_int} / {tritium_cargo_int}"
                except (ValueError, TypeError):
                    tritium_text = f"{fuel} / {tritium_cargo}" if fuel and tritium_cargo else str(fuel) if fuel else "Needs Update"
            else:
                try:
                    fuel_int = int(fuel) if fuel else 0
                    tritium_text = str(fuel_int)
                except (ValueError, TypeError):
                    tritium_text = str(fuel) if fuel else "Needs Update"

            # Use the same column indexing pattern as headers (i*2 for labels, i*2+1 for separators)
            # Use column_widths array to ensure alignment with headers
            col_idx = 0

            # Select button - updates dropdown to select this carrier
            # Only set bg if row_bg is a valid non-empty string
            select_btn = tk.Button(
                table_frame,
                text="Select",
                command=lambda c=callsign: plugin.select_carrier_from_details(c, details_window),
                relief=tk.RAISED,
                bg=row_bg if row_bg else None  # Only set bg if row_bg is not empty
            )
            select_btn.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(select_btn)
            # Add separator after Select column
            if col_idx < len(headers) - 1:
                separator0 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator0.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator0)
            col_idx += 1

            # Highlight if this is the currently selected carrier
            if callsign == plugin.selected_carrier_callsign:
                select_btn.config(bg="lightgreen", text="Selected")

            # Callsign (clickable to Inara, right-click to copy)
            callsign_label = HyperlinkLabel(
                table_frame,
                text=callsign,
                url=lambda e, c=callsign: plugin.open_inara_carrier(c),
                popup_copy=True,
                anchor="w"
            )
            callsign_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(callsign_label)
            if col_idx < len(headers) - 1:
                separator1 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator1.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator1)
            col_idx += 1

            # Name (clickable to Inara, right-click to copy)
            name_label = HyperlinkLabel(
                table_frame,
                text=name,
                url=lambda e, c=callsign: plugin.open_inara_carrier(c),
                popup_copy=True,
                anchor="w"
            )
            name_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(name_label)
            if col_idx < len(headers) - 1:
                separator2 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator2.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator2)
            col_idx += 1

            # EDSM button - before System column
            btn_kwargs = {"master": table_frame, "text": "EDSM", "command": lambda s=system: plugin.open_edsm_system(s)}
            if row_bg:
                btn_kwargs["bg"] = row_bg
            edsm_btn = tk.Button(**btn_kwargs)
            edsm_btn.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(edsm_btn)
            if col_idx < len(headers) - 1:
                separator_edsm = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator_edsm.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator_edsm)
            col_idx += 1

            # System (clickable to Inara, right-click to copy)
            system_label = HyperlinkLabel(
                table_frame,
                text=system,
                url=lambda e, s=system: plugin.open_inara_system(s),
                popup_copy=True,
                anchor="w"
            )
            system_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(system_label)
            if col_idx < len(headers) - 1:
                separator3 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator3.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator3)
            col_idx += 1

            # Tritium (fuel / cargo) - right-align numeric
            label_kwargs = {"master": table_frame, "text": tritium_text, "anchor": "e"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            tritium_label = tk.Label(**label_kwargs)
            tritium_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.E)
            theme.update(tritium_label)
            if col_idx < len(headers) - 1:
                separator4 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator4.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator4)
            col_idx += 1

            # Balance - right-align numeric (displayed in green)
            label_kwargs = {"master": table_frame, "text": balance_formatted, "anchor": "e", "fg": "green"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            balance_label = tk.Label(**label_kwargs)
            balance_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.E)
            theme.update(balance_label)
            if col_idx < len(headers) - 1:
                separator5 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator5.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator5)
            col_idx += 1

            # Cargo - display as button (like EDSM button style)
            # Check if carrier has cargo data to determine button state
            has_cargo_data = False
            if hasattr(plugin, 'cargo_manager') and plugin.cargo_manager:
                cargo_data = plugin.cargo_manager.get_cargo_for_carrier(callsign)
                has_cargo_data = len(cargo_data) > 0
            
            def on_cargo_click(c=callsign):
                """Wrapper to catch and log any errors from button click"""
                try:
                    from .windows import show_cargo_details_window as cargo_window_func
                    cargo_window_func(plugin, c)
                except Exception as e:
                    logger.error(f"[on_cargo_click] Error opening cargo window: {e}", exc_info=True)
                    try:
                        from .ui.message_dialog import showerror
                        # LANG: Error opening cargo details
                        showerror(plugin.parent, plugin_tl("Error"), plugin_tl("Failed to open cargo details: {ERROR}").format(ERROR=str(e)))
                    except:
                        pass
            
            btn_kwargs = {
                "master": table_frame,
                "text": cargo_text,
                "command": on_cargo_click,
                "anchor": "w",
                "state": tk.NORMAL if has_cargo_data else tk.DISABLED
            }
            if row_bg:
                btn_kwargs["bg"] = row_bg
            cargo_btn = tk.Button(**btn_kwargs)
            cargo_btn.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(cargo_btn)
            if col_idx < len(headers) - 1:
                separator6 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator6.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator6)
            col_idx += 1

            # Ships button - check if carrier has ships data to determine button state
            has_ships_data = False
            if hasattr(plugin, 'ships_manager') and plugin.ships_manager:
                ships_data = plugin.ships_manager.get_ships_for_carrier(callsign)
                has_ships_data = len(ships_data) > 0
            
            def on_ships_click(c=callsign):
                """Wrapper to catch and log any errors from button click"""
                try:
                    from .windows import show_ships_details_window as ships_window_func
                    ships_window_func(plugin, c)
                except Exception as e:
                    logger.error(f"[on_ships_click] Error opening ships window: {e}", exc_info=True)
                    try:
                        from .ui.message_dialog import showerror
                        # LANG: Error opening ships details
                        showerror(plugin.parent, plugin_tl("Error"), plugin_tl("Failed to open ships details: {ERROR}").format(ERROR=str(e)))
                    except:
                        pass
            
            # Create a container frame for Ships and Modules buttons
            shipyard_frame = tk.Frame(table_frame)
            if row_bg:
                shipyard_frame.config(bg=row_bg)
            shipyard_frame.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(shipyard_frame)
            
            ships_btn_kwargs = {
                "master": shipyard_frame,
                "text": "Ships",
                "command": on_ships_click,
                "state": tk.NORMAL if has_ships_data else tk.DISABLED
            }
            if row_bg:
                ships_btn_kwargs["bg"] = row_bg
            ships_btn = tk.Button(**ships_btn_kwargs)
            ships_btn.pack(side=tk.LEFT, padx=(0, 5))
            theme.update(ships_btn)
            
            # Modules button - check if carrier has modules data to determine button state
            has_modules_data = False
            if hasattr(plugin, 'modules_manager') and plugin.modules_manager:
                modules_data = plugin.modules_manager.get_modules_for_carrier(callsign)
                has_modules_data = len(modules_data) > 0
                logger.debug(f"[Fleet Carrier Window] Carrier {callsign} has {len(modules_data)} modules, button enabled: {has_modules_data}")
            else:
                logger.warning(f"[Fleet Carrier Window] modules_manager not available for carrier {callsign}")
            
            def on_modules_click(c=callsign):
                """Wrapper to catch and log any errors from button click"""
                logger.info(f"[on_modules_click] Modules button clicked for carrier: {c}")
                try:
                    show_modules_details_window(plugin, c)
                except Exception as e:
                    logger.error(f"[on_modules_click] Error opening modules window: {e}", exc_info=True)
                    try:
                        from .ui.message_dialog import showerror
                        # LANG: Error opening modules details
                        showerror(plugin.parent, plugin_tl("Error"), plugin_tl("Failed to open modules details: {ERROR}").format(ERROR=str(e)))
                    except:
                        pass
            
            modules_btn_kwargs = {
                "master": shipyard_frame,
                "text": "Modules",
                "command": on_modules_click,
                "state": tk.NORMAL if has_modules_data else tk.DISABLED
            }
            if row_bg:
                modules_btn_kwargs["bg"] = row_bg
            modules_btn = tk.Button(**modules_btn_kwargs)
            modules_btn.pack(side=tk.LEFT)
            theme.update(modules_btn)
            
            if col_idx < len(headers) - 1:
                separator_ships = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator_ships.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator_ships)
            col_idx += 1

            # State
            label_kwargs = {"master": table_frame, "text": state, "anchor": "w"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            state_label = tk.Label(**label_kwargs)
            state_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(state_label)
            if col_idx < len(headers) - 1:
                separator7 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator7.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator7)
            col_idx += 1

            # Theme
            label_kwargs = {"master": table_frame, "text": theme_name, "anchor": "w"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            theme_label = tk.Label(**label_kwargs)
            theme_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(theme_label)
            if col_idx < len(headers) - 1:
                separator8 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator8.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator8)
            col_idx += 1

            # Icy Rings (read-only indicator) - colored dot, center-aligned
            icy_rings_str = str(icy_rings).strip().lower() if icy_rings else ''
            icy_rings_value = icy_rings_str == 'yes'
            # Create a frame to center the canvas within the column
            frame_kwargs = {"master": table_frame}
            if row_bg:
                frame_kwargs["bg"] = row_bg
            icy_rings_frame = tk.Frame(**frame_kwargs)
            icy_rings_frame.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.EW)
            theme.update(icy_rings_frame)
            canvas_kwargs = {"master": icy_rings_frame, "width": 40, "height": 40, "highlightthickness": 0}
            if row_bg:
                canvas_kwargs["bg"] = row_bg
            icy_rings_canvas = ThemeSafeCanvas(**canvas_kwargs)
            icy_rings_canvas.pack(anchor=tk.CENTER)  # Center the canvas in the frame
            if icy_rings_value:
                icy_rings_canvas.create_oval(10, 10, 30, 30, fill="red", outline="darkred", width=2)
            else:
                icy_rings_canvas.create_oval(10, 10, 30, 30, fill=row_bg, outline="lightgray", width=2)
            if col_idx < len(headers) - 1:
                separator9 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator9.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator9)
            col_idx += 1

            # Pristine (read-only indicator) - colored dot, center-aligned
            pristine_str = str(pristine).strip().lower() if pristine else ''
            pristine_value = pristine_str == 'yes'
            # Create a frame to center the canvas within the column
            frame_kwargs = {"master": table_frame}
            if row_bg:
                frame_kwargs["bg"] = row_bg
            pristine_frame = tk.Frame(**frame_kwargs)
            pristine_frame.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.EW)
            theme.update(pristine_frame)
            canvas_kwargs = {"master": pristine_frame, "width": 40, "height": 40, "highlightthickness": 0}
            if row_bg:
                canvas_kwargs["bg"] = row_bg
            pristine_canvas = ThemeSafeCanvas(**canvas_kwargs)
            pristine_canvas.pack(anchor=tk.CENTER)  # Center the canvas in the frame
            if pristine_value:
                pristine_canvas.create_oval(10, 10, 30, 30, fill="red", outline="darkred", width=2)
            else:
                pristine_canvas.create_oval(10, 10, 30, 30, fill=row_bg, outline="lightgray", width=2)
            if col_idx < len(headers) - 1:
                separator10 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator10.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator10)
            col_idx += 1

            # Docking Access (read-only indicator) - colored dot, center-aligned
            docking_access_str = str(docking_access).strip().lower() if docking_access else ''
            docking_access_value = docking_access_str in ['yes', 'all', 'friends', 'squadron']
            # Create a frame to center the canvas within the column
            frame_kwargs = {"master": table_frame}
            if row_bg:
                frame_kwargs["bg"] = row_bg
            docking_access_frame = tk.Frame(**frame_kwargs)
            docking_access_frame.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.EW)
            theme.update(docking_access_frame)
            canvas_kwargs = {"master": docking_access_frame, "width": 40, "height": 40, "highlightthickness": 0}
            if row_bg:
                canvas_kwargs["bg"] = row_bg
            docking_access_canvas = ThemeSafeCanvas(**canvas_kwargs)
            docking_access_canvas.pack(anchor=tk.CENTER)  # Center the canvas in the frame
            if docking_access_value:
                docking_access_canvas.create_oval(10, 10, 30, 30, fill="red", outline="darkred", width=2)
            else:
                docking_access_canvas.create_oval(10, 10, 30, 30, fill=row_bg, outline="lightgray", width=2)
            if col_idx < len(headers) - 1:
                separator11 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator11.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator11)
            col_idx += 1

            # Notorious Access (read-only indicator) - colored dot, center-aligned
            if isinstance(notorious_access, str):
                notorious_access_str = notorious_access.strip().lower()
                notorious_access_value = notorious_access_str in ['true', 'yes', '1']
            else:
                notorious_access_value = bool(notorious_access) if notorious_access else False
            # Create a frame to center the canvas within the column
            frame_kwargs = {"master": table_frame}
            if row_bg:
                frame_kwargs["bg"] = row_bg
            notorious_access_frame = tk.Frame(**frame_kwargs)
            notorious_access_frame.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.EW)
            theme.update(notorious_access_frame)
            canvas_kwargs = {"master": notorious_access_frame, "width": 40, "height": 40, "highlightthickness": 0}
            if row_bg:
                canvas_kwargs["bg"] = row_bg
            notorious_access_canvas = ThemeSafeCanvas(**canvas_kwargs)
            notorious_access_canvas.pack(anchor=tk.CENTER)  # Center the canvas in the frame
            if notorious_access_value:
                notorious_access_canvas.create_oval(10, 10, 30, 30, fill="red", outline="darkred", width=2)
            else:
                notorious_access_canvas.create_oval(10, 10, 30, 30, fill=row_bg, outline="lightgray", width=2)
            if col_idx < len(headers) - 1:
                separator12 = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator12.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator12)
            col_idx += 1

            # Last Updated (formatted as local time: MM/DD/YY h:mm a)
            label_kwargs = {"master": table_frame, "text": last_updated_display, "anchor": "w"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            last_updated_label = tk.Label(**label_kwargs)
            last_updated_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(last_updated_label)

        # Apply theme recursively to entire table_frame after all widgets are created
        # This ensures any widgets we missed get themed properly
        # theme.update() will automatically apply correct foreground colors based on current theme
        theme.update(table_frame)

        # Style ttk.Separator widgets - they need special handling via ttk.Style
        # Separators don't automatically get themed, so we style them to match theme foreground color
        try:
            separator_style = ttk.Style()
            # Get theme foreground color from a label to match separator color
            sample_label = tk.Label(table_frame)
            theme.update(sample_label)
            try:
                theme_fg = sample_label.cget('foreground')
                if theme_fg:
                    # Configure separator background to match theme foreground color
                    separator_style.configure('TSeparator', background=theme_fg)
            except Exception:
                pass
            sample_label.destroy()
        except Exception:
            pass

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

        # Bind mousewheel scrolling after all widgets are created
        def on_mousewheel(event):
            # Scroll vertically with mousewheel
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def on_shift_mousewheel(event):
            # Scroll horizontally with Shift+mousewheel
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        
        # Recursively bind mousewheel to all widgets in the window
        def bind_mousewheel_recursive(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Shift-MouseWheel>", on_shift_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel_recursive(child)
        
        bind_mousewheel_recursive(details_window)

        # Restore window position or center on screen
        # The window manager handles close button in title bar, so no need for separate close button
        restore_window_position(details_window, "Fleet Carrier Details", saved_positions, final_width, 600)
        
        # After window is positioned, update saved position with actual window size
        # This ensures the saved position reflects the correct size for current columns
        try:
            details_window.update_idletasks()
            actual_width = details_window.winfo_width()
            actual_height = details_window.winfo_height()
            actual_x = details_window.winfo_x()
            actual_y = details_window.winfo_y()
            # Only update if the width changed (data might have changed)
            if saved_positions and "Fleet Carrier Details" in saved_positions:
                old_x, old_y, old_width, old_height = saved_positions["Fleet Carrier Details"]
                if old_width != actual_width:
                    # Width changed, update saved position with new size
                    saved_positions["Fleet Carrier Details"] = (actual_x, actual_y, actual_width, actual_height)
        except Exception:
            pass

    except Exception:
        logger.warning('!! Error showing carrier details window: ' + traceback.format_exc(), exc_info=False)
        # LANG: Error displaying carrier details
        showerror(plugin.parent, plugin_tl("Error"), plugin_tl("Failed to display carrier details."))


def _refresh_carrier_details_window(plugin):
    """
    Internal function to refresh carrier details window while preserving scroll position.
    Saves scroll position, rebuilds window, then restores scroll position.
    """
    try:
        window = plugin.carrier_details_window_ref
        if not window or not window.winfo_exists():
            return
        
        # Save window position and scroll position before rebuilding
        saved_window_pos = None
        saved_scroll_x = 0.0
        saved_scroll_y = 0.0
        try:
            # Save window position (x, y, width, height)
            window.update_idletasks()
            saved_window_pos = (
                window.winfo_x(),
                window.winfo_y(),
                window.winfo_width(),
                window.winfo_height()
            )
            
            # Also save to saved_positions dict if available (for persistence)
            if hasattr(plugin, 'window_positions') and plugin.window_positions is not None:
                plugin.window_positions["Fleet Carrier Details"] = saved_window_pos
            
            # Save scroll position
            content_frame = window.winfo_children()[1]  # Second child is content_frame
            main_frame = content_frame.winfo_children()[0]  # First child is main_frame
            for child in main_frame.winfo_children():
                if isinstance(child, tk.Canvas):
                    canvas = child
                    # Get current scroll position as fraction (0.0 to 1.0)
                    try:
                        # Get scroll region to calculate proper fraction
                        scroll_region = canvas.cget('scrollregion')
                        if scroll_region:
                            coords = scroll_region.split()
                            if len(coords) == 4:
                                scroll_width = float(coords[2]) - float(coords[0])
                                scroll_height = float(coords[3]) - float(coords[1])
                                if scroll_width > 0:
                                    saved_scroll_x = canvas.canvasx(0) / scroll_width
                                if scroll_height > 0:
                                    saved_scroll_y = canvas.canvasy(0) / scroll_height
                    except Exception:
                        pass
                    break
        except Exception:
            pass
        
        # Close existing window (position already saved above)
        try:
            window.destroy()
        except Exception:
            pass
        plugin.carrier_details_window_ref = None
        
        # Rebuild the window (skip refresh check to avoid recursion)
        # Window position will be restored by restore_window_position() using saved_positions
        show_carrier_details_window(plugin, skip_refresh_check=True)
        
        # Restore scroll position after window is rebuilt
        if saved_scroll_x > 0 or saved_scroll_y > 0:
            try:
                window = plugin.carrier_details_window_ref
                if window and window.winfo_exists():
                    window.update_idletasks()  # Ensure window is fully rendered
                    content_frame = window.winfo_children()[1]
                    main_frame = content_frame.winfo_children()[0]
                    for child in main_frame.winfo_children():
                        if isinstance(child, tk.Canvas):
                            canvas = child
                            canvas.update_idletasks()
                            # Restore scroll position
                            try:
                                canvas.xview_moveto(max(0.0, min(1.0, saved_scroll_x)))
                                canvas.yview_moveto(max(0.0, min(1.0, saved_scroll_y)))
                            except Exception:
                                pass
                            break
            except Exception:
                pass
        
    except Exception:
        logger.warning('!! Error refreshing carrier details window: ' + traceback.format_exc(), exc_info=False)


def refresh_carrier_details_window_if_open(plugin):
    """
    Refresh the carrier details window if it's currently open.
    This is called when carrier data changes (e.g., CAPI updates) to update the display.
    """
    if hasattr(plugin, 'carrier_details_window_ref') and plugin.carrier_details_window_ref:
        try:
            # Check if window still exists
            if plugin.carrier_details_window_ref.winfo_exists():
                # Use seamless refresh
                _refresh_carrier_details_window(plugin)
        except Exception:
            # Window was closed, clear reference
            plugin.carrier_details_window_ref = None


def _refresh_route_window(plugin):
    """
    Internal function to refresh route window while preserving scroll position.
    Saves scroll position, rebuilds window with updated waypoint highlight, then restores scroll position.
    """
    try:
        # Check if we're already refreshing to prevent recursion
        if hasattr(plugin, '_refreshing_route_window') and plugin._refreshing_route_window:
            return
        plugin._refreshing_route_window = True
        
        window = plugin.route_window_ref
        if not window:
            plugin._refreshing_route_window = False
            return
        
        # Check if window exists - use try/except for more reliable check
        try:
            if not window.winfo_exists():
                plugin.route_window_ref = None
                plugin._refreshing_route_window = False
                return
        except (tk.TclError, AttributeError):
            # Window is already destroyed or invalid
            plugin.route_window_ref = None
            plugin._refreshing_route_window = False
            return
        
        # Save window position and scroll position before rebuilding
        saved_window_pos = None
        saved_scroll_x = 0.0
        saved_scroll_y = 0.0
        try:
            # Save window position (x, y, width, height)
            window.update_idletasks()
            saved_window_pos = (
                window.winfo_x(),
                window.winfo_y(),
                window.winfo_width(),
                window.winfo_height()
            )
            
            # Also save to saved_positions dict if available (for persistence)
            if hasattr(plugin, 'window_positions') and plugin.window_positions is not None:
                plugin.window_positions["Route View"] = saved_window_pos
            
            # Save scroll position
            content_frame = window.winfo_children()[1]  # Second child is content_frame
            main_frame = content_frame.winfo_children()[0]  # First child is main_frame
            for child in main_frame.winfo_children():
                if isinstance(child, tk.Canvas):
                    canvas = child
                    # Get current scroll position as fraction (0.0 to 1.0)
                    try:
                        # Get scroll region to calculate proper fraction
                        scroll_region = canvas.cget('scrollregion')
                        if scroll_region:
                            coords = scroll_region.split()
                            if len(coords) == 4:
                                scroll_width = float(coords[2]) - float(coords[0])
                                scroll_height = float(coords[3]) - float(coords[1])
                                if scroll_width > 0:
                                    saved_scroll_x = canvas.canvasx(0) / scroll_width
                                if scroll_height > 0:
                                    saved_scroll_y = canvas.canvasy(0) / scroll_height
                    except Exception:
                        pass
                    break
        except Exception:
            pass
        
        # Close existing window (position already saved above)
        # Clear reference first to prevent any handlers from interfering
        old_window = window
        plugin.route_window_ref = None
        try:
            old_window.destroy()
        except Exception:
            pass
        
        # Ensure window destruction is complete before creating new window
        # Use parent window to update idletasks since old_window is destroyed
        try:
            if plugin.parent:
                plugin.parent.update_idletasks()
        except Exception:
            pass
        
        # Rebuild the window (skip refresh check to avoid recursion)
        show_route_window(plugin, skip_refresh_check=True)
        
        # Verify window was created successfully before restoring scroll position
        if not hasattr(plugin, 'route_window_ref') or not plugin.route_window_ref:
            # Window creation failed, clear refresh flag and return
            plugin._refreshing_route_window = False
            return
        
        # Restore scroll position after window is rebuilt
        if saved_scroll_x > 0 or saved_scroll_y > 0:
            try:
                window = plugin.route_window_ref
                if window and window.winfo_exists():
                    window.update_idletasks()  # Ensure window is fully rendered
                    content_frame = window.winfo_children()[1]
                    main_frame = content_frame.winfo_children()[0]
                    for child in main_frame.winfo_children():
                        if isinstance(child, tk.Canvas):
                            canvas = child
                            canvas.update_idletasks()
                            # Restore scroll position
                            try:
                                canvas.xview_moveto(max(0.0, min(1.0, saved_scroll_x)))
                                canvas.yview_moveto(max(0.0, min(1.0, saved_scroll_y)))
                            except Exception:
                                pass
                            break
            except Exception:
                pass
        
        # Clear refresh flag
        plugin._refreshing_route_window = False
        
    except Exception:
        logger.warning('!! Error refreshing route window: ' + traceback.format_exc(), exc_info=False)
        # Clear refresh flag on error
        if hasattr(plugin, '_refreshing_route_window'):
            plugin._refreshing_route_window = False


def show_route_window(plugin, skip_refresh_check=False):
    """
    Open a window displaying the current route as an easy-to-read list.
    System names are hyperlinked to Inara.cz.
    Shows all columns based on route type with checkboxes for yes/no fields.
    Highlights the current next waypoint row.
    
    Args:
        plugin: The plugin instance
        skip_refresh_check: If True, skip the check for existing window (used by refresh function)
    """
    logger.info(f"[show_route_window] CALLED - route length: {len(plugin.route) if plugin.route else 0}")
    try:
        if not plugin.route or len(plugin.route) == 0:
            logger.info("[show_route_window] No route loaded, showing info dialog")
            # LANG: Info message when no route is loaded
            showinfo(plugin.parent, plugin_tl("View Route"), plugin_tl("No route is currently loaded."))
            return

        # If window is already open, refresh it seamlessly instead of closing
        # (Check this first before the refresh flag check, since refresh intentionally calls this with skip_refresh_check=True)
        if not skip_refresh_check and hasattr(plugin, 'route_window_ref') and plugin.route_window_ref:
            try:
                # Check if window still exists and is valid
                window = plugin.route_window_ref
                if window and window.winfo_exists():
                    # Window exists, refresh it seamlessly
                    _refresh_route_window(plugin)
                    return
                else:
                    # Window doesn't exist, clear reference
                    plugin.route_window_ref = None
            except (tk.TclError, AttributeError):
                # Window was closed or invalid, clear reference and create new one
                plugin.route_window_ref = None
            except Exception:
                # Any other error, clear reference and create new one
                plugin.route_window_ref = None

        # Prevent creating window if refresh is in progress (unless we're the one doing the refresh)
        if not skip_refresh_check and hasattr(plugin, '_refreshing_route_window') and plugin._refreshing_route_window:
            return

        # Use stored full CSV data if available (more efficient than reading file)
        route_data = []
        fieldnames = []
        fieldname_map = {}

        logger.debug(f"[show_route_window] route_full_data length: {len(plugin.route_full_data) if plugin.route_full_data else 0}")
        logger.debug(f"[show_route_window] route_fieldnames: {plugin.route_fieldnames if hasattr(plugin, 'route_fieldnames') else 'N/A'}")
        if plugin.route_full_data and len(plugin.route_full_data) > 0:
            logger.debug(f"[show_route_window] First row keys: {list(plugin.route_full_data[0].keys())}")
        
        if plugin.route_full_data and len(plugin.route_full_data) > 0:
            # Use in-memory full data (preserves all columns from original CSV)
            route_data = plugin.route_full_data
            # Use preserved original fieldnames if available
            if plugin.route_fieldnames:
                fieldnames = plugin.route_fieldnames
                fieldname_map = {name.lower(): name for name in fieldnames}
                logger.debug(f"[show_route_window] Using route_fieldnames: {fieldnames}")
            elif route_data:
                # Fallback: extract from first row keys (will be lowercase)
                fieldnames = list(route_data[0].keys())
                fieldname_map = {name.lower(): name for name in fieldnames}
                logger.debug(f"[show_route_window] Using keys from first row: {fieldnames}")
        elif os.path.exists(plugin.save_route_path):
            # Fallback: read from saved CSV file
            try:
                with open(plugin.save_route_path, 'r', encoding='utf-8-sig', newline='') as csvfile:
                    reader = csv.DictReader(csvfile)
                    fieldnames = reader.fieldnames if reader.fieldnames else []

                    # Create case-insensitive fieldname mapping
                    fieldname_map = {name.lower(): name for name in fieldnames}

                    def get_field(row, field_name, default=""):
                        """Get field value from row using case-insensitive lookup"""
                        key = fieldname_map.get(field_name.lower(), field_name)
                        value = row.get(key, default)
                        # Convert None, "None", or empty strings to empty string
                        if value is None or str(value).strip().lower() == 'none':
                            return default
                        return value

                    # Read all rows and store all fields
                    for row in reader:
                        route_entry = {}
                        for field_name in fieldnames:
                            field_value = get_field(row, field_name, '')
                            # Convert None, "None", or empty strings to empty string for display
                            if field_value is None or str(field_value).strip().lower() == 'none':
                                field_value = ''
                            route_entry[field_name.lower()] = field_value
                        route_data.append(route_entry)
            except Exception:
                logger.warning('!! Error reading route CSV for display: ' + traceback.format_exc(), exc_info=False)
                # LANG: Error reading route CSV file
                showerror(plugin.parent, plugin_tl("Error"), plugin_tl("Failed to read route CSV file."))
                return
        else:
            # No data available
            # LANG: Warning when route file not found
            showwarning(plugin.parent, plugin_tl("Route File Not Found"), plugin_tl("Route CSV file not found. Please import the route again."))
            return
        
        if not route_data:
            # LANG: Info when no route data to display
            showinfo(plugin.parent, plugin_tl("View Route"), plugin_tl("No route data to display."))
            return

        # Detect route type from CSV columns if not already set
        # Check for Road to Riches by looking for Body Name column
        if not plugin.roadtoriches and 'body name' in fieldname_map:
            plugin.roadtoriches = True

        # Detect Fleet Carrier route if not already set (check for Restock Tritium or Icy Ring)
        if not plugin.fleetcarrier:
            if 'restock tritium' in fieldname_map or 'icy ring' in fieldname_map or 'pristine' in fieldname_map:
                plugin.fleetcarrier = True

        # Detect Galaxy route if not already set (check for Refuel column)
        if not plugin.galaxy:
            if 'refuel' in fieldname_map and plugin.system_header.lower() in fieldname_map:
                plugin.galaxy = True

        # Define columns to exclude based on route type
        exclude_columns = set()
        checkbox_columns = set()

        # Fleet Carrier routes: exclude Tritium in tank and Tritium in market
        if plugin.fleetcarrier:
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
        if plugin.galaxy:
            if 'refuel' in fieldname_map:
                checkbox_columns.add('refuel')
            if 'neutron star' in fieldname_map:
                checkbox_columns.add('neutron star')

        # Road to Riches: Is Terraformable is checkbox
        if plugin.roadtoriches:
            if 'is terraformable' in fieldname_map:
                checkbox_columns.add('is terraformable')

        # Neutron Star checkbox: Add for any route type that has this column (except fleet carrier)
        # This ensures Neutron Star shows up for galaxy routes, neutron routes, and any other route type
        if not plugin.fleetcarrier and 'neutron star' in fieldname_map:
            checkbox_columns.add('neutron star')

        # Also detect galaxy route type from CSV if not already set
        if not plugin.galaxy and 'refuel' in fieldname_map and plugin.system_header.lower() in fieldname_map:
            plugin.galaxy = True
            if 'refuel' in fieldname_map:
                checkbox_columns.add('refuel')
            if 'neutron star' in fieldname_map:
                checkbox_columns.add('neutron star')

        # Build list of columns to display
        # Use original fieldnames if available
        display_columns = []  # For display (translated)
        data_columns = []  # For data lookup (original English names)
        logger.debug(f"[show_route_window] Building display columns, fieldnames length: {len(fieldnames)}")
        
        # Create a translation mapping for common column headers
        def translate_column_header(header):
            """Translate column header if it's a known string, otherwise return as-is."""
            # Common headers across all route types
            header_translations = {
                "System Name": plugin_tl("System Name"),
                "Distance": plugin_tl("Distance"),
                "Distance To Arrival": plugin_tl("Distance To Arrival"),
                "Distance Remaining": plugin_tl("Distance Remaining"),
                "Jumps": plugin_tl("Jumps"),
                "Fuel Left": plugin_tl("Fuel Left"),
                "Fuel Used": plugin_tl("Fuel Used"),
                "Refuel": plugin_tl("Refuel"),
                "Neutron Star": plugin_tl("Neutron Star"),
                # Fleet Carrier specific
                "Tritium in tank": plugin_tl("Tritium in tank"),
                "Tritium in market": plugin_tl("Tritium in market"),
                "Icy Ring": plugin_tl("Icy Ring"),
                "Pristine": plugin_tl("Pristine"),
                "Restock Tritium": plugin_tl("Restock Tritium"),
                # Road to Riches specific
                "Body Name": plugin_tl("Body Name"),
                "Body Subtype": plugin_tl("Body Subtype"),
                "Is Terraformable": plugin_tl("Is Terraformable"),
                "Estimated Scan Value": plugin_tl("Estimated Scan Value"),
                "Estimated Mapping Value": plugin_tl("Estimated Mapping Value"),
            }
            return header_translations.get(header, header)
        
        if fieldnames:
            # Use original fieldnames from CSV header
            for field in fieldnames:
                field_lower = field.lower()
                # Always exclude excluded columns
                if field_lower in exclude_columns:
                    logger.debug(f"[show_route_window] Excluding column: {field}")
                    continue
                # Keep original field for data lookup
                data_columns.append(field)
                # Translate the header for display only
                translated_field = translate_column_header(field)
                display_columns.append(translated_field)
            logger.debug(f"[show_route_window] Display columns from fieldnames: {display_columns}")
        elif route_data and len(route_data) > 0:
            # Fallback: use keys from first route entry (convert back to title case if possible)
            for key in route_data[0].keys():
                if key not in exclude_columns:
                    # Convert key back to title case for display (e.g., "system name" -> "System Name")
                    display_name = key.replace('_', ' ').title()
                    # Keep original key for data lookup
                    data_columns.append(display_name)
                    # Translate the header for display only
                    translated_display_name = translate_column_header(display_name)
                    display_columns.append(translated_display_name)
            logger.debug(f"[show_route_window] Display columns from keys: {display_columns}")

        # For Road to Riches, track previous system name to avoid repetition
        prev_system_name = None

        # Create new window with custom themed title bar
        # Initialize window_positions if it doesn't exist
        if not hasattr(plugin, 'window_positions'):
            plugin.window_positions = {}
        saved_positions = plugin.window_positions
        
        # Double-check that no window exists before creating (safety check)
        if hasattr(plugin, 'route_window_ref') and plugin.route_window_ref:
            try:
                if plugin.route_window_ref.winfo_exists():
                    # Window still exists, should not happen if skip_refresh_check is True
                    # But if it does, destroy it first
                    logger.warning("Route window still exists when creating new one, destroying old window first")
                    old_window = plugin.route_window_ref
                    plugin.route_window_ref = None
                    try:
                        old_window.destroy()
                        if plugin.parent:
                            plugin.parent.update_idletasks()
                    except Exception:
                        pass
            except (tk.TclError, AttributeError):
                # Window doesn't exist, clear reference
                plugin.route_window_ref = None
        
        route_window, content_frame = create_themed_window(
            plugin.parent,
            plugin_tl("Route View"),
            saved_positions=saved_positions
        )

        # Store reference to this window for dynamic updates
        plugin.route_window_ref = route_window

        # Wrap the window manager's close function to also clear our reference
        original_close = route_window._close_func
        def on_window_close():
            if plugin.route_window_ref == route_window:
                plugin.route_window_ref = None
            # Call the original close function which saves position and destroys window
            original_close()
        
        # Update the close button's command to use our wrapper
        # Find the close button by searching for the '✕' text in title bar
        try:
            title_bar = route_window.winfo_children()[0]  # First child is title_bar
            for child in title_bar.winfo_children():
                if isinstance(child, tk.Button):
                    try:
                        if child.cget('text') == '✕':
                            child.config(command=on_window_close)
                            break
                    except Exception:
                        pass
        except Exception:
            # Fallback: update the stored function (though button won't use it)
            route_window._close_func = on_window_close

        # Create main container with horizontal and vertical scrolling
        # Use content_frame from create_themed_window instead of creating new frame
        main_frame = content_frame

        # Create horizontal scrollbar (initially hidden)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL)
        
        # Create vertical scrollbar (initially hidden)
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL)

        # Wrapper functions to auto-show/hide scrollbars based on whether scrolling is needed
        def safe_h_scrollbar_set(*args):
            h_scrollbar.set(*args)
            # Auto-show/hide horizontal scrollbar
            # args are (first, last) where both are 0.0-1.0
            # If first=0.0 and last=1.0, all content is visible (no scrolling needed)
            # Use larger tolerance (0.98) to account for rounding, pixel alignment, and padding
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    # All content visible, hide scrollbar
                    h_scrollbar.pack_forget()
                else:
                    # Scrolling needed, show scrollbar
                    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X, before=canvas)
        
        def safe_v_scrollbar_set(*args):
            v_scrollbar.set(*args)
            # Auto-show/hide vertical scrollbar
            # Use larger tolerance (0.98) to account for rounding, pixel alignment, and padding
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    # All content visible, hide scrollbar
                    v_scrollbar.pack_forget()
                else:
                    # Scrolling needed, show scrollbar
                    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, before=canvas)

        # Create canvas with both scrollbars
        canvas = ThemeSafeCanvas(main_frame,
                        xscrollcommand=safe_h_scrollbar_set,
                        yscrollcommand=safe_v_scrollbar_set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        theme.update(canvas)

        h_scrollbar.config(command=canvas.xview)
        v_scrollbar.config(command=canvas.yview)

        # Style scrollbars to match EDMC theme
        style_scrollbars(h_scrollbar, v_scrollbar, main_frame)

        scrollable_frame = tk.Frame(canvas)

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        theme.update(scrollable_frame)

        # Update canvas scroll region when frame size changes
        def on_frame_configure(event):
            # Always update scroll region so scrollbars can update during resize
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            # Only update canvas window width if NOT resizing (prevents horizontal thrashing)
            if hasattr(route_window, '_is_resizing') and route_window._is_resizing:
                return
            
            # Only update canvas window width if content is narrower than canvas
            # This allows horizontal scrolling when content is wider than canvas
            canvas_width = canvas.winfo_width()
            if canvas_width > 1:  # Only update if canvas has been rendered
                canvas_window_id = canvas.find_all()
                if canvas_window_id:
                    # Get the actual content width from the scrollable frame
                    content_width = scrollable_frame.winfo_reqwidth()
                    # Only set width if content is narrower than canvas (to fill available space)
                    # If content is wider, let it be wider to enable horizontal scrolling
                    if content_width < canvas_width:
                        canvas.itemconfig(canvas_window_id[0], width=canvas_width)
                    else:
                        # Reset width to allow natural content width
                        canvas.itemconfig(canvas_window_id[0], width=content_width)

        scrollable_frame.bind("<Configure>", on_frame_configure)

        # Also bind to canvas resize
        def on_canvas_configure(event):
            # Always update scroll region so scrollbars can update during resize
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            # Only update canvas window width if NOT resizing (prevents horizontal thrashing)
            if hasattr(route_window, '_is_resizing') and route_window._is_resizing:
                return
            
            canvas_width = event.width
            canvas_window_id = canvas.find_all()
            if canvas_window_id:
                # Get the actual content width from the scrollable frame
                content_width = scrollable_frame.winfo_reqwidth()
                # Only set width if content is narrower than canvas
                if content_width < canvas_width:
                    canvas.itemconfig(canvas_window_id[0], width=canvas_width)
                else:
                    # Reset width to allow natural content width
                    canvas.itemconfig(canvas_window_id[0], width=content_width)

        canvas.bind('<Configure>', on_canvas_configure)

        # Create a single table frame that will contain both header and data rows in one grid
        table_frame = tk.Frame(scrollable_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        theme.update(table_frame)
        # Force update to ensure theme colors are applied before reading background
        table_frame.update_idletasks()

        # Add step number as first column, and EDSM button before System Name
        # Check if System Name is in data_columns (original names) and insert EDSM before it
        # Build parallel lists: data_columns_with_edsm (for lookups) and display_columns_with_edsm (for display)
        data_columns_with_edsm = []
        display_columns_with_edsm = []
        edsm_inserted = False
        system_name_index = -1
        for idx, (data_col, display_col) in enumerate(zip(data_columns, display_columns)):
            # Check using original English name for data lookup
            if data_col.lower() == plugin.system_header.lower() and not edsm_inserted:
                system_name_index = idx
                data_columns_with_edsm.append("EDSM")
                display_columns_with_edsm.append(plugin_tl("EDSM"))  # EDSM stays as EDSM but wrap it anyway
                edsm_inserted = True
            data_columns_with_edsm.append(data_col)
            display_columns_with_edsm.append(display_col)

        # If System Name wasn't found, just add EDSM at the beginning (after step number)
        if not edsm_inserted:
            data_columns_with_edsm = ["EDSM"] + data_columns
            display_columns_with_edsm = [plugin_tl("EDSM")] + display_columns

        headers = ["#"] + display_columns_with_edsm
        # Calculate column widths based on both header and data content using pixel measurements
        # Get fonts for accurate width calculation
        header_font_route = tkfont.Font(family="Arial", size=9, weight="bold")
        data_font_route = tkfont.Font(family="Arial", size=9)
        
        # Start with header widths (in pixels)
        column_widths_px_route = [header_font_route.measure("#") + 20]  # Step number column
        for h in display_columns_with_edsm:
            if h == "EDSM":
                column_widths_px_route.append(header_font_route.measure("EDSM") + 20)
            else:
                column_widths_px_route.append(header_font_route.measure(h) + 20)

        # Now check all data rows to find maximum content width for each column
        # Iterate through headers (skip step number "#" at index 0)
        # For Road to Riches, this nested loop can be expensive, so yield to event loop periodically
        yield_interval_width = 500 if plugin.roadtoriches else 1000  # Yield more frequently for Road to Riches

        for header_idx, (data_col_name, display_col_name) in enumerate(zip(data_columns_with_edsm, display_columns_with_edsm), start=1):
            # Skip EDSM column (it's fixed width based on header)
            if data_col_name == "EDSM":
                continue

            # Use original English name for data lookup
            field_lower = data_col_name.lower()

            # Check all route entries for this column
            for idx, route_entry in enumerate(route_data):
                # Get value from route_entry using original English field name
                raw_value = route_entry.get(field_lower, '')
                if raw_value is None or str(raw_value).strip().lower() == 'none':
                    value = ''
                else:
                    value = str(raw_value).strip() if isinstance(raw_value, str) else str(raw_value)

                # For Road to Riches, handle system name repetition
                # This adds extra dictionary lookups which can be expensive in the nested loop
                if plugin.roadtoriches and field_lower == plugin.system_header.lower():
                    # Use previous system name if current is empty
                    if not value and idx > 0:
                        prev_entry = route_data[idx - 1]
                        if field_lower in prev_entry:
                            value = prev_entry.get(field_lower, '').strip()

                # Calculate pixel width needed for this value (add 20px padding)
                if value:
                    value_width_px = data_font_route.measure(str(value)) + 20
                    # Update column width if this value is wider
                    # header_idx corresponds to column_widths_px_route index (header_idx already accounts for step number)
                    if header_idx < len(column_widths_px_route):
                        column_widths_px_route[header_idx] = max(column_widths_px_route[header_idx], value_width_px)
                
                # Periodically yield to event loop during column width calculation (especially important for Road to Riches)
                # This prevents blocking during the nested loop iteration
                total_iterations = header_idx * len(route_data) + idx
                if total_iterations > 0 and total_iterations % yield_interval_width == 0 and plugin.parent:
                    plugin.parent.update_idletasks()

        # Calculate required width based on actual pixel measurements
        # Account for separators (one between each column, ~2px each)
        num_separators = len(headers) - 1
        separator_width = num_separators * 2
        # Sum up actual pixel widths plus separators and margins
        total_column_width = sum(column_widths_px_route) + separator_width + 75  # Add margin to prevent horizontal scrollbar
        screen_width = route_window.winfo_screenwidth()
        # Open window wide enough to show all columns, but don't exceed screen width
        # If content is wider than screen, user can scroll horizontally
        window_width = min(total_column_width, screen_width - 20)  # Leave small margin from screen edges
        # Ensure minimum width so content isn't cut off
        window_width = max(window_width, 800)  # At least 800px wide
        
        # Configure grid columns to use pixel-based widths for tight, automatic sizing
        for i, width_px in enumerate(column_widths_px_route):
            # Each data column uses column index i*2 (separators use i*2+1)
            table_frame.grid_columnconfigure(i*2, minsize=width_px, weight=0)
            # Separator columns (if not last column)
            if i < len(column_widths_px_route) - 1:
                table_frame.grid_columnconfigure(i*2+1, minsize=2, weight=0)

        # Determine which columns should be right-aligned (numeric columns)
        # Exclude checkbox columns (Refuel, Neutron Star, etc.) - they should be left-aligned
        numeric_columns = set()
        checkbox_column_names = set(checkbox_columns)
        for field_name in data_columns:  # Use original English names
            field_lower = field_name.lower()
            # Only right-align pure numeric columns, not checkbox columns
            if field_lower not in checkbox_column_names:
                if any(keyword in field_lower for keyword in ['distance', 'fuel used', 'fuel left', 'estimated scan value', 'estimated mapping value', 'jumps']):
                    numeric_columns.add(field_lower)

        # Header row (row 0) - styled with grey background and bold text
        header_row = 0
        for i, header in enumerate(headers):
            # Grid column configuration handles width, just create label with proper anchor
            # Right-align numeric columns, left-align text columns, center-align checkbox columns
            header_lower = header.lower()
            if i == 0:  # Step number - left align
                anchor = "w"
                sticky_val = tk.W
            elif header_lower == "edsm":  # EDSM button column - center align
                anchor = "c"
                sticky_val = tk.EW
            elif header_lower in checkbox_columns:
                anchor = "c"  # Center-align for indicator columns (colored dots)
                sticky_val = tk.EW  # Expand to fill column width for centering
            elif header_lower in numeric_columns:
                anchor = "e"  # Right-align for numeric columns
                sticky_val = tk.E
            else:
                anchor = "w"  # Left-align for text columns
                sticky_val = tk.W
            # Header label with grey background and bold text
            label = tk.Label(table_frame, text=header, font=("Arial", 9, "bold"), anchor=anchor)
            label.grid(row=header_row, column=i*2, padx=2, pady=5, sticky=sticky_val)
            theme.update(label)
            # Add vertical separator after each column (except the last)
            if i < len(headers) - 1:
                separator = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator.grid(row=header_row, column=i*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator)
                # ttk.Separator needs additional styling via ttk.Style
                # We'll configure this after all widgets are created

        # Get current next waypoint system name for highlighting
        # Use the same helper method that the plugin uses to get the system name
        # This ensures consistency between navigation and display
        # IMPORTANT: Don't modify plugin state - only read from it
        current_next_waypoint = None
        if hasattr(plugin, 'offset') and plugin.offset is not None and hasattr(plugin, 'route') and plugin.route:
            try:
                # Ensure offset is valid before using it
                if plugin.offset >= 0 and plugin.offset < len(plugin.route):
                    # Use the plugin's helper method to get the system name at the current offset
                    # This handles empty system names for Road to Riches correctly
                    if hasattr(plugin, '_get_system_name_at_index'):
                        current_next_waypoint = plugin._get_system_name_at_index(plugin.offset)
                    else:
                        # Fallback to next_stop if helper method doesn't exist
                        current_next_waypoint = getattr(plugin, 'next_stop', None)
                else:
                    # Offset is out of bounds, use next_stop as fallback
                    current_next_waypoint = getattr(plugin, 'next_stop', None)
            except Exception:
                # Fallback to next_stop on any error
                current_next_waypoint = getattr(plugin, 'next_stop', None)
        else:
            current_next_waypoint = getattr(plugin, 'next_stop', None)
        
        if current_next_waypoint and current_next_waypoint == "No route planned":
            current_next_waypoint = None

        # Calculate alternating row colors for better readability
        table_frame.update_idletasks()
        try:
            base_bg = table_frame.cget('bg')
            
            # Detect theme first to determine appropriate base color
            try:
                from config import config  # type: ignore
                current_theme = config.get_int('theme')
                is_dark = current_theme in [1, 2]  # 1 = dark, 2 = transparent (dark)
            except:
                # Fallback: detect from background color
                is_dark = (isinstance(base_bg, str) and 
                          base_bg.lower() in ['black', '#000000', '#1e1e1e', 'systemwindow'])
            
            # Determine base_row_bg based on theme, not just background color
            # For transparent theme (theme=2), base_bg might be 'systemwindow' which we should use
            if base_bg and base_bg.strip():
                # For dark/transparent themes, use the background even if it's 'systemwindow'
                if is_dark:
                    # Dark/transparent theme: use the background color (including 'systemwindow')
                    base_row_bg = base_bg
                else:
                    # Light theme: exclude white/systemwindow
                    if base_bg.lower() not in ['white', '#ffffff', 'systemwindow', 'systembuttonface']:
                        base_row_bg = base_bg
                    else:
                        # Light theme with systemwindow - use white
                        base_row_bg = '#ffffff'
            else:
                # No background color detected - use theme-appropriate default
                base_row_bg = '#1e1e1e' if is_dark else '#ffffff'
            
            # Create alternating color - slightly lighter for dark mode, slightly darker for light mode
            if base_row_bg and base_row_bg != "":
                if is_dark:
                    # Dark mode: alternate with slightly lighter shade
                    try:
                        if base_row_bg.startswith('#'):
                            rgb = tuple(int(base_row_bg[i:i+2], 16) for i in (1, 3, 5))
                            alt_rgb = tuple(min(255, c + 15) for c in rgb)  # Lighten by 15
                            alt_row_bg = f"#{alt_rgb[0]:02x}{alt_rgb[1]:02x}{alt_rgb[2]:02x}"
                        else:
                            # Named color (e.g., 'systemwindow') - use a fixed lighter shade for dark theme
                            # Convert to a slightly lighter dark gray
                            alt_row_bg = '#2a2a2a'  # Lighter than typical dark theme background
                    except:
                        alt_row_bg = '#2a2a2a' if is_dark else '#e5e5e5'
                else:
                    # Light mode: alternate with slightly darker shade
                    try:
                        if base_row_bg.startswith('#'):
                            rgb = tuple(int(base_row_bg[i:i+2], 16) for i in (1, 3, 5))
                            alt_rgb = tuple(max(0, c - 15) for c in rgb)  # Darken by 15
                            alt_row_bg = f"#{alt_rgb[0]:02x}{alt_rgb[1]:02x}{alt_rgb[2]:02x}"
                        else:
                            # Named color (e.g., 'systemwindow') - use a fixed darker shade for light theme
                            alt_row_bg = '#e5e5e5'  # Slightly darker than white
                    except:
                        alt_row_bg = '#2a2a2a' if is_dark else '#e5e5e5'
            else:
                alt_row_bg = ""
        except Exception:
            base_row_bg = ""
            alt_row_bg = ""

        # Route data rows (rows 1+) - use same grid as header for perfect alignment
        # Track which system we've already highlighted to avoid highlighting multiple rows for the same system
        highlighted_system = None
        
        # For Road to Riches files (which can have many rows), yield to event loop periodically
        # to prevent blocking GUI updates. Process in batches and call update_idletasks() every N rows.
        yield_interval = 50 if plugin.roadtoriches else 100  # Yield more frequently for Road to Riches

        for idx, route_entry in enumerate(route_data):
            data_row = idx + 1  # Start from row 1 (row 0 is header)

            # Get system name from this row for comparison
            # For Road to Riches, we need to track the actual system name even if it's not displayed
            system_name_in_row = None
            system_field_lower = plugin.system_header.lower()
            if system_field_lower in route_entry:
                system_name_in_row = route_entry.get(system_field_lower, '').strip()

            # For Road to Riches, if system name is empty in this row, use previous system name
            # BUT only for display purposes - for highlighting, we only highlight rows that actually have the system name
            display_system_name = system_name_in_row
            if plugin.roadtoriches and not system_name_in_row and idx > 0:
                # Check previous entry for system name (for display only)
                prev_entry = route_data[idx - 1]
                if system_field_lower in prev_entry:
                    display_system_name = prev_entry.get(system_field_lower, '').strip()

            # Check if this row matches the current next waypoint
            # For Road to Riches: Only highlight the FIRST row that has the system name (not rows with empty system names)
            # This ensures we highlight the system location, not individual bodies
            is_current_waypoint = False
            if current_next_waypoint:
                # For Road to Riches, only highlight if this row actually has the system name (not empty)
                if plugin.roadtoriches:
                    if system_name_in_row and system_name_in_row.lower() == current_next_waypoint.lower():
                        # Only highlight if we haven't already highlighted this system
                        if highlighted_system != current_next_waypoint.lower():
                            is_current_waypoint = True
                            highlighted_system = current_next_waypoint.lower()
                else:
                    # For other route types, use the display system name
                    if display_system_name and display_system_name.lower() == current_next_waypoint.lower():
                        is_current_waypoint = True

            # Get row background color from theme AFTER theme.update() has been applied
            # Highlight current waypoint with yellow background - text color handled by theme
            # Use alternating colors for better readability when not highlighted
            if is_current_waypoint:
                # Always use yellow highlight - theme system will adjust text color for readability
                row_bg = "#fff9c4"  # Light yellow highlight for current waypoint
            else:
                # Alternate row background color for better readability
                row_bg = base_row_bg if idx % 2 == 0 else alt_row_bg

            col_idx = 0

            # Step number
            label_kwargs = {"master": table_frame, "text": str(idx + 1), "anchor": "w"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            step_label = tk.Label(**label_kwargs)
            step_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(step_label)
            # For highlighted rows, set text to black for readability (except URLs which stay blue)
            if is_current_waypoint:
                step_label.config(foreground="black")
            # Add separator after step number
            if col_idx < len(headers) - 1:
                separator_step = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator_step.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator_step)
            col_idx += 1

            # Display each column - use column_widths to match header widths
            # Note: We iterate through data_columns (original English names) for data lookup
            for field_idx, (data_field_name, display_field_name) in enumerate(zip(data_columns, display_columns)):
                field_lower = data_field_name.lower()  # Use original English name for lookup
                # Get value from route_entry (which uses lowercase keys)
                raw_value = route_entry.get(field_lower, '')
                # Convert to string and handle None/"None" values
                if raw_value is None or str(raw_value).strip().lower() == 'none':
                    value = ''
                else:
                    value = str(raw_value).strip() if isinstance(raw_value, str) else str(raw_value)

                # Special handling: Add EDSM button before System Name
                if field_lower == plugin.system_header.lower():
                    # EDSM column comes right before System Name in headers
                    # Add EDSM button first

                    # Get the system name value for EDSM button
                    system_name_for_edsm = None
                    if plugin.roadtoriches:
                        current_system = value
                        system_name_for_edsm = current_system if current_system and current_system.lower() != prev_system_name else None
                    else:
                        system_name_for_edsm = value if value else None

                    if system_name_for_edsm:
                        btn_kwargs = {"master": table_frame, "text": "EDSM", "command": lambda s=system_name_for_edsm: plugin.open_edsm_system(s)}
                        if row_bg:
                            btn_kwargs["bg"] = row_bg
                        edsm_btn = tk.Button(**btn_kwargs)
                        edsm_btn.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                        theme.update(edsm_btn)
                    else:
                        # Empty cell if no system name
                        label_kwargs = {"master": table_frame, "text": ""}
                        if row_bg:
                            label_kwargs["bg"] = row_bg
                        empty_label = tk.Label(**label_kwargs)
                        empty_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                        theme.update(empty_label)
                        # For highlighted rows, set text to black for readability
                        if is_current_waypoint:
                            empty_label.config(foreground="black")
                    if col_idx < len(headers) - 1:
                        separator_edsm = ttk.Separator(table_frame, orient=tk.VERTICAL)
                        separator_edsm.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                        theme.update(separator_edsm)
                    col_idx += 1

                    # Now add System Name at the next column position

                    # Handle System Name display
                    # For Road to Riches, check if system name repeats
                    if plugin.roadtoriches:
                        current_system = value
                        if current_system and current_system.lower() == prev_system_name:
                            # System name repeats, show empty
                            label_kwargs = {"master": table_frame, "text": "", "anchor": "w"}
                            if row_bg:
                                label_kwargs["bg"] = row_bg
                            system_label = tk.Label(**label_kwargs)
                            system_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                            theme.update(system_label)
                            # For highlighted rows, set text to black for readability
                            if is_current_waypoint:
                                system_label.config(foreground="black")
                        else:
                            # New system name, display it (with right-click copy)
                            if current_system:
                                system_label = HyperlinkLabel(
                                    table_frame,
                                    text=current_system,
                                    url=lambda e, s=current_system: plugin.open_inara_system(s),
                                    popup_copy=True,
                                    anchor="w"
                                )
                                system_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                                theme.update(system_label)
                            else:
                                label_kwargs = {"master": table_frame, "text": "", "anchor": "w"}
                                if row_bg:
                                    label_kwargs["bg"] = row_bg
                                empty_label = tk.Label(**label_kwargs)
                                empty_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                                theme.update(empty_label)
                                # For highlighted rows, set text to black for readability
                                if is_current_waypoint:
                                    empty_label.config(foreground="black")
                        prev_system_name = current_system.lower() if current_system else None
                    else:
                        # Normal system name display (clickable to Inara, right-click to copy)
                        if value:
                            system_label = HyperlinkLabel(
                                table_frame,
                                text=value,
                                url=lambda e, s=value: plugin.open_inara_system(s),
                                popup_copy=True,
                                anchor="w"
                            )
                            system_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                            theme.update(system_label)
                        else:
                            label_kwargs = {"master": table_frame, "text": "", "anchor": "w"}
                            if row_bg:
                                label_kwargs["bg"] = row_bg
                            empty_label = tk.Label(**label_kwargs)
                            empty_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
                            theme.update(empty_label)
                            # For highlighted rows, set text to black for readability
                            if is_current_waypoint:
                                empty_label.config(foreground="black")

                    # Add separator after System Name and move to next column
                    if col_idx < len(headers) - 1:
                        separator_system = ttk.Separator(table_frame, orient=tk.VERTICAL)
                        separator_system.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                        theme.update(separator_system)
                    col_idx += 1
                    continue  # Skip the rest of the loop for System Name since we've handled it

                # Checkbox columns (yes/no fields) - display as colored dot indicator
                if field_lower in checkbox_columns:
                    # Strip whitespace and convert to lowercase for comparison
                    checkbox_value_str = str(value).strip().lower() if value else ''
                    checkbox_value = checkbox_value_str == 'yes'

                    # Determine dot color based on field type
                    # Neutron Star uses light blue, others use red
                    if field_lower == 'neutron star':
                        dot_color = "lightblue"
                        dot_outline = "blue"
                    else:
                        dot_color = "red"
                        dot_outline = "darkred"

                    # Create a frame to center the canvas within the column
                    frame_kwargs = {"master": table_frame}
                    if row_bg:
                        frame_kwargs["bg"] = row_bg
                    checkbox_frame = tk.Frame(**frame_kwargs)
                    checkbox_frame.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.EW)
                    theme.update(checkbox_frame)

                    # Create a canvas to draw a colored dot (centered in frame)
                    canvas_kwargs = {"master": checkbox_frame, "width": 40, "height": 40, "highlightthickness": 0}
                    if row_bg:
                        canvas_kwargs["bg"] = row_bg
                    checkbox_canvas = ThemeSafeCanvas(**canvas_kwargs)
                    checkbox_canvas.pack(anchor=tk.CENTER)  # Center the canvas in the frame

                    if checkbox_value:
                        # Draw a filled circle for "yes" (light blue for neutron star, red for others)
                        checkbox_canvas.create_oval(10, 10, 30, 30, fill=dot_color, outline=dot_outline, width=2)
                    else:
                        # Draw an empty circle for "no" (or leave blank)
                        checkbox_canvas.create_oval(10, 10, 30, 30, fill=row_bg, outline="lightgray", width=2)

                # Regular text columns - right-align numeric columns, left-align others
                else:
                    # Determine if this is a numeric column
                    is_numeric = field_lower in numeric_columns

                    # Process the value - handle None, "None", empty strings
                    display_value = value if value else ""
                    if display_value is None or str(display_value).strip().lower() == 'none':
                        display_value = ""

                    # Round distance and fuel columns UP to nearest hundredth if they're numeric
                    if is_numeric and field_lower in ["distance to arrival", "distance remaining", "distance", "fuel used", "fuel left"]:
                        if display_value:  # Only process if not empty
                            try:
                                val_float = float(display_value)
                                # Round UP to nearest hundredth: multiply by 100, ceil, divide by 100
                                rounded = math.ceil(val_float * 100) / 100
                                display_value = f"{rounded:.2f}"
                            except (ValueError, TypeError):
                                pass  # Keep original value if not a number

                    anchor = "e" if is_numeric else "w"
                    sticky = tk.E if is_numeric else tk.W
                    # Use col_width which now matches header width calculation exactly
                    label_kwargs = {"master": table_frame, "text": display_value, "anchor": anchor}
                    if row_bg:
                        label_kwargs["bg"] = row_bg
                    value_label = tk.Label(**label_kwargs)
                    value_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=sticky)
                    theme.update(value_label)
                    # For highlighted rows, set text to black for readability (except URLs which stay blue)
                    if is_current_waypoint:
                        # Don't change foreground if it's a URL/link (blue color)
                        try:
                            current_fg = value_label.cget('foreground')
                            if current_fg and current_fg.lower() not in ['blue', '#0000ff', '#0000ff']:
                                value_label.config(foreground="black")
                        except Exception:
                            value_label.config(foreground="black")

                # Add separator after each column (except the last)
                if col_idx < len(headers) - 1:
                    separator = ttk.Separator(table_frame, orient=tk.VERTICAL)
                    separator.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                    theme.update(separator)

                col_idx += 1
            
            # Periodically yield to event loop to prevent blocking (especially important for Road to Riches)
            # This allows button updates and other GUI events to process during window creation
            if (idx + 1) % yield_interval == 0:
                table_frame.update_idletasks()
                if plugin.parent:
                    plugin.parent.update_idletasks()
                    if hasattr(plugin, 'waypoint_btn') and hasattr(plugin, 'next_stop'):
                        try:
                            current_button_text = plugin.waypoint_btn.cget('text')
                            expected_text = plugin.next_wp_label + '\n' + (plugin.next_stop if plugin.next_stop else "")
                            if current_button_text != expected_text:
                                logger.warning(f'[show_route_window] Button text mismatch at row {idx + 1}: expected="{expected_text[:50]}...", actual="{current_button_text[:50]}..."')
                        except Exception:
                            pass

        # Apply theme recursively to entire table_frame after all widgets are created
        # This ensures any widgets we missed get themed properly
        # theme.update() will automatically apply correct foreground colors based on current theme
        theme.update(table_frame)

        # For highlighted rows, override theme colors with black text for readability (except URLs which stay blue)
        # This must be done AFTER theme.update() to override theme colors
        def set_highlighted_text_black():
            """Set text to black for all labels in highlighted rows, preserving blue URLs."""
            # Find the highlighted row by looking for labels with yellow background
            for widget in table_frame.winfo_children():
                try:
                    if isinstance(widget, tk.Label):
                        widget_bg = widget.cget('bg')
                        # Check if this label has the yellow highlight background
                        if widget_bg and widget_bg.lower() in ['#fff9c4', '#fff9c4']:
                            # This is a highlighted row - set text to black unless it's a URL
                            current_fg = widget.cget('foreground')
                            current_cursor = widget.cget('cursor')
                            # Keep blue links as blue, set everything else to black
                            if current_fg and current_fg.lower() in ['blue', '#0000ff', '#0000ff']:
                                pass  # Keep blue URLs
                            elif current_cursor == 'hand2':
                                pass  # Keep links (hand2 cursor indicates clickable)
                            else:
                                widget.config(foreground="black")
                    elif isinstance(widget, tk.Button):
                        # Check buttons too - but only their text/foreground
                        widget_bg = widget.cget('bg')
                        if widget_bg and widget_bg.lower() in ['#fff9c4', '#fff9c4']:
                            current_fg = widget.cget('foreground')
                            if current_fg and current_fg.lower() not in ['blue', '#0000ff', '#0000ff']:
                                widget.config(foreground="black")
                except Exception:
                    pass

        # Apply black text to highlighted rows AFTER theme.update()
        set_highlighted_text_black()

        # Style ttk.Separator widgets - they need special handling via ttk.Style
        # Separators don't automatically get themed, so we style them to match theme foreground color
        try:
            separator_style = ttk.Style()
            # Get theme foreground color from a label to match separator color
            sample_label = tk.Label(table_frame)
            theme.update(sample_label)
            try:
                theme_fg = sample_label.cget('foreground')
                if theme_fg:
                    # Configure separator background to match theme foreground color
                    separator_style.configure('TSeparator', background=theme_fg)
            except Exception:
                pass
            sample_label.destroy()
        except Exception:
            pass

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

        # Bind mousewheel scrolling after all widgets are created
        def on_mousewheel(event):
            # Scroll vertically with mousewheel
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def on_shift_mousewheel(event):
            # Scroll horizontally with Shift+mousewheel
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        
        # Recursively bind mousewheel to all widgets in the window
        def bind_mousewheel_recursive(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Shift-MouseWheel>", on_shift_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel_recursive(child)
        
        bind_mousewheel_recursive(route_window)

        # Restore window position or center on screen
        # The window manager handles close button in title bar, so no need for separate close button
        restore_window_position(route_window, "Route View", saved_positions, final_width, 700)
        
        # CRITICAL: Ensure plugin route state remains valid after window creation
        if hasattr(plugin, 'route') and hasattr(plugin, 'offset'):
            try:
                old_offset = plugin.offset
                old_next_stop = getattr(plugin, 'next_stop', None)
                if plugin.offset is not None:
                    if plugin.offset < 0:
                        logger.warning(f'[show_route_window] Offset was negative ({plugin.offset}), correcting')
                        plugin.offset = 0
                    if plugin.offset >= len(plugin.route):
                        logger.warning(f'[show_route_window] Offset ({plugin.offset}) >= route length ({len(plugin.route)}), correcting')
                        plugin.offset = len(plugin.route) - 1 if len(plugin.route) > 0 else 0
                    # Ensure next_stop is still valid
                    if plugin.offset < len(plugin.route) and hasattr(plugin, '_get_system_name_at_index'):
                        display_system_name = plugin._get_system_name_at_index(plugin.offset)
                        if display_system_name and hasattr(plugin, 'next_stop'):
                            plugin.next_stop = display_system_name
                if old_offset != plugin.offset:
                    logger.warning(f'[show_route_window] Offset changed during window creation: {old_offset} -> {plugin.offset}')
            except Exception as e:
                logger.warning(f'[show_route_window] Error validating plugin state: {e}', exc_info=True)

        # After window is positioned, update saved position with actual window size
        # This ensures the saved position reflects the correct size for this route's columns
        try:
            route_window.update_idletasks()
            actual_width = route_window.winfo_width()
            actual_height = route_window.winfo_height()
            actual_x = route_window.winfo_x()
            actual_y = route_window.winfo_y()
            # Only update if the width changed (new route might need different width)
            if saved_positions and "Route View" in saved_positions:
                old_x, old_y, old_width, old_height = saved_positions["Route View"]
                if old_width != actual_width:
                    # Width changed, update saved position with new size
                    saved_positions["Route View"] = (actual_x, actual_y, actual_width, actual_height)
        except Exception:
            pass

    except Exception as e:
        logger.error(f'[show_route_window] Exception during window creation: {e}', exc_info=True)
        logger.warning('!! Error showing route window: ' + traceback.format_exc(), exc_info=False)
        # Clear window reference on error to prevent orphaned windows
        if hasattr(plugin, 'route_window_ref'):
            try:
                if plugin.route_window_ref and plugin.route_window_ref.winfo_exists():
                    plugin.route_window_ref.destroy()
            except Exception:
                pass
            plugin.route_window_ref = None
        # Clear refresh flag on error
        if hasattr(plugin, '_refreshing_route_window'):
            plugin._refreshing_route_window = False
        # LANG: Error displaying route
        showerror(plugin.parent, plugin_tl("Error"), plugin_tl("Failed to display route."))


def refresh_route_window_if_open(plugin):
    """
    Refresh the route window if it's currently open.
    This is called when the next waypoint changes to update the highlight.
    The window will be rebuilt with the current waypoint highlighted, preserving scroll position.
    """
    if hasattr(plugin, 'route_window_ref') and plugin.route_window_ref:
        try:
            # Check if window still exists
            if plugin.route_window_ref.winfo_exists():
                # Use seamless refresh that preserves scroll position
                _refresh_route_window(plugin)
        except Exception:
            # Window was closed, clear reference
            plugin.route_window_ref = None


def show_cargo_details_window(plugin, callsign: str):
    """
    Open a window displaying detailed cargo information for a specific fleet carrier.
    
    Args:
        plugin: The plugin instance
        callsign: Fleet carrier callsign to display cargo for
    """
    try:
        # Get cargo details from CargoDetailsManager
        if not hasattr(plugin, 'cargo_manager') or not plugin.cargo_manager:
            # LANG: Window title for cargo details (title and message)
            showinfo(plugin.parent, plugin_tl("Cargo Details"), plugin_tl("Cargo manager not available."))
            return
        
        cargo_items = plugin.cargo_manager.get_cargo_for_carrier(callsign)
        
        if not cargo_items:
            # LANG: Window title for cargo details and no data message
            showinfo(plugin.parent, plugin_tl("Cargo Details"), f"{plugin_tl('No cargo data available for')} {callsign}.")
            return
        
        # Create new window with custom themed title bar
        if not hasattr(plugin, 'window_positions'):
            plugin.window_positions = {}
        saved_positions = plugin.window_positions
        
        # LANG: Window title for cargo details window
        window_title = f"{plugin_tl('Cargo Details')} - {callsign}"
        cargo_window, content_frame = create_themed_window(
            plugin.parent,
            window_title,
            saved_positions=saved_positions
        )
        
        # Define headers
        # LANG: Cargo window column headers
        headers = [plugin_tl("Cargo"), plugin_tl("Quantity"), plugin_tl("Value")]
        
        # Get fonts for accurate width calculation
        header_font = tkfont.Font(family="Arial", size=9, weight="bold")
        data_font = tkfont.Font(family="Arial", size=9)
        
        # Initialize column widths based on header text
        column_widths_px = [header_font.measure(h) + 20 for h in headers]
        
        # Sort cargo items alphabetically by localized name
        sorted_cargo = sorted(cargo_items, key=lambda x: x.get('localized_name', '').lower())
        
        # Calculate maximum content width for each column
        for item in sorted_cargo:
            localized_name = item.get('localized_name', 'Unknown')
            quantity = item.get('quantity', '0')
            total_value_raw = item.get('total_value', '0')
            
            # Format value with commas
            try:
                total_value_int = int(total_value_raw) if total_value_raw else 0
                total_value_formatted = f"{total_value_int:,}"
            except (ValueError, TypeError):
                total_value_formatted = str(total_value_raw) if total_value_raw else "0"
            
            # Update column widths
            column_widths_px[0] = max(column_widths_px[0], data_font.measure(str(localized_name)) + 20)
            column_widths_px[1] = max(column_widths_px[1], data_font.measure(str(quantity)) + 20)
            column_widths_px[2] = max(column_widths_px[2], data_font.measure(str(total_value_formatted)) + 20)
        
        # Calculate required width
        num_separators = len(headers) - 1
        separator_width = num_separators * 2
        total_column_width = sum(column_widths_px) + separator_width + 75
        screen_width = cargo_window.winfo_screenwidth()
        window_width = min(total_column_width, screen_width - 20)
        window_width = max(window_width, 400)
        
        # Create main container with scrolling
        main_frame = content_frame
        
        # Create scrollbars
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL)
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL)
        
        def safe_h_scrollbar_set(*args):
            h_scrollbar.set(*args)
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    h_scrollbar.pack_forget()
                else:
                    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X, before=canvas)
        
        def safe_v_scrollbar_set(*args):
            v_scrollbar.set(*args)
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    v_scrollbar.pack_forget()
                else:
                    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, before=canvas)
        
        # Create canvas
        canvas = ThemeSafeCanvas(main_frame,
                                 xscrollcommand=safe_h_scrollbar_set,
                                 yscrollcommand=safe_v_scrollbar_set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        theme.update(canvas)
        
        h_scrollbar.config(command=canvas.xview)
        v_scrollbar.config(command=canvas.yview)
        
        style_scrollbars(h_scrollbar, v_scrollbar, main_frame)
        
        scrollable_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        theme.update(scrollable_frame)
        
        # Update canvas scroll region
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            if hasattr(cargo_window, '_is_resizing') and cargo_window._is_resizing:
                return
            canvas_width = canvas.winfo_width()
            if canvas_width > 1:
                canvas_window_id = canvas.find_all()
                if canvas_window_id:
                    content_width = scrollable_frame.winfo_reqwidth()
                    if content_width < canvas_width:
                        canvas.itemconfig(canvas_window_id[0], width=canvas_width)
                    else:
                        canvas.itemconfig(canvas_window_id[0], width=content_width)
        
        scrollable_frame.bind("<Configure>", on_frame_configure)
        
        def on_canvas_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            if hasattr(cargo_window, '_is_resizing') and cargo_window._is_resizing:
                return
            canvas_width = event.width
            canvas_window_id = canvas.find_all()
            if canvas_window_id:
                content_width = scrollable_frame.winfo_reqwidth()
                if content_width < canvas_width:
                    canvas.itemconfig(canvas_window_id[0], width=canvas_width)
                else:
                    canvas.itemconfig(canvas_window_id[0], width=content_width)
        
        canvas.bind('<Configure>', on_canvas_configure)
        
        # Create table frame
        table_frame = tk.Frame(scrollable_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        theme.update(table_frame)
        table_frame.update_idletasks()
        
        # Configure grid columns
        for i, width_px in enumerate(column_widths_px):
            table_frame.grid_columnconfigure(i*2, minsize=width_px, weight=0)
            if i < len(column_widths_px) - 1:
                table_frame.grid_columnconfigure(i*2+1, minsize=2, weight=0)
        
        # Get base background color for alternating rows
        try:
            from config import config
            current_theme = config.get_int('theme')
            base_bg = table_frame.cget('bg')
            
            try:
                is_dark = current_theme in [1, 2]
            except:
                is_dark = (isinstance(base_bg, str) and 
                          base_bg.lower() in ['black', '#000000', '#1e1e1e', 'systemwindow'])
            
            if base_bg and base_bg.strip():
                if is_dark:
                    base_row_bg = base_bg
                else:
                    if base_bg.lower() not in ['white', '#ffffff', 'systemwindow', 'systembuttonface']:
                        base_row_bg = base_bg
                    else:
                        base_row_bg = '#ffffff'
            else:
                base_row_bg = '#1e1e1e' if is_dark else '#ffffff'
            
            # Create alternating color
            if base_row_bg and base_row_bg != "":
                if is_dark:
                    try:
                        if base_row_bg.startswith('#'):
                            rgb = tuple(int(base_row_bg[i:i+2], 16) for i in (1, 3, 5))
                            alt_rgb = tuple(min(255, c + 15) for c in rgb)
                            alt_row_bg = f"#{alt_rgb[0]:02x}{alt_rgb[1]:02x}{alt_rgb[2]:02x}"
                        else:
                            alt_row_bg = '#2a2a2a'
                    except:
                        alt_row_bg = '#2a2a2a'
                else:
                    try:
                        if base_row_bg.startswith('#'):
                            rgb = tuple(int(base_row_bg[i:i+2], 16) for i in (1, 3, 5))
                            alt_rgb = tuple(max(0, c - 15) for c in rgb)
                            alt_row_bg = f"#{alt_rgb[0]:02x}{alt_rgb[1]:02x}{alt_rgb[2]:02x}"
                        else:
                            alt_row_bg = '#e5e5e5'
                    except:
                        alt_row_bg = '#e5e5e5'
            else:
                alt_row_bg = ""
        except Exception:
            base_row_bg = ""
            alt_row_bg = ""
        
        # Create header row
        for col_idx, header in enumerate(headers):
            header_label = tk.Label(
                table_frame,
                text=header,
                font=header_font,
                anchor="w",
                relief=tk.RAISED,
                borderwidth=1
            )
            header_label.grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.EW)
            theme.update(header_label)
            
            # Add separator after each column except the last
            if col_idx < len(headers) - 1:
                separator = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator.grid(row=0, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator)
        
        # Create data rows
        for idx, item in enumerate(sorted_cargo):
            data_row = idx + 1
            row_bg = base_row_bg if idx % 2 == 0 else alt_row_bg
            
            localized_name = item.get('localized_name', 'Unknown')
            quantity = item.get('quantity', '0')
            total_value_raw = item.get('total_value', '0')
            
            # Format value with commas
            try:
                total_value_int = int(total_value_raw) if total_value_raw else 0
                total_value_formatted = f"{total_value_int:,}"
            except (ValueError, TypeError):
                total_value_formatted = str(total_value_raw) if total_value_raw else "0"
            
            col_idx = 0
            
            # Cargo (Localized Name)
            label_kwargs = {"master": table_frame, "text": localized_name, "anchor": "w"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            cargo_label = tk.Label(**label_kwargs)
            cargo_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(cargo_label)
            if col_idx < len(headers) - 1:
                sep = ttk.Separator(table_frame, orient=tk.VERTICAL)
                sep.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(sep)
            col_idx += 1
            
            # Quantity - right-align numeric
            label_kwargs = {"master": table_frame, "text": quantity, "anchor": "e"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            quantity_label = tk.Label(**label_kwargs)
            quantity_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.E)
            theme.update(quantity_label)
            if col_idx < len(headers) - 1:
                sep = ttk.Separator(table_frame, orient=tk.VERTICAL)
                sep.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(sep)
            col_idx += 1
            
            # Value - right-align numeric with green font
            label_kwargs = {"master": table_frame, "text": total_value_formatted, "anchor": "e", "fg": "green"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            value_label = tk.Label(**label_kwargs)
            value_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.E)
            theme.update(value_label)
        
        # Apply theme to table
        theme.update(table_frame)
        
        # Bind mousewheel scrolling
        def bind_mousewheel_recursive(widget):
            """Recursively bind mousewheel to widget and all children"""
            def on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            def on_shift_mousewheel(event):
                canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
            
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Shift-MouseWheel>", on_shift_mousewheel)
            
            for child in widget.winfo_children():
                bind_mousewheel_recursive(child)
        
        bind_mousewheel_recursive(cargo_window)
        
        # Handle window resize
        cargo_window._is_resizing = False
        original_config = cargo_window.winfo_toplevel().config
        
        def on_window_configure(event):
            if event.widget == cargo_window.winfo_toplevel():
                cargo_window._is_resizing = True
                if hasattr(cargo_window, '_resize_after_id'):
                    cargo_window.after_cancel(cargo_window._resize_after_id)
                cargo_window._resize_after_id = cargo_window.after(100, lambda: setattr(cargo_window, '_is_resizing', False))
        
        cargo_window.winfo_toplevel().bind('<Configure>', on_window_configure)
        
        # Set initial window size and position
        cargo_window.update_idletasks()
        window_height = min(600, cargo_window.winfo_screenheight() - 100)
        cargo_window.geometry(f"{window_width}x{window_height}")
        
        # Restore saved position if available, otherwise center and show window
        if saved_positions and window_title in saved_positions:
            restore_window_position(cargo_window, window_title, saved_positions, window_width, window_height)
        else:
            # First time showing window - center on screen
            screen_width = cargo_window.winfo_screenwidth()
            screen_height = cargo_window.winfo_screenheight()
            x = (screen_width // 2) - (window_width // 2)
            y = (screen_height // 2) - (window_height // 2)
            cargo_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            cargo_window.deiconify()
        
        # Update scroll region
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
    except Exception as e:
        logger.error(f'[show_cargo_details_window] Exception: {e}', exc_info=True)
        logger.warning('!! Error showing cargo details window: ' + traceback.format_exc(), exc_info=False)


def show_ships_details_window(plugin, callsign: str):
    """
    Open a window displaying detailed ships information for a specific fleet carrier.
    
    Args:
        plugin: The plugin instance
        callsign: Fleet carrier callsign to display ships for
    """
    try:
        # Get ships details from StoredShipsManager
        if not hasattr(plugin, 'ships_manager') or not plugin.ships_manager:
            # LANG: Window title for ships details (title and message)
            showinfo(plugin.parent, plugin_tl("Ships Details"), plugin_tl("Ships manager not available."))
            return
        
        ships_items = plugin.ships_manager.get_ships_for_carrier(callsign)
        
        if not ships_items:
            # LANG: Window title for ships details and no data message
            showinfo(plugin.parent, plugin_tl("Ships Details"), f"{plugin_tl('No ships data available for')} {callsign}.")
            return
        
        # Create new window with custom themed title bar
        if not hasattr(plugin, 'window_positions'):
            plugin.window_positions = {}
        saved_positions = plugin.window_positions
        
        # LANG: Window title for ships details window
        window_title = f"{plugin_tl('Ships Details')} - {callsign}"
        ships_window, content_frame = create_themed_window(
            plugin.parent,
            window_title,
            saved_positions=saved_positions
        )
        
        # Define headers - Ship (Index 1), Ship Name (Index 3), Last Updated (Index 7)
        # LANG: Ships window column headers
        headers = [plugin_tl("Ship"), plugin_tl("Ship Name"), plugin_tl("Last Updated")]
        
        # Get fonts for accurate width calculation
        header_font = tkfont.Font(family="Arial", size=9, weight="bold")
        data_font = tkfont.Font(family="Arial", size=9)
        
        # Initialize column widths based on header text
        column_widths_px = [header_font.measure(h) + 20 for h in headers]
        
        # Sort ships alphabetically by ship type (Index 1)
        sorted_ships = sorted(ships_items, key=lambda x: x.get('ship_type', '').lower())
        
        # Calculate maximum content width for each column
        for item in sorted_ships:
            ship_type = item.get('ship_type', 'Unknown')
            ship_name = item.get('ship_name', '')
            last_updated = item.get('last_updated', 'Unknown')
            
            # Convert ship_type to title case for display
            ship_type_display = ship_type.replace('_', ' ').title()
            
            # Format last updated to local time
            last_updated_display = last_updated
            if last_updated and last_updated != 'Unknown':
                try:
                    from datetime import datetime
                    # Parse format: "YYYY-MM-DD HH:MM:SS UTC"
                    dt = datetime.strptime(last_updated, '%Y-%m-%d %H:%M:%S %Z')
                    # Convert to local time
                    local_dt = dt.astimezone()
                    # Format as "MM/DD/YY h:mm a"
                    formatted = local_dt.strftime('%m/%d/%y %I:%M %p')
                    # Remove leading zero from hour
                    parts = formatted.split(' ')
                    hour_min = parts[1]
                    if hour_min.startswith('0'):
                        hour_min = hour_min[1:]
                    last_updated_display = f"{parts[0]} {hour_min} {parts[2]}"
                except Exception:
                    last_updated_display = last_updated
            
            # Update column widths
            column_widths_px[0] = max(column_widths_px[0], data_font.measure(str(ship_type_display)) + 20)
            column_widths_px[1] = max(column_widths_px[1], data_font.measure(str(ship_name if ship_name else "Unnamed")) + 20)
            column_widths_px[2] = max(column_widths_px[2], data_font.measure(str(last_updated_display)) + 20)
        
        # Calculate required width
        num_separators = len(headers) - 1
        separator_width = num_separators * 2
        total_column_width = sum(column_widths_px) + separator_width + 75
        screen_width = ships_window.winfo_screenwidth()
        window_width = min(total_column_width, screen_width - 20)
        window_width = max(window_width, 400)
        
        # Create main container with scrolling
        main_frame = content_frame
        
        # Create scrollbars
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL)
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL)
        
        def safe_h_scrollbar_set(*args):
            h_scrollbar.set(*args)
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    h_scrollbar.pack_forget()
                else:
                    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X, before=canvas)
        
        def safe_v_scrollbar_set(*args):
            v_scrollbar.set(*args)
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    v_scrollbar.pack_forget()
                else:
                    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, before=canvas)
        
        # Create canvas
        canvas = ThemeSafeCanvas(main_frame,
                                 xscrollcommand=safe_h_scrollbar_set,
                                 yscrollcommand=safe_v_scrollbar_set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        theme.update(canvas)
        
        h_scrollbar.config(command=canvas.xview)
        v_scrollbar.config(command=canvas.yview)
        
        style_scrollbars(h_scrollbar, v_scrollbar, main_frame)
        
        scrollable_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        theme.update(scrollable_frame)
        
        # Update canvas scroll region
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            if hasattr(ships_window, '_is_resizing') and ships_window._is_resizing:
                return
            canvas_width = canvas.winfo_width()
            if canvas_width > 1:
                canvas_window_id = canvas.find_all()
                if canvas_window_id:
                    content_width = scrollable_frame.winfo_reqwidth()
                    if content_width < canvas_width:
                        canvas.itemconfig(canvas_window_id[0], width=canvas_width)
                    else:
                        canvas.itemconfig(canvas_window_id[0], width=content_width)
        
        scrollable_frame.bind("<Configure>", on_frame_configure)
        
        def on_canvas_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            if hasattr(ships_window, '_is_resizing') and ships_window._is_resizing:
                return
            canvas_width = canvas.winfo_width()
            if canvas_width > 1:
                canvas_window_id = canvas.find_all()
                if canvas_window_id:
                    content_width = scrollable_frame.winfo_reqwidth()
                    if content_width < canvas_width:
                        canvas.itemconfig(canvas_window_id[0], width=canvas_width)
                    else:
                        canvas.itemconfig(canvas_window_id[0], width=content_width)
        
        canvas.bind('<Configure>', on_canvas_configure)
        
        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        
        ships_window.bind("<MouseWheel>", on_mousewheel)
        ships_window.bind("<Shift-MouseWheel>", on_shift_mousewheel)
        
        # Create table frame
        table_frame = tk.Frame(scrollable_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        theme.update(table_frame)
        table_frame.update_idletasks()
        
        # Configure grid columns
        for i, width_px in enumerate(column_widths_px):
            table_frame.grid_columnconfigure(i*2, minsize=width_px, weight=0)
            if i < len(column_widths_px) - 1:
                table_frame.grid_columnconfigure(i*2+1, minsize=2, weight=0)
        
        # Get base background color for alternating rows
        try:
            from config import config
            current_theme = config.get_int('theme')
            base_bg = table_frame.cget('bg')
            
            try:
                is_dark = current_theme in [1, 2]
            except:
                is_dark = (isinstance(base_bg, str) and 
                          base_bg.lower() in ['black', '#000000', '#1e1e1e', 'systemwindow'])
            
            if base_bg and base_bg.strip():
                if is_dark:
                    base_row_bg = base_bg
                else:
                    if base_bg.lower() not in ['white', '#ffffff', 'systemwindow', 'systembuttonface']:
                        base_row_bg = base_bg
                    else:
                        base_row_bg = '#ffffff'
            else:
                base_row_bg = '#1e1e1e' if is_dark else '#ffffff'
            
            # Create alternating color
            if base_row_bg and base_row_bg != "":
                if is_dark:
                    try:
                        if base_row_bg.startswith('#'):
                            rgb = tuple(int(base_row_bg[i:i+2], 16) for i in (1, 3, 5))
                            alt_rgb = tuple(min(255, c + 15) for c in rgb)
                            alt_row_bg = f"#{alt_rgb[0]:02x}{alt_rgb[1]:02x}{alt_rgb[2]:02x}"
                        else:
                            alt_row_bg = '#2a2a2a'
                    except:
                        alt_row_bg = '#2a2a2a'
                else:
                    try:
                        if base_row_bg.startswith('#'):
                            rgb = tuple(int(base_row_bg[i:i+2], 16) for i in (1, 3, 5))
                            alt_rgb = tuple(max(0, c - 15) for c in rgb)
                            alt_row_bg = f"#{alt_rgb[0]:02x}{alt_rgb[1]:02x}{alt_rgb[2]:02x}"
                        else:
                            alt_row_bg = '#f5f5f5'
                    except:
                        alt_row_bg = '#f5f5f5'
            else:
                base_row_bg = ""
                alt_row_bg = ""
        except Exception:
            base_row_bg = ""
            alt_row_bg = ""
        
        # Create header row
        for col_idx, header in enumerate(headers):
            header_label = tk.Label(
                table_frame,
                text=header,
                font=header_font,
                anchor="w",
                relief=tk.RAISED,
                borderwidth=1
            )
            header_label.grid(row=0, column=col_idx*2, padx=2, pady=5, sticky=tk.EW)
            theme.update(header_label)
            
            # Add separator after each column except the last
            if col_idx < len(headers) - 1:
                separator = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator.grid(row=0, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator)
        
        # Create data rows
        for idx, item in enumerate(sorted_ships):
            data_row = idx + 1
            row_bg = base_row_bg if idx % 2 == 0 else alt_row_bg
            
            ship_type = item.get('ship_type', 'Unknown')
            ship_name = item.get('ship_name', '')
            last_updated = item.get('last_updated', 'Unknown')
            
            # Convert ship_type to title case for display
            ship_type_display = ship_type.replace('_', ' ').title()
            
            # Format last updated
            last_updated_display = last_updated
            if last_updated and last_updated != 'Unknown':
                try:
                    from datetime import datetime
                    dt = datetime.strptime(last_updated, '%Y-%m-%d %H:%M:%S %Z')
                    local_dt = dt.astimezone()
                    formatted = local_dt.strftime('%m/%d/%y %I:%M %p')
                    parts = formatted.split(' ')
                    hour_min = parts[1]
                    if hour_min.startswith('0'):
                        hour_min = hour_min[1:]
                    last_updated_display = f"{parts[0]} {hour_min} {parts[2]}"
                except Exception:
                    last_updated_display = last_updated
            
            col_idx = 0
            
            # Ship (Ship Type)
            label_kwargs = {"master": table_frame, "text": ship_type_display, "anchor": "w"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            ship_label = tk.Label(**label_kwargs)
            ship_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(ship_label)
            if col_idx < len(headers) - 1:
                separator = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator)
            col_idx += 1
            
            # Ship Name
            ship_name_display = ship_name if ship_name else "Unnamed"
            label_kwargs = {"master": table_frame, "text": ship_name_display, "anchor": "w"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            name_label = tk.Label(**label_kwargs)
            name_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(name_label)
            if col_idx < len(headers) - 1:
                separator = ttk.Separator(table_frame, orient=tk.VERTICAL)
                separator.grid(row=data_row, column=col_idx*2+1, padx=0, pady=2, sticky=tk.NS)
                theme.update(separator)
            col_idx += 1
            
            # Last Updated
            label_kwargs = {"master": table_frame, "text": last_updated_display, "anchor": "w"}
            if row_bg:
                label_kwargs["bg"] = row_bg
            updated_label = tk.Label(**label_kwargs)
            updated_label.grid(row=data_row, column=col_idx*2, padx=2, pady=5, sticky=tk.W)
            theme.update(updated_label)
        
        # Handle window resize
        ships_window._is_resizing = False
        original_config = ships_window.winfo_toplevel().config
        
        def on_window_configure(event):
            if event.widget == ships_window.winfo_toplevel():
                ships_window._is_resizing = True
                if hasattr(ships_window, '_resize_after_id'):
                    ships_window.after_cancel(ships_window._resize_after_id)
                ships_window._resize_after_id = ships_window.after(100, lambda: setattr(ships_window, '_is_resizing', False))
        
        ships_window.winfo_toplevel().bind('<Configure>', on_window_configure)
        
        # Set initial window size and position
        ships_window.update_idletasks()
        window_height = min(600, ships_window.winfo_screenheight() - 100)
        ships_window.geometry(f"{window_width}x{window_height}")
        
        # Restore saved position if available, otherwise center and show window
        if saved_positions and window_title in saved_positions:
            restore_window_position(ships_window, window_title, saved_positions, window_width, window_height)
        else:
            # First time showing window - center on screen
            screen_width = ships_window.winfo_screenwidth()
            screen_height = ships_window.winfo_screenheight()
            x = (screen_width // 2) - (window_width // 2)
            y = (screen_height // 2) - (window_height // 2)
            ships_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            ships_window.deiconify()
        
        # Update scroll region
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
    except Exception as e:
        logger.error(f'[show_ships_details_window] Exception: {e}', exc_info=True)
        logger.warning('!! Error showing ships details window: ' + traceback.format_exc(), exc_info=False)
        showerror(plugin.parent, "Error", f"Failed to display cargo details for {callsign}.")


# Module categorization mapping
MODULE_CATEGORIES = {
    # Core Internal Modules
    'powerplant': ('Core Internal Modules', 'Power Plant'),
    'engine': ('Core Internal Modules', 'Thrusters'),
    'hyperdrive': ('Core Internal Modules', 'Frame Shift Drive'),
    'lifesupport': ('Core Internal Modules', 'Life Support'),
    'powerdistributor': ('Core Internal Modules', 'Power Distributor'),
    'sensors': ('Core Internal Modules', 'Sensors'),
    'fueltank': ('Core Internal Modules', 'Fuel Tank'),
    
    # Optional Internal - Utility
    'cargorack': ('Optional Internal Modules', 'Cargo Rack'),
    'fuelscoop': ('Optional Internal Modules', 'Fuel Scoop'),
    'repairer': ('Optional Internal Modules', 'AFM Unit'),
    'refinery': ('Optional Internal Modules', 'Refinery'),
    'shieldgenerator': ('Optional Internal Modules', 'Shield Generator'),
    'hullreinforcement': ('Optional Internal Modules', 'Hull Reinforcement'),
    'modulereinforcement': ('Optional Internal Modules', 'Module Reinforcement'),
    'shieldcellbank': ('Optional Internal Modules', 'Shield Cell Bank'),
    'detailedsurfacescanner': ('Optional Internal Modules', 'Detailed Surface Scanner'),
    'fsdinterdictor': ('Optional Internal Modules', 'FSD Interdictor'),
    'supercruiseassist': ('Optional Internal Modules', 'Supercruise Assist'),
    'dockingcomputer': ('Optional Internal Modules', 'Docking Computer'),
    
    # Optional Internal - Passenger/Vehicles
    'passengercabin': ('Optional Internal Modules', 'Passenger Cabin'),
    'buggybay': ('Optional Internal Modules', 'Planetary Vehicle Hangar'),
    'fighterbay': ('Optional Internal Modules', 'Fighter Hangar'),
    
    # Optional Internal - Limpets
    'dronecontrol': ('Optional Internal Modules', 'Limpet Controller'),
    'multidronecontrol': ('Optional Internal Modules', 'Multi-Limpet Controller'),
    
    # Optional Internal - Guardian
    'guardianshieldreinforcement': ('Optional Internal Modules', 'Guardian Shield Reinforcement'),
    'guardianhullreinforcement': ('Optional Internal Modules', 'Guardian Hull Reinforcement'),
    'guardianmodulereinforcement': ('Optional Internal Modules', 'Guardian Module Reinforcement'),
    'guardianfsdbooster': ('Optional Internal Modules', 'Guardian FSD Booster'),
    'guardianpowerplant': ('Optional Internal Modules', 'Guardian Power Plant'),
    'guardianpowerdistributor': ('Optional Internal Modules', 'Guardian Power Distributor'),
    
    # Hardpoint Weapons - Energy
    'pulselaser': ('Hardpoint Weapons', 'Pulse Laser'),
    'burstlaser': ('Hardpoint Weapons', 'Burst Laser'),
    'beamlaser': ('Hardpoint Weapons', 'Beam Laser'),
    'railgun': ('Hardpoint Weapons', 'Rail Gun'),
    'plasmaaccelerator': ('Hardpoint Weapons', 'Plasma Accelerator'),
    
    # Hardpoint Weapons - Kinetic
    'multicannon': ('Hardpoint Weapons', 'Multi-Cannon'),
    'cannon': ('Hardpoint Weapons', 'Cannon'),
    'slugshot': ('Hardpoint Weapons', 'Fragment Cannon'),
    
    # Hardpoint Weapons - Explosive
    'basicmissilerack': ('Hardpoint Weapons', 'Missile Rack'),
    'advancedmissilerack': ('Hardpoint Weapons', 'Advanced Missile Rack'),
    'drunkmissilerack': ('Hardpoint Weapons', 'Pack-Hound Missile Rack'),
    'dumbfiremissilerack': ('Hardpoint Weapons', 'Dumbfire Missile Rack'),
    'minelauncher': ('Hardpoint Weapons', 'Mine Launcher'),
    'mininglaser': ('Hardpoint Weapons', 'Mining Laser'),
    
    # Hardpoint Weapons - Mining
    'mining_abrblstr': ('Hardpoint Weapons', 'Abrasion Blaster'),
    'mining_subsurfdispmisle': ('Hardpoint Weapons', 'Sub-Surface Displacement Missile'),
    'mining_seismchrgwarhd': ('Hardpoint Weapons', 'Seismic Charge Launcher'),
    
    # Hardpoint Weapons - Anti-Xeno
    'flakmortar': ('Hardpoint Weapons', 'Remote Flak Launcher'),
    'flechettelauncher': ('Hardpoint Weapons', 'Remote Flechette Launcher'),
    'guardian': ('Hardpoint Weapons', 'Guardian Weapon'),
    
    # Utility Mounts
    'shieldbooster': ('Utility Mounts', 'Shield Booster'),
    'chafflauncher': ('Utility Mounts', 'Chaff Launcher'),
    'heatsinklauncher': ('Utility Mounts', 'Heat Sink Launcher'),
    'plasmapointdefence': ('Utility Mounts', 'Point Defence'),
    'electroniccountermeasure': ('Utility Mounts', 'ECM'),
    'crimescanner': ('Utility Mounts', 'Kill Warrant Scanner'),
    'manifestscanner': ('Utility Mounts', 'Manifest Scanner'),
    'cargoscanner': ('Utility Mounts', 'Cargo Scanner'),
    'cloudscanner': ('Utility Mounts', 'Frame Shift Wake Scanner'),
    'xenoscanner': ('Utility Mounts', 'Xeno Scanner'),
    'mrascanner': ('Utility Mounts', 'Pulse Wave Analyser'),
    'shutdownfieldneutraliser': ('Utility Mounts', 'Shutdown Field Neutraliser'),
}


def _categorize_module(module_name: str) -> Tuple[str, str]:
    """
    Categorize a module based on its internal name.
    
    Args:
        module_name: Internal module name (e.g., "$int_powerplant_size4_class5_name;")
        
    Returns:
        Tuple of (main_category, subcategory)
    """
    # Normalize module name - remove $ prefix and _name suffix
    normalized = module_name.lower().replace('$', '').replace('_name;', '').replace('_name', '')
    
    # Check each category pattern
    for pattern, (main_cat, sub_cat) in MODULE_CATEGORIES.items():
        if pattern in normalized:
            return (main_cat, sub_cat)
    
    # Default category for unknown modules
    return ('Other Modules', 'Miscellaneous')


def _extract_module_info(module: Dict) -> Dict:
    """
    Extract and format module information for display.
    
    Args:
        module: Module dictionary from StoredModulesManager
        
    Returns:
        Dictionary with formatted module information
    """
    module_name = module.get('module_name_localized', module.get('module_name', 'Unknown'))
    
    # Extract size and class from module name if present
    size = None
    class_num = None
    
    # Try to parse from internal name
    internal_name = module.get('module_name', '').lower()
    if '_size' in internal_name:
        try:
            size_part = internal_name.split('_size')[1].split('_')[0]
            size = int(size_part)
        except:
            pass
    
    if '_class' in internal_name:
        try:
            class_part = internal_name.split('_class')[1].split('_')[0]
            class_num = int(class_part)
        except:
            pass
    
    # Get price
    try:
        price = int(module.get('buy_price', 0))
    except:
        price = 0
    
    # Get engineering info
    is_engineered = module.get('engineered', '').lower() == 'true'
    engineer_mod = module.get('engineer', '')
    level = module.get('level', '')
    
    # Format engineering display
    engineering_text = ""
    if is_engineered and engineer_mod:
        # Clean up engineering name (remove prefix)
        clean_mod = engineer_mod.replace('Weapon_', '').replace('Engine_', '').replace('PowerPlant_', '').replace('ShieldGenerator_', '').replace('FSDinterdictor_', '').replace('Sensor_', '').replace('CargoRack_', '').replace('Misc_', '').replace('Decorative_', '')
        engineering_text = f"{clean_mod} G{level}"
    
    return {
        'name': module_name,
        'size': size,
        'class': class_num,
        'price': price,
        'is_engineered': is_engineered,
        'engineering': engineering_text,
        'full_module': module
    }


def _group_modules(modules: List[Dict]) -> Dict[Tuple[str, str, int, int, str], List[Dict]]:
    """
    Group modules by exact match (name, size, class, engineering type/level/quality).
    
    Args:
        modules: List of module dictionaries
        
    Returns:
        Dictionary mapping (name, size, class, engineering) -> list of modules
    """
    grouped = defaultdict(list)
    
    for module in modules:
        info = _extract_module_info(module)
        
        # Create key for exact matching
        key = (
            info['name'],
            info['size'] if info['size'] is not None else -1,
            info['class'] if info['class'] is not None else -1,
            info['engineering']  # Includes type, level, quality
        )
        
        grouped[key].append(info)
    
    return grouped


def show_modules_details_window(plugin, callsign: str):
    """
    Open a window displaying stored modules for a specific fleet carrier.
    Modules are displayed in an expandable tree view organized by category.
    
    Args:
        plugin: The plugin instance
        callsign: Fleet carrier callsign to display modules for
    """
    try:
        # Get modules details from StoredModulesManager
        if not hasattr(plugin, 'modules_manager') or not plugin.modules_manager:
            # LANG: Window title for modules details (title and message)
            showinfo(plugin.parent, plugin_tl("Stored Modules"), plugin_tl("Modules manager not available."))
            return
        
        modules_items = plugin.modules_manager.get_modules_for_carrier(callsign)
        
        if not modules_items:
            # LANG: Window title for modules details and no data message
            showinfo(plugin.parent, plugin_tl("Stored Modules"), f"{plugin_tl('No modules data available for')} {callsign}.")
            return
        
        # Create new window with custom themed title bar
        if not hasattr(plugin, 'window_positions'):
            plugin.window_positions = {}
        saved_positions = plugin.window_positions
        
        # LANG: Window title for modules details window
        window_title = f"{plugin_tl('Stored Modules')} - {callsign}"
        modules_window, content_frame = create_themed_window(
            plugin.parent,
            window_title,
            saved_positions=saved_positions
        )
        
        # Calculate summary statistics
        total_modules = len(modules_items)
        total_value = plugin.modules_manager.get_total_modules_value(callsign)
        engineered_count = plugin.modules_manager.get_engineered_module_count(callsign)
        
        # Create summary frame at top
        summary_frame = tk.Frame(content_frame)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)
        theme.update(summary_frame)
        
        # First line: Total Modules and Engineered count
        summary_line1 = tk.Label(
            summary_frame,
            text=f"Total Modules: {total_modules}  |  Engineered: {engineered_count}",
            font=('Arial', 10, 'bold')
        )
        summary_line1.pack()
        theme.update(summary_line1)
        
        # Second line: Total Value
        summary_line2 = tk.Label(
            summary_frame,
            text=f"Total Value: {total_value:,} CR",
            font=('Arial', 10, 'bold')
        )
        summary_line2.pack()
        theme.update(summary_line2)
        
        # Create scrollable frame for tree view
        # Create scrollbars with auto-hide functionality
        h_scrollbar = ttk.Scrollbar(content_frame, orient=tk.HORIZONTAL)
        v_scrollbar = ttk.Scrollbar(content_frame, orient=tk.VERTICAL)
        
        def safe_h_scrollbar_set(*args):
            h_scrollbar.set(*args)
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    h_scrollbar.pack_forget()
                else:
                    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X, before=canvas)
        
        def safe_v_scrollbar_set(*args):
            v_scrollbar.set(*args)
            if len(args) == 2:
                first, last = float(args[0]), float(args[1])
                if first <= 0.02 and last >= 0.98:
                    v_scrollbar.pack_forget()
                else:
                    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, before=canvas)
        
        # Create canvas with theme-safe implementation
        canvas = ThemeSafeCanvas(content_frame, 
                                 xscrollcommand=safe_h_scrollbar_set,
                                 yscrollcommand=safe_v_scrollbar_set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        theme.update(canvas)
        
        h_scrollbar.config(command=canvas.xview)
        v_scrollbar.config(command=canvas.yview)
        
        # Style scrollbars
        style_scrollbars(h_scrollbar, v_scrollbar, content_frame)
        
        scrollable_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        
        modules_window.bind("<MouseWheel>", on_mousewheel)
        modules_window.bind("<Shift-MouseWheel>", on_shift_mousewheel)
        
        # Categorize and group modules
        categorized = defaultdict(lambda: defaultdict(list))
        
        for module in modules_items:
            main_cat, sub_cat = _categorize_module(module.get('module_name', ''))
            categorized[main_cat][sub_cat].append(module)
        
        # Create expandable tree structure
        # Track expanded state for each category
        expanded_state = {}
        
        def create_category_row(parent_frame, category_name, subcategories, level=0):
            """Create an expandable category row"""
            # Calculate totals for this category
            total_count = sum(len(mods) for mods in subcategories.values())
            engineered_in_cat = sum(
                1 for mods in subcategories.values()
                for mod in mods
                if mod.get('engineered', '').lower() == 'true'
            )
            
            # Create container for this category
            cat_container = tk.Frame(parent_frame)
            cat_container.pack(fill=tk.X, pady=2)
            theme.update(cat_container)
            
            # Create header frame
            header_frame = tk.Frame(cat_container)
            header_frame.pack(fill=tk.X)
            theme.update(header_frame)
            
            # Indent based on level
            indent_label = tk.Label(header_frame, text="  " * level, width=level*2)
            indent_label.pack(side=tk.LEFT)
            theme.update(indent_label)
            
            # Expansion indicator
            indicator_var = tk.StringVar(value="▶")
            indicator_label = tk.Label(header_frame, textvariable=indicator_var, width=2, cursor="hand2")
            indicator_label.pack(side=tk.LEFT)
            theme.update(indicator_label)
            
            # Category label with count
            cat_label = tk.Label(
                header_frame,
                text=f"{category_name} ({total_count}, {engineered_in_cat} Engineered)",
                font=('Arial', 9, 'bold' if level == 0 else 'normal'),
                cursor="hand2"
            )
            cat_label.pack(side=tk.LEFT, padx=5)
            theme.update(cat_label)
            
            # Content frame (initially hidden)
            content_frame_inner = tk.Frame(cat_container)
            theme.update(content_frame_inner)
            
            # Track expanded state
            expanded_state[category_name] = False
            
            def toggle_expand(event=None):
                """Toggle expansion of this category"""
                if expanded_state[category_name]:
                    # Collapse
                    content_frame_inner.pack_forget()
                    indicator_var.set("▶")
                    expanded_state[category_name] = False
                else:
                    # Expand
                    content_frame_inner.pack(fill=tk.X, padx=(20, 0))
                    indicator_var.set("▼")
                    expanded_state[category_name] = True
            
            # Bind click events
            indicator_label.bind("<Button-1>", toggle_expand)
            cat_label.bind("<Button-1>", toggle_expand)
            
            return content_frame_inner
        
        def create_module_list(parent_frame, modules, level=0):
            """Create list of modules (grouped by exact match)"""
            # Group modules
            grouped = _group_modules(modules)
            
            # Sort by price (highest first)
            sorted_groups = sorted(grouped.items(), key=lambda x: x[1][0]['price'], reverse=True)
            
            for (name, size, class_num, engineering), module_list in sorted_groups:
                count = len(module_list)
                price = module_list[0]['price']
                
                # Format display text
                size_class_text = ""
                if size != -1 and class_num != -1:
                    size_class_text = f" (Size {size}, Class {class_num})"
                elif size != -1:
                    size_class_text = f" (Size {size})"
                
                engineering_text = f" ({engineering})" if engineering else ""
                count_text = f" (×{count})" if count > 1 else ""
                price_text = f" - {price:,} CR"
                
                full_text = f"{name}{size_class_text}{engineering_text}{count_text}{price_text}"
                
                # Create module row
                module_frame = tk.Frame(parent_frame)
                module_frame.pack(fill=tk.X, pady=1)
                theme.update(module_frame)
                
                # Indent
                indent_label = tk.Label(module_frame, text="  " * (level + 1), width=(level + 1)*2)
                indent_label.pack(side=tk.LEFT)
                theme.update(indent_label)
                
                # Module label
                module_label = tk.Label(
                    module_frame,
                    text=full_text,
                    font=('Arial', 9),
                    anchor="w"
                )
                module_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
                theme.update(module_label)
        
        # Build tree structure
        # Sort main categories
        sorted_main_cats = sorted(categorized.keys())
        
        for main_cat in sorted_main_cats:
            subcategories = categorized[main_cat]
            
            # Create main category row
            main_content = create_category_row(scrollable_frame, main_cat, subcategories, level=0)
            
            # Sort subcategories
            sorted_sub_cats = sorted(subcategories.keys())
            
            for sub_cat in sorted_sub_cats:
                modules = subcategories[sub_cat]
                
                # Create subcategory row
                sub_content = create_category_row(main_content, sub_cat, {sub_cat: modules}, level=1)
                
                # Add module list
                create_module_list(sub_content, modules, level=1)
        
        # Update scroll region
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
        # Restore window position or center on screen (same as cargo/ships windows)
        restore_window_position(modules_window, window_title, saved_positions, 800, 600)
        
    except Exception as e:
        logger.error(f'[show_modules_details_window] Exception: {e}', exc_info=True)
        logger.warning('!! Error showing modules details window: ' + traceback.format_exc(), exc_info=False)
