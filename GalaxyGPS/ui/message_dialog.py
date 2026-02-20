"""
Custom themed message dialogs matching EDMC style.
"""

import tkinter as tk
from theme import theme  # type: ignore

# Localization: use plugin's tl from package (PLUGINS.md: avoid "from load import" across plugins)
from GalaxyGPS import _plugin_tl as plugin_tl


def show_themed_message(parent, title, message, message_type="info", buttons="ok"):
    """
    Show a custom themed message dialog matching EDMC style.
    
    Args:
        parent: Parent window
        title: Dialog title
        message: Message text to display
        message_type: Type of message ("info", "warning", "error")
        buttons: Button configuration ("ok", "yesno", "okcancel")
        
    Returns:
        True/False for yesno/okcancel, None for ok
    """
    # Create custom themed window
    from .window_manager import create_themed_window
    
    dialog_window, content_frame = create_themed_window(parent, title, None)
    
    # Get theme colors
    try:
        temp_label = tk.Label(content_frame)
        theme.update(temp_label)
        theme_bg = temp_label.cget('bg')
        theme_fg = temp_label.cget('foreground')
        temp_label.destroy()
    except:
        theme_bg = '#1e1e1e'
        theme_fg = 'orange'
    
    # Create main content frame with padding
    main_content = tk.Frame(content_frame, bg=theme_bg)
    main_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    theme.update(main_content)
    
    # Icon and message frame - use pack layout
    message_frame = tk.Frame(main_content, bg=theme_bg)
    message_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
    theme.update(message_frame)
    
    # Icon (simple text-based for now)
    icon_text = ""
    icon_color = theme_fg
    if message_type == "error":
        icon_text = "✕"
        icon_color = "#ff4444"
    elif message_type == "warning":
        icon_text = "⚠"
        icon_color = "#ffaa00"
    else:  # info
        icon_text = "ℹ"
        icon_color = theme_fg
    
    if icon_text:
        icon_label = tk.Label(message_frame, text=icon_text, font=('Arial', 24, 'bold'),
                            bg=theme_bg, fg=icon_color)
        icon_label.pack(side=tk.LEFT, padx=(0, 15), anchor=tk.N)
        theme.update(icon_label)
    
    # Message text - use Text widget for better wrapping control
    # Use Text widget with proper wrapping
    message_text = tk.Text(message_frame, wrap=tk.WORD, font=('Arial', 10),
                          bg=theme_bg, fg=theme_fg, relief=tk.FLAT, bd=0,
                          padx=5, pady=5, width=50, height=5)  # Reasonable default size
    message_text.insert('1.0', message)
    message_text.config(state=tk.DISABLED)  # Make read-only
    message_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    theme.update(message_text)
    
    # Button frame
    button_frame = tk.Frame(main_content, bg=theme_bg)
    button_frame.pack(fill=tk.X)
    theme.update(button_frame)
    
    result = [None]  # Use list to allow modification in nested functions
    
    def on_ok():
        result[0] = True
        dialog_window.destroy()
    
    def on_yes():
        result[0] = True
        dialog_window.destroy()
    
    def on_no():
        result[0] = False
        dialog_window.destroy()
    
    def on_cancel():
        result[0] = False
        dialog_window.destroy()
    
    # Create buttons based on configuration
    if buttons == "yesno":
        # LANG: Yes button in confirmation dialogs
        yes_btn = tk.Button(button_frame, text=plugin_tl("Yes"), command=on_yes,
                          bg=theme_bg, fg=theme_fg, relief=tk.RAISED,
                          padx=20, pady=5, font=('Arial', 10, 'bold'))
        yes_btn.pack(side=tk.RIGHT, padx=(10, 0))
        theme.update(yes_btn)
        
        # LANG: No button in confirmation dialogs
        no_btn = tk.Button(button_frame, text=plugin_tl("No"), command=on_no,
                         bg=theme_bg, fg=theme_fg, relief=tk.RAISED,
                         padx=20, pady=5, font=('Arial', 10))
        no_btn.pack(side=tk.RIGHT)
        theme.update(no_btn)
    elif buttons == "okcancel":
        # LANG: OK button in dialogs
        ok_btn = tk.Button(button_frame, text=plugin_tl("OK"), command=on_ok,
                          bg=theme_bg, fg=theme_fg, relief=tk.RAISED,
                          padx=20, pady=5, font=('Arial', 10, 'bold'))
        ok_btn.pack(side=tk.RIGHT, padx=(10, 0))
        theme.update(ok_btn)
        
        # LANG: Cancel button in dialogs
        cancel_btn = tk.Button(button_frame, text=plugin_tl("Cancel"), command=on_cancel,
                             bg=theme_bg, fg=theme_fg, relief=tk.RAISED,
                             padx=20, pady=5, font=('Arial', 10))
        cancel_btn.pack(side=tk.RIGHT)
        theme.update(cancel_btn)
    else:  # ok
        # LANG: OK button in dialogs
        ok_btn = tk.Button(button_frame, text=plugin_tl("OK"), command=on_ok,
                          bg=theme_bg, fg=theme_fg, relief=tk.RAISED,
                          padx=20, pady=5, font=('Arial', 10, 'bold'))
        ok_btn.pack(side=tk.RIGHT)
        theme.update(ok_btn)
    
    # Set initial window size - will adjust after text wraps
    dialog_window.update_idletasks()
    
    # Calculate approximate size needed
    # Count lines in message
    message_lines = message.split('\n')
    line_count = len(message_lines)
    
    # Estimate character width (Arial 10 is roughly 6-7 pixels per character)
    max_chars_per_line = 0
    for line in message_lines:
        max_chars_per_line = max(max_chars_per_line, len(line))
    
    # Set text widget width to ensure proper wrapping
    # Use a reasonable width (50-60 characters is good for readability)
    text_widget_width = min(max(50, max_chars_per_line + 10), 70)
    message_text.config(width=text_widget_width)
    
    # Calculate window width based on text widget width
    # Text widget width in characters * ~7 pixels per char + icon + padding
    estimated_text_width_pixels = text_widget_width * 7
    window_width = max(450, min(estimated_text_width_pixels + 150, 700))  # Icon (50px) + padding (100px)
    
    # Update geometry to set width
    screen_width = dialog_window.winfo_screenwidth()
    screen_height = dialog_window.winfo_screenheight()
    dialog_window.geometry(f"{window_width}x300+{(screen_width // 2) - (window_width // 2)}+{(screen_height // 2) - 150}")
    dialog_window.minsize(450, 180)
    dialog_window.maxsize(700, 600)
    
    # Force update to get actual heights after all widgets are created and packed
    # This ensures all buttons are rendered and we get accurate measurements
    dialog_window.update_idletasks()
    message_text.update_idletasks()
    button_frame.update_idletasks()
    
    # Update button widgets individually to ensure they're measured correctly
    if buttons == "yesno":
        yes_btn.update_idletasks()
        no_btn.update_idletasks()
    elif buttons == "okcancel":
        ok_btn.update_idletasks()
        cancel_btn.update_idletasks()
    else:  # ok
        ok_btn.update_idletasks()
    
    # Get actual required heights of all components
    actual_text_height = message_text.winfo_reqheight()
    actual_button_height = button_frame.winfo_reqheight()
    
    # Get icon height if present
    icon_height = 0
    if icon_text:
        icon_label.update_idletasks()
        icon_height = icon_label.winfo_reqheight()
    
    # Calculate total window height needed
    # Title bar: ~30px
    # Main content padding: 20px top + 20px bottom = 40px
    # Message frame padding bottom: 20px
    # Text height: actual_text_height (or icon height if larger)
    # Button frame height: actual_button_height (with extra padding for safety)
    # Extra safety margin: 30px to ensure buttons are never cut off
    title_bar_height = 30
    content_padding = 40  # 20px top + 20px bottom
    message_frame_bottom_padding = 20
    safety_margin = 30  # Increased safety margin to prevent button cutoff
    
    # Use the larger of icon or text height for the message area
    message_area_height = max(icon_height, actual_text_height)
    
    # Ensure button height has minimum padding
    button_area_height = max(actual_button_height + 10, 50)  # At least 50px for button area
    
    total_height = (title_bar_height + 
                   content_padding + 
                   message_area_height + 
                   message_frame_bottom_padding + 
                   button_area_height + 
                   safety_margin)
    
    window_height = max(220, total_height)  # Minimum 220px (increased from 200)
    window_height = min(window_height, 600)  # Cap at max height
    
    # Center window with final size
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    dialog_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    # Make window modal and always on top
    # Note: We do NOT use transient() because that prevents taskbar icon
    # Instead we use grab_set() to make it modal and topmost to keep it on top
    dialog_window.grab_set()
    dialog_window.attributes('-topmost', True)
    
    # Initial beep to alert user
    dialog_window.bell()
    
    # Flash window when user tries to interact with parent or other windows
    def on_parent_click(event):
        """Flash the dialog when user tries to click parent window"""
        try:
            dialog_window.bell()  # System beep
            # Force window back to front
            dialog_window.lift()
            dialog_window.focus_force()
        except:
            pass
    
    # Bind click events on parent to flash dialog
    # This catches attempts to click the main EDMC window
    parent_click_binding = parent.bind('<Button-1>', on_parent_click, add='+')
    
    # Clean up binding when dialog closes
    original_destroy = dialog_window.destroy
    def cleanup_and_destroy():
        try:
            parent.unbind('<Button-1>', parent_click_binding)
        except:
            pass
        original_destroy()
    dialog_window.destroy = cleanup_and_destroy
    
    # Show window
    dialog_window.deiconify()
    
    # Force focus to dialog
    dialog_window.focus_force()
    
    # Periodic check to ensure dialog keeps focus and stays on top
    def keep_on_top():
        """Periodically ensure dialog stays on top and has focus"""
        try:
            if dialog_window.winfo_exists():
                # Check if dialog has lost focus
                focused_widget = dialog_window.focus_get()
                if focused_widget is None or focused_widget.winfo_toplevel() != dialog_window:
                    # Dialog lost focus - beep and restore
                    dialog_window.bell()
                    dialog_window.lift()
                    dialog_window.focus_force()
                
                # Schedule next check
                dialog_window.after(200, keep_on_top)
        except:
            pass
    
    # Start the focus monitoring
    dialog_window.after(200, keep_on_top)
    
    # Wait for window to be destroyed
    dialog_window.wait_window()
    
    return result[0]


def showinfo(parent, title, message):
    """Show an info message dialog."""
    return show_themed_message(parent, title, message, "info", "ok")


def showwarning(parent, title, message):
    """Show a warning message dialog."""
    return show_themed_message(parent, title, message, "warning", "ok")


def showerror(parent, title, message):
    """Show an error message dialog."""
    return show_themed_message(parent, title, message, "error", "ok")


def askyesno(parent, title, message):
    """Show a yes/no question dialog."""
    return show_themed_message(parent, title, message, "info", "yesno")


def askokcancel(parent, title, message):
    """Show an OK/Cancel question dialog."""
    return show_themed_message(parent, title, message, "info", "okcancel")
