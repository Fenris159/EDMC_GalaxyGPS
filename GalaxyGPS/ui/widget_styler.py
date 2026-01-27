"""
Widget styling utilities for matching EDMC theme.
"""

import tkinter as tk
import tkinter.ttk as ttk
from theme import theme  # type: ignore


def style_scrollbars(h_scrollbar, v_scrollbar, parent_frame):
    """
    Style scrollbars to match EDMC theme colors.
    
    Args:
        h_scrollbar: Horizontal ttk.Scrollbar widget
        v_scrollbar: Vertical ttk.Scrollbar widget
        parent_frame: Parent frame to get theme colors from
    """
    try:
        from config import config  # type: ignore
        
        scrollbar_style = ttk.Style()
        
        # Set ttk theme to 'clam' for better scrollbar styling control
        # 'clam' theme allows more customization than default Windows themes
        try:
            current_ttk_theme = scrollbar_style.theme_use()
            # Only change if using default Windows theme
            if current_ttk_theme in ['vista', 'xpnative', 'winnative']:
                try:
                    scrollbar_style.theme_use('clam')
                except:
                    pass  # If 'clam' not available, continue with current theme
        except:
            pass
        
        # Detect theme directly from config
        try:
            current_theme = config.get_int('theme')
            # 0 = normal, 1 = dark, 2 = transparent
            is_dark = current_theme in [1, 2]
        except:
            # Fallback: try to detect from frame background
            try:
                sample_label = tk.Label(parent_frame)
                theme.update(sample_label)
                theme_bg = sample_label.cget('bg')
                sample_label.destroy()
                # Simple check if background looks dark
                is_dark = (isinstance(theme_bg, str) and 
                         theme_bg.lower() in ['black', '#000000', '#1e1e1e', 'systemwindow'])
            except:
                is_dark = False
        
        # Get theme foreground color for slider
        try:
            sample_label = tk.Label(parent_frame)
            theme.update(sample_label)
            theme_fg = sample_label.cget('foreground')
            theme_bg = sample_label.cget('bg')
            sample_label.destroy()
        except:
            theme_fg = 'orange'
            theme_bg = '#1e1e1e'
        
        if is_dark:
            # Dark/Transparent theme: dark trough, orange slider (always visible)
            # Configure the scrollbar style - use dark colors, make them thicker
            try:
                scrollbar_style.configure('TScrollbar',
                                        background=theme_fg,  # Orange thumb - always visible
                                        troughcolor=theme_bg,  # Dark trough/track
                                        darkcolor=theme_bg,
                                        lightcolor=theme_bg,
                                        bordercolor=theme_bg,
                                        arrowcolor=theme_fg,
                                        gripcount=0,
                                        width=48,  # Double thickness (24 -> 48)
                                        arrowsize=32)  # Double arrow size to match
                # Set active/pressed states - keep orange but maybe slightly brighter
                scrollbar_style.map('TScrollbar',
                                  background=[('active', theme_fg), ('pressed', '#ffb347')],  # Slightly brighter on press
                                  arrowcolor=[('active', theme_fg), ('pressed', '#ffb347')])
            except:
                # Fallback: try simpler configuration
                try:
                    scrollbar_style.configure('TScrollbar',
                                            background=theme_fg,  # Orange thumb
                                            troughcolor=theme_bg,  # Dark trough
                                            arrowcolor=theme_fg,
                                            width=48,
                                            arrowsize=32)
                except:
                    pass
        else:
            # Normal theme: light gray colors, make them thicker
            try:
                scrollbar_style.configure('TScrollbar',
                                        background='#808080',  # Dark gray thumb - always visible
                                        troughcolor='#f0f0f0',  # Light gray trough
                                        darkcolor='#d0d0d0',
                                        lightcolor='#f0f0f0',
                                        bordercolor='#a0a0a0',
                                        arrowcolor='black',
                                        width=48,  # Double thickness (24 -> 48)
                                        arrowsize=32)  # Double arrow size to match
                scrollbar_style.map('TScrollbar',
                                  background=[('active', '#606060'), ('pressed', '#404040')])
            except:
                pass
        
        # Apply theme.update() to scrollbars as well
        try:
            theme.update(h_scrollbar)
            theme.update(v_scrollbar)
        except:
            pass
        
        # Force update of scrollbars
        h_scrollbar.update_idletasks()
        v_scrollbar.update_idletasks()
        
    except Exception as e:
        import logging
        from config import appname  # type: ignore
        import os
        plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
        logger = logging.getLogger(f'{appname}.{plugin_name}')
        logger.debug(f'Error styling scrollbars: {e}', exc_info=True)
        pass
