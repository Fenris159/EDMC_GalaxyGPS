import tkinter as tk
from theme import theme  # type: ignore


class ThemeSafeCanvas(tk.Canvas):
    """
    A Canvas widget that gracefully handles unsupported options from EDMC's theme system.
    Canvas widgets don't support text-related options like -foreground and -font,
    so we silently ignore them to prevent TclError when EDMC's theme system tries to apply them.
    """
    # Options that Canvas widgets don't support but EDMC's theme system may try to apply
    _unsupported_options = {
        'foreground', '-foreground', 'fg', '-fg',
        'font', '-font'
    }

    def configure(self, cnf=None, **kw):
        """Override configure to silently ignore unsupported options."""
        if cnf is not None:
            # Handle dict-style configuration
            if isinstance(cnf, dict):
                cnf = {k: v for k, v in cnf.items() if k not in self._unsupported_options}
            elif isinstance(cnf, str):
                # Handle single option query like 'foreground' or '-foreground'
                if cnf in self._unsupported_options:
                    # Return empty string for unsupported option (matching tkinter behavior)
                    return ''
        # Remove unsupported options from keyword arguments
        kw = {k: v for k, v in kw.items() if k not in self._unsupported_options}
        # Call parent configure with filtered options (only if there are options to configure)
        if cnf is None and not kw:
            return super().configure()
        return super().configure(cnf, **kw)

    def __setitem__(self, key, value):
        """Override __setitem__ to silently ignore unsupported options."""
        if key in self._unsupported_options:
            # Silently ignore unsupported options
            return
        return super().__setitem__(key, value)

    config = configure  # Alias for configure method


class ThemedCombobox:
    """
    Custom combobox widget that can be fully styled to match EDMC themes.
    Uses tk.Entry, tk.Button, and tk.Listbox instead of ttk.Combobox
    to allow complete theme control on Windows.
    
    This widget provides the same API as ttk.Combobox but with full styling support.
    """
    def __init__(self, parent, textvariable=None, values=None, width=None, state="readonly", **kwargs):
        self.parent = parent
        self.textvariable = textvariable if textvariable else tk.StringVar()
        self.values = values if values else []
        self.width = width
        self.state = state
        self.kwargs = kwargs
        
        # Create container frame
        self.frame = tk.Frame(parent)
        
        # Create Entry widget for display
        # Only set width if specified, otherwise let it auto-size
        entry_kwargs = {
            'textvariable': self.textvariable,
            'state': 'readonly' if state == 'readonly' else 'normal',
            **kwargs
        }
        if width is not None:
            entry_kwargs['width'] = width
        
        self.entry = tk.Entry(self.frame, **entry_kwargs)
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create dropdown button with arrow
        self.dropdown_btn = tk.Button(
            self.frame,
            text="▼",
            width=2,
            command=self.toggle_dropdown,
            relief=tk.FLAT,
            borderwidth=1
        )
        self.dropdown_btn.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Dropdown popup window (created when needed)
        self.popup = None
        self.listbox = None
        self.is_open = False
        self._root_click_binding = None
        self._selecting = False  # Flag to prevent click-outside interference
        
        # Bind events: only open on explicit click (entry or dropdown button).
        # Do NOT open on FocusIn — that causes the dropdown to reopen when focus
        # returns after closing a dialog or clicking another button (e.g. View Route).
        self.entry.bind('<Button-1>', self.on_entry_click)
        
    def toggle_dropdown(self):
        """Toggle the dropdown list visibility"""
        if self.is_open:
            self.close_dropdown()
        else:
            self.open_dropdown()
    
    def on_entry_click(self, event):
        """Handle click on entry - open dropdown if readonly"""
        if self.state == 'readonly':
            self.open_dropdown()
    
    def open_dropdown(self):
        """Open the dropdown list"""
        if self.is_open or not self.values:
            return
        
        self.is_open = True
        
        # Get position of entry widget
        self.entry.update_idletasks()
        x = self.frame.winfo_rootx()
        y = self.frame.winfo_rooty() + self.frame.winfo_height()
        
        # Create popup window (initially positioned, will be repositioned after size calculation)
        self.popup = tk.Toplevel(self.parent)
        self.popup.wm_overrideredirect(True)
        self.popup.wm_geometry(f"+{x}+{y}")
        
        # Get theme colors
        try:
            from config import config  # type: ignore
            current_theme = config.get_int('theme')
            frame_bg = self.frame.cget('bg')
            
            # Determine if this is a dark theme
            is_dark_theme = current_theme in [1, 2]  # 1=Dark, 2=Transparent
            
            # Determine background color
            def get_actual_color(color_name):
                try:
                    temp_widget = tk.Label(self.frame, bg=color_name)
                    temp_widget.update_idletasks()
                    actual_color = temp_widget.cget('bg')
                    temp_widget.destroy()
                    return actual_color
                except:
                    return color_name
            
            if frame_bg and frame_bg.strip():
                if current_theme == 2 and frame_bg.lower() == 'systemwindow':
                    bg_color = get_actual_color('systemwindow')
                elif frame_bg.startswith('#'):
                    bg_color = frame_bg
                elif frame_bg.lower() not in ['white', '#ffffff', 'systembuttonface']:
                    bg_color = get_actual_color(frame_bg)
                else:
                    bg_color = '#1e1e1e' if is_dark_theme else '#ffffff'
            else:
                bg_color = '#1e1e1e' if is_dark_theme else '#ffffff'
            
            # Determine foreground color based on theme
            if is_dark_theme:
                fg_color = 'orange'
            else:
                # Default theme uses system default text color
                fg_color = 'SystemWindowText'
        except:
            bg_color = '#1e1e1e'
            fg_color = 'orange'
            is_dark_theme = True
        
        # Create listbox with hover highlighting enabled
        # Calculate a highlight color (slightly lighter/darker than bg)
        def calculate_highlight_color(bg_color):
            """Calculate a highlight color based on background"""
            try:
                # Parse hex color
                if bg_color.startswith('#'):
                    r = int(bg_color[1:3], 16)
                    g = int(bg_color[3:5], 16)
                    b = int(bg_color[5:7], 16)
                    # If dark theme, lighten; if light theme, darken
                    if r + g + b < 384:  # Dark theme (sum < 128*3)
                        # Lighten by adding 30
                        r = min(255, r + 30)
                        g = min(255, g + 30)
                        b = min(255, b + 30)
                    else:  # Light theme
                        # Darken by subtracting 30
                        r = max(0, r - 30)
                        g = max(0, g - 30)
                        b = max(0, b - 30)
                    return f'#{r:02x}{g:02x}{b:02x}'
                else:
                    # Fallback to a generic highlight color
                    return '#3d3d3d' if bg_color == '#1e1e1e' else '#e0e0e0'
            except:
                return '#3d3d3d' if bg_color == '#1e1e1e' else '#e0e0e0'
        
        highlight_color = calculate_highlight_color(bg_color)
        
        self.listbox = tk.Listbox(
            self.popup,
            bg=bg_color,
            fg=fg_color,
            selectbackground=highlight_color,
            selectforeground=fg_color,
            activestyle='underline',  # Show visual feedback on hover
            borderwidth=1,
            relief=tk.SOLID,
            highlightthickness=0
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        
        # Track hover state for additional visual feedback
        self.hover_index = None
        
        def on_motion(event):
            """Handle mouse motion over listbox to highlight item"""
            index = self.listbox.nearest(event.y)
            if index != self.hover_index:
                self.hover_index = index
                # Clear previous selection and select hovered item
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(index)
                self.listbox.activate(index)
        
        def on_leave(event):
            """Handle mouse leaving listbox"""
            self.hover_index = None
        
        self.listbox.bind('<Motion>', on_motion)
        self.listbox.bind('<Leave>', on_leave)
        
        # Add values to listbox
        for value in self.values:
            self.listbox.insert(tk.END, value)
        
        # Apply theme (EDMC theme.update rejects tk.Toplevel; only theme the listbox)
        theme.update(self.listbox)
        
        # Bind selection event
        self.listbox.bind('<Button-1>', self.on_select)
        self.listbox.bind('<Double-Button-1>', self.on_select)
        self.listbox.bind('<Return>', self.on_select)
        self.listbox.bind('<Escape>', lambda e: self.close_dropdown())
        
        # Flag to prevent click-outside from interfering with selection
        self._selecting = False
        
        # Simple approach: bind directly to the popup's FocusOut event
        # This will trigger when user clicks anywhere outside the popup
        def on_focus_out(event=None):
            # Small delay to allow selection to complete if clicking inside
            def check_close():
                if self.is_open and not self._selecting:
                    self.close_dropdown()
            self.parent.after(150, check_close)
        
        self.popup.bind('<FocusOut>', on_focus_out)
        
        # Alternative: bind a click handler to detect clicks outside
        # This catches clicks that FocusOut might miss
        def on_click_anywhere(event):
            if not self.is_open or self._selecting:
                return
            
            try:
                # Get the widget that was clicked
                widget = event.widget
                
                # Check if the clicked widget is part of our popup or combobox
                widget_str = str(widget)
                popup_str = str(self.popup) if self.popup else ""
                listbox_str = str(self.listbox) if self.listbox else ""
                frame_str = str(self.frame)
                entry_str = str(self.entry)
                btn_str = str(self.dropdown_btn)
                
                # If click is on our widgets, don't close
                if (widget_str.startswith(popup_str) or 
                    widget_str.startswith(listbox_str) or
                    widget_str == frame_str or
                    widget_str == entry_str or
                    widget_str == btn_str or
                    widget == self.popup or
                    widget == self.listbox or
                    widget == self.frame or
                    widget == self.entry or
                    widget == self.dropdown_btn):
                    return
                
                # Click was outside, close dropdown
                self.close_dropdown()
            except:
                pass
        
        # Bind to root window with a unique tag
        root = self.parent.winfo_toplevel()
        self._root_click_binding = root.bind('<Button-1>', on_click_anywhere, add='+')
        
        # Set focus to listbox
        self.listbox.focus_set()
        
        # Calculate popup size
        self.listbox.update_idletasks()
        listbox_height = min(self.listbox.winfo_reqheight(), 200)  # Max 200px height
        
        # Calculate width based on actual text measurement of longest item
        if self.values:
            try:
                # Get the font used by the listbox
                import tkinter.font as tkfont
                font_spec = self.listbox.cget('font')
                
                # Convert font specification to Font object
                if isinstance(font_spec, str):
                    if font_spec:
                        # Named font like 'TkDefaultFont'
                        font = tkfont.nametofont(font_spec)
                    else:
                        # Empty string, use default
                        font = tkfont.nametofont('TkDefaultFont')
                else:
                    # Font tuple or Font object
                    font = tkfont.Font(font=font_spec)
                
                # Measure width of longest text
                max_width = 0
                for value in self.values:
                    text_width = font.measure(str(value))
                    if text_width > max_width:
                        max_width = text_width
                
                # Add padding for scrollbar and borders
                listbox_width = max_width + 40
            except Exception:
                # Fallback to estimation if font measurement fails
                max_text_length = max(len(str(value)) for value in self.values)
                listbox_width = max_text_length * 10
        else:
            listbox_width = 200
        
        # Ensure minimum width
        listbox_width = max(listbox_width, self.entry.winfo_width(), 200)
        
        self.popup.wm_geometry(f"{listbox_width}x{listbox_height}")
        
        # Smart positioning: adjust if dropdown would extend beyond screen edge
        # Get screen dimensions
        screen_width = self.parent.winfo_screenwidth()
        screen_height = self.parent.winfo_screenheight()
        
        # Update popup to get actual size
        self.popup.update_idletasks()
        popup_width = self.popup.winfo_width()
        popup_height = self.popup.winfo_height()
        
        # Check horizontal overflow and adjust x position if needed
        if x + popup_width > screen_width:
            # Dropdown would extend beyond right edge
            # Align right edge of dropdown with right edge of entry widget
            x = self.frame.winfo_rootx() + self.frame.winfo_width() - popup_width
            # Ensure it doesn't go off the left edge
            x = max(0, x)
        
        # Check vertical overflow and adjust y position if needed
        if y + popup_height > screen_height:
            # Dropdown would extend beyond bottom edge
            # Position above the entry widget instead
            y = self.frame.winfo_rooty() - popup_height
            # Ensure it doesn't go off the top edge
            y = max(0, y)
        
        # Reposition popup with adjusted coordinates
        self.popup.wm_geometry(f"+{x}+{y}")
        
        # Highlight current selection if any
        current_value = self.textvariable.get()
        if current_value in self.values:
            idx = self.values.index(current_value)
            self.listbox.selection_set(idx)
            self.listbox.see(idx)
    
    def on_select(self, event=None):
        """Handle selection from listbox"""
        self._selecting = True  # Flag to prevent click-outside interference
        
        if self.listbox:
            # If called from a click event, get the clicked index directly
            if event and hasattr(event, 'y'):
                # Get the index of the item at the click position
                idx = self.listbox.nearest(event.y)
                if 0 <= idx < len(self.values):
                    value = self.values[idx]
                    self.textvariable.set(value)
                    # Trigger virtual event similar to ttk.Combobox
                    self.entry.event_generate('<<ComboboxSelected>>')
                    self.close_dropdown()
                    self._selecting = False
                    return
            
            # Fallback to curselection for keyboard events
            selection = self.listbox.curselection()
            if selection:
                idx = selection[0]
                value = self.values[idx]
                self.textvariable.set(value)
                # Trigger virtual event similar to ttk.Combobox
                self.entry.event_generate('<<ComboboxSelected>>')
        
        self._selecting = False
        self.close_dropdown()
    
    def close_dropdown(self):
        """Close the dropdown list"""
        if self.popup:
            # Unbind root click handler if it exists
            try:
                root = self.parent.winfo_toplevel()
                if hasattr(self, '_root_click_binding') and self._root_click_binding:
                    root.unbind('<Button-1>', self._root_click_binding)
            except:
                pass
            self.popup.destroy()
            self.popup = None
            self.listbox = None
        self.is_open = False
    
    def config(self, **kwargs):
        """Configure the combobox"""
        if 'values' in kwargs:
            self.values = kwargs.pop('values')
        if 'state' in kwargs:
            self.state = kwargs.pop('state')
            self.entry.config(state='readonly' if self.state == 'readonly' else 'normal')
        self.entry.config(**kwargs)
    
    def cget(self, option):
        """Get configuration option"""
        if option == 'values':
            return self.values
        elif option == 'state':
            return self.state
        else:
            return self.entry.cget(option)
    
    def __getitem__(self, key):
        """Get configuration option using [] syntax"""
        return self.cget(key)
    
    def __setitem__(self, key, value):
        """Set configuration option using [] syntax"""
        self.config(**{key: value})
    
    def pack(self, **kwargs):
        """Pack the combobox frame"""
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """Grid the combobox frame"""
        self.frame.grid(**kwargs)
    
    def bind(self, event, handler):
        """Bind event to entry widget"""
        self.entry.bind(event, handler)
    
    def current(self, index=None):
        """Get or set current selection index"""
        if index is not None:
            if 0 <= index < len(self.values):
                self.textvariable.set(self.values[index])
                self.entry.event_generate('<<ComboboxSelected>>')
        else:
            current_value = self.textvariable.get()
            if current_value in self.values:
                return self.values.index(current_value)
            return -1
    
    def apply_theme_styling(self):
        """
        Apply theme-aware styling to the combobox entry and dropdown button.
        Should be called after theme.update() has been applied to the parent frame.
        """
        try:
            from config import config  # type: ignore
            current_theme = config.get_int('theme')
            frame_bg = self.frame.cget('bg')
            
            # Convert named system colors to actual color values
            def get_actual_color(color_name):
                try:
                    temp_widget = tk.Label(self.frame, bg=color_name)
                    temp_widget.update_idletasks()
                    actual_color = temp_widget.cget('bg')
                    temp_widget.destroy()
                    return actual_color
                except:
                    return color_name
            
            # Determine if this is a dark theme
            is_dark_theme = current_theme in [1, 2]  # 1=Dark, 2=Transparent
            
            # Determine background color based on theme
            if frame_bg and frame_bg.strip():
                if current_theme == 2 and frame_bg.lower() == 'systemwindow':
                    bg_color = get_actual_color('systemwindow')
                elif frame_bg.startswith('#'):
                    bg_color = frame_bg
                elif frame_bg.lower() not in ['white', '#ffffff', 'systembuttonface']:
                    bg_color = get_actual_color(frame_bg)
                else:
                    bg_color = '#1e1e1e' if is_dark_theme else '#ffffff'
            else:
                bg_color = '#1e1e1e' if is_dark_theme else '#ffffff'
            
            # Determine foreground color based on theme
            # Dark/Transparent themes: orange
            # Default (light) theme: use default system colors (let theme.update handle it)
            if is_dark_theme:
                fg_color = 'orange'
                insert_color = 'orange'
            else:
                # For default theme, use system defaults (black text on white)
                fg_color = 'SystemWindowText'  # System default text color
                insert_color = 'black'
            
            # Style the entry field
            self.entry.config(
                bg=bg_color,
                fg=fg_color,
                insertbackground=insert_color,
                readonlybackground=bg_color
            )
            
            # Style the dropdown button
            self.dropdown_btn.config(
                bg=bg_color,
                fg=fg_color,
                activebackground=bg_color,
                activeforeground=fg_color
            )
            
            # Apply theme to the combobox frame and widgets
            theme.update(self.frame)
            theme.update(self.entry)
            theme.update(self.dropdown_btn)
            
        except Exception as e:
            # Silently fail if styling can't be applied
            pass


def style_listbox_for_theme(listbox, parent_frame=None):
    """
    Apply theme-aware styling to a Listbox widget.
    This helper function can be used to style any listbox to match EDMC themes.
    
    Args:
        listbox: The tk.Listbox widget to style
        parent_frame: Optional parent frame to get background color from.
                     If None, uses listbox's parent.
    """
    try:
        from config import config  # type: ignore
        
        # Get parent frame for background color reference
        if parent_frame is None:
            parent_frame = listbox.master if hasattr(listbox, 'master') else None
        
        if parent_frame:
            frame_bg = parent_frame.cget('bg')
        else:
            frame_bg = None
        
        current_theme = config.get_int('theme')
        
        # Convert named system colors to actual color values
        def get_actual_color(color_name):
            try:
                temp_widget = tk.Label(listbox, bg=color_name)
                temp_widget.update_idletasks()
                actual_color = temp_widget.cget('bg')
                temp_widget.destroy()
                return actual_color
            except:
                return color_name
        
        # Determine background color based on theme
        if frame_bg and frame_bg.strip():
            if current_theme == 2 and frame_bg.lower() == 'systemwindow':
                bg_color = get_actual_color('systemwindow')
            elif frame_bg.startswith('#'):
                bg_color = frame_bg
            elif frame_bg.lower() not in ['white', '#ffffff', 'systembuttonface']:
                bg_color = get_actual_color(frame_bg)
            else:
                bg_color = '#1e1e1e' if current_theme in [1, 2] else '#ffffff'
        else:
            bg_color = '#1e1e1e' if current_theme in [1, 2] else '#ffffff'
        
        # Style the listbox
        listbox.config(
            bg=bg_color,
            fg='orange',
            selectbackground=bg_color,
            selectforeground='orange',
            activestyle='none'
        )
        
        # Apply theme
        theme.update(listbox)
        
    except Exception:
        # Silently fail if styling can't be applied
        pass
