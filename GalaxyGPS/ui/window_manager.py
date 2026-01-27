"""
Window management utilities for creating custom themed windows with drag and resize functionality.
"""

import tkinter as tk
from theme import theme  # type: ignore


def create_themed_window(parent, title, saved_positions=None):
    """
    Create a Toplevel window with custom themed title bar matching EDMC style.
    
    Args:
        parent: Parent window
        title: Window title text
        saved_positions: Optional dict to store window positions (keyed by title)
        
    Returns:
        tuple: (window, content_frame) where content_frame is where widgets should be added
    """
    window = tk.Toplevel(parent)
    window.title(title)
    
    # Hide window until geometry is set to prevent flash in top-left corner
    window.withdraw()
    
    # Use overrideredirect for custom title bar
    # We'll implement native-feeling resize functionality
    window.overrideredirect(True)
    window.resizable(True, True)  # Enable resizing even with overrideredirect
    
    # Make window appear in taskbar (Windows)
    # With overrideredirect, we need to explicitly set window styles
    try:
        # Get the window handle and set extended window styles
        import ctypes
        from ctypes import wintypes
        
        # Wait for window to be created
        window.update_idletasks()
        
        # Get window handle
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        
        # Windows constants
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        
        # Get current extended style
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        
        # Add WS_EX_APPWINDOW (shows in taskbar) and remove WS_EX_TOOLWINDOW (hides from taskbar)
        style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
        
        # Set the new style
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        
        # Force window to update
        window.withdraw()
        window.deiconify()
        window.withdraw()  # Hide again until we're ready to show it
    except Exception as e:
        # If this fails (non-Windows or other error), just continue without taskbar icon
        pass
    
    # Get theme colors for title bar
    window.update_idletasks()
    try:
        # Create a temporary label to get theme colors
        temp_label = tk.Label(window)
        theme.update(temp_label)
        theme_bg = temp_label.cget('bg')
        theme_fg = temp_label.cget('foreground')
        temp_label.destroy()
    except:
        theme_bg = '#1e1e1e'  # Dark theme default
        theme_fg = 'orange'  # EDMC orange
    
    # Create custom title bar
    title_bar = tk.Frame(window, bg=theme_bg, height=30, relief=tk.FLAT, bd=0)
    title_bar.pack(fill=tk.X, side=tk.TOP)
    theme.update(title_bar)
    
    # Title label
    title_label = tk.Label(title_bar, text=title, bg=theme_bg, fg=theme_fg, font=('Arial', 10, 'bold'))
    title_label.pack(side=tk.LEFT, padx=10, pady=5)
    theme.update(title_label)
    
    # Close button
    def close_window():
        # Save window position before closing
        if saved_positions is not None:
            try:
                window.update_idletasks()
                x = window.winfo_x()
                y = window.winfo_y()
                width = window.winfo_width()
                height = window.winfo_height()
                # Store position using window title as key
                saved_positions[title] = (x, y, width, height)
            except:
                pass
        window.destroy()
    
    close_btn = tk.Button(title_bar, text='✕', command=close_window, width=3, 
                         bg=theme_bg, fg=theme_fg, relief=tk.FLAT, bd=0,
                         activebackground='#ff4444', activeforeground='white',
                         font=('Arial', 12, 'bold'))
    close_btn.pack(side=tk.RIGHT, padx=5, pady=2)
    theme.update(close_btn)
    
    # Window dragging functionality
    def start_drag(event):
        window._drag_start_x = event.x
        window._drag_start_y = event.y
    
    def on_drag(event):
        x = window.winfo_x() + event.x - window._drag_start_x
        y = window.winfo_y() + event.y - window._drag_start_y
        window.geometry(f'+{x}+{y}')
    
    # Make entire title bar draggable (including empty space)
    def start_drag_title(event):
        window._drag_start_x = event.x_root
        window._drag_start_y = event.y_root
    
    def on_drag_title(event):
        if not hasattr(window, '_drag_start_x'):
            return
        dx = event.x_root - window._drag_start_x
        dy = event.y_root - window._drag_start_y
        x = window.winfo_x() + dx
        y = window.winfo_y() + dy
        window.geometry(f'+{x}+{y}')
        window._drag_start_x = event.x_root
        window._drag_start_y = event.y_root
    
    def stop_drag_title(event):
        if hasattr(window, '_drag_start_x'):
            delattr(window, '_drag_start_x')
    
    # Bind drag to entire title bar
    # Use add='+' to allow resize handler to also check edges
    title_bar.bind('<Button-1>', start_drag_title, add='+')
    title_bar.bind('<B1-Motion>', on_drag_title)
    title_bar.bind('<ButtonRelease-1>', stop_drag_title)
    title_label.bind('<Button-1>', start_drag_title, add='+')
    title_label.bind('<B1-Motion>', on_drag_title)
    title_label.bind('<ButtonRelease-1>', stop_drag_title)
    # Also make close button draggable (but don't interfere with click)
    close_btn.bind('<Button-1>', lambda e: start_drag_title(e) if e.state == 0x0 else None, add='+')
    
    # Create content frame where all widgets go
    content_frame = tk.Frame(window, bg=theme_bg)
    content_frame.pack(fill=tk.BOTH, expand=True)
    theme.update(content_frame)
    
    # Add native-style window resizing functionality
    # Only detect resize on actual window edges using screen coordinates
    resize_border_width = 15  # Border width for easier grabbing
    
    def check_resize_area(event):
        """Check if mouse is in resize area and return resize direction"""
        # Use screen coordinates to get true window-relative position
        # This works regardless of which widget triggered the event
        try:
            win_x = window.winfo_x()
            win_y = window.winfo_y()
            win_width = window.winfo_width()
            win_height = window.winfo_height()
            
            # Calculate mouse position relative to window using screen coordinates
            mouse_x = event.x_root - win_x
            mouse_y = event.y_root - win_y
            
            # Check if we're on the actual window edges (within border_width pixels)
            # Use only coordinates - widget checks happen in start_resize
            on_left = mouse_x >= 0 and mouse_x < resize_border_width
            on_right = mouse_x > win_width - resize_border_width and mouse_x <= win_width
            on_top = mouse_y >= 0 and mouse_y < resize_border_width
            on_bottom = mouse_y > win_height - resize_border_width and mouse_y <= win_height
            
            return on_left, on_right, on_top, on_bottom
        except:
            # If window geometry isn't ready, return no edges
            return False, False, False, False
    
    def on_mouse_enter(event):
        """Show resize cursors when near window edges"""
        # Don't change cursor if dragging
        if hasattr(window, '_drag_start_x') or hasattr(window, '_resize_start_x'):
            return
        
        on_left, on_right, on_top, on_bottom = check_resize_area(event)
        
        # Set appropriate cursor for resize
        if on_top and on_left:
            window.config(cursor='top_left_corner')
        elif on_top and on_right:
            window.config(cursor='top_right_corner')
        elif on_bottom and on_left:
            window.config(cursor='bottom_left_corner')
        elif on_bottom and on_right:
            window.config(cursor='bottom_right_corner')
        elif on_top or on_bottom:
            window.config(cursor='sb_v_double_arrow')  # Vertical resize
        elif on_left or on_right:
            window.config(cursor='sb_h_double_arrow')  # Horizontal resize
        else:
            window.config(cursor='')
    
    def on_mouse_leave(event):
        """Reset cursor when leaving window"""
        window.config(cursor='')
    
    def start_resize(event):
        """Start resizing the window"""
        # Check if we're actually on a window edge using screen coordinates FIRST
        # This way we can detect edges even if the event came from a scrollbar or other widget
        on_left, on_right, on_top, on_bottom = check_resize_area(event)
        
        # Only proceed if we're actually on an edge
        if not (on_left or on_right or on_top or on_bottom):
            return
        
        # Don't start resize if clicking directly on title bar widgets (that's for dragging)
        # BUT only block if we're NOT on top edge (allow top edge resize from other areas)
        if (event.widget == title_bar or event.widget == title_label or event.widget == close_btn) and not on_top:
            return
        
        # If clicking title bar widgets on top edge, still allow resize from top
        # The drag handler will have lower priority
        
        # If we're on an edge, mark window as resizing to prevent scrollbar interaction
        window._is_resizing = True
        
        # Store resize info
        window._resize_start_x = event.x_root
        window._resize_start_y = event.y_root
        window._resize_start_width = window.winfo_width()
        window._resize_start_height = window.winfo_height()
        window._resize_start_x_pos = window.winfo_x()
        window._resize_start_y_pos = window.winfo_y()
        window._resize_left = on_left
        window._resize_right = on_right
        window._resize_top = on_top
        window._resize_bottom = on_bottom
    
    def on_resize(event):
        """Handle window resizing"""
        if not hasattr(window, '_resize_start_x'):
            return
        
        dx = event.x_root - window._resize_start_x
        dy = event.y_root - window._resize_start_y
        
        new_width = window._resize_start_width
        new_height = window._resize_start_height
        new_x = window._resize_start_x_pos
        new_y = window._resize_start_y_pos
        
        min_width = 400
        min_height = 300
        
        # Resize based on which edges are being dragged
        if window._resize_right:
            new_width = max(min_width, window._resize_start_width + dx)
        elif window._resize_left:
            new_width = max(min_width, window._resize_start_width - dx)
            new_x = window._resize_start_x_pos + dx
            if new_width == min_width:
                new_x = window._resize_start_x_pos + (window._resize_start_width - min_width)
        
        if window._resize_bottom:
            new_height = max(min_height, window._resize_start_height + dy)
        elif window._resize_top:
            new_height = max(min_height, window._resize_start_height - dy)
            new_y = window._resize_start_y_pos + dy
            if new_height == min_height:
                new_y = window._resize_start_y_pos + (window._resize_start_height - min_height)
        
        # Only update if dimensions actually changed (reduces artifacts)
        current_width = window.winfo_width()
        current_height = window.winfo_height()
        current_x = window.winfo_x()
        current_y = window.winfo_y()
        
        # Update only if there's a meaningful change (at least 1 pixel)
        if (int(new_width) != current_width or int(new_height) != current_height or 
            int(new_x) != current_x or int(new_y) != current_y):
            window.geometry(f'{int(new_width)}x{int(new_height)}+{int(new_x)}+{int(new_y)}')
            # Force immediate update to reduce visual lag
            window.update_idletasks()
    
    def stop_resize(event):
        """Stop resizing"""
        if hasattr(window, '_resize_start_x'):
            delattr(window, '_resize_start_x')
        if hasattr(window, '_is_resizing'):
            delattr(window, '_is_resizing')
        window.config(cursor='')
    
    # Bind resize events ONLY to the window itself
    # We use screen coordinates to detect edges, so this works even if events come from inner widgets
    # Only change cursor/resize when actually on window edges
    window.bind('<Motion>', on_mouse_enter)
    window.bind('<Leave>', on_mouse_leave)
    window.bind('<Button-1>', start_resize)
    window.bind('<B1-Motion>', on_resize)
    window.bind('<ButtonRelease-1>', stop_resize)
    
    # Store reference to start_resize so it can be called from scrollbar handlers
    window._start_resize_handler = start_resize
    
    # Helper function to prevent scrollbar interaction during resize
    # This will be used when scrollbars are created later
    def should_block_widget_event(widget, event):
        """Check if widget event should be blocked because we're resizing from an edge"""
        if not hasattr(window, '_is_resizing'):
            return False
        
        # If we're resizing, check if widget is a scrollbar on an edge
        try:
            # Check if widget is a scrollbar (ttk.Scrollbar)
            widget_class = widget.winfo_class()
            if 'Scrollbar' in widget_class:
                # We're resizing, so block scrollbar interaction
                return True
        except:
            pass
        return False
    
    # Store helper for later use
    window._should_block_widget_event = should_block_widget_event
    
    # Store close function for protocol handler
    window._close_func = close_window
    
    return window, content_frame


def restore_window_position(window, title, saved_positions, default_width, default_height):
    """
    Restore window position from saved positions or center on screen.
    
    Args:
        window: The window to position
        title: Window title (used as key in saved_positions)
        saved_positions: Dict of saved positions (keyed by title)
        default_width: Default width if no saved position
        default_height: Default height if no saved position
    """
    saved_pos = saved_positions.get(title) if saved_positions else None
    
    if saved_pos:
        # Restore saved size and position
        saved_x, saved_y, saved_width, saved_height = saved_pos
        # Validate position and size are still reasonable
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # Always use the calculated default_width (for current route's columns) as the primary width
        # This allows the window to both grow and shrink to fit the current route's columns
        # Only ensure minimum width of 800px and maximum of screen width
        window_width = max(800, min(default_width, screen_width - 20))
        window_height = max(400, min(saved_height, screen_height - 20))
        
        # Adjust x position to keep window on screen with new width
        # If width changed significantly, try to keep window centered or adjust position
        x = max(0, min(saved_x, screen_width - window_width))
        y = max(0, min(saved_y, screen_height - window_height))
        
        window.minsize(800, 400)  # Minimum size to show content
        window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Always update saved position with new size to reflect current route's requirements
        if saved_positions is not None:
            saved_positions[title] = (x, y, window_width, window_height)
    else:
        # Set window size to fit all columns and center on screen (first launch)
        window.minsize(800, 400)  # Minimum size to show content
        
        # Center window on screen using calculated width
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width // 2) - (default_width // 2)
        y = (screen_height // 2) - (default_height // 2)
        window.geometry(f"{default_width}x{default_height}+{x}+{y}")
    
    # Show window after geometry is set to prevent flash in top-left corner
    window.deiconify()
