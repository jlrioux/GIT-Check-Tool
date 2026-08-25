# =============================================================================
# GitCheckTool.py
# -----------------------------------------------------------------------------
# A system-tray "Repo Status App" built with Tkinter + pystray.
# It runs in the background, periodically checks the status of configured Git
# repositories, updates a tray/window icon to reflect the status, and sends
# Windows toast notifications when relevant updates occur.
# =============================================================================

# --- Standard library / third-party imports ---------------------------------
import tkinter as tk                 # Core GUI framework (Tkinter)
from tkinter import scrolledtext     # Scrollable text widget for console output
import pystray                       # System tray icon support
import time                          # Sleep/delays for the background loop
import threading                     # Background threads (tray + auto-loop)
import os                            # Filesystem ops and current working dir
from PIL import Image                # Load PNG images for the tray/window icons
from win11toast import toast         # Windows 11 toast notification helper
from CLIManagager import CLIManagerClass  # Custom CLI manager that runs git commands

# --- Version constant --------------------------------------------------------
# String identifying the app version (used in the UI version label).
__version = '1_1_2'


# --- Notification helper ------------------------------------------------------
def send_toast(title,content):
    # Thin wrapper around the win11toast toast() function.
    # title:   notification title string
    # content: notification body string
    toast(title, content)

# Store the working directory at startup; used later to build icon paths.
cwd = os.getcwd()

# Global reference to the CLI manager instance.
# It is created lazily inside the background auto-loop once the app is ready.
cli_manager = None

# --- Global state -------------------------------------------------------------
# every 1 minute, while the program is in the background, check for repo status
# and push windows notifications if an update occurs
window_is_shown = True               # True while the main window is visible
__auto_loop_count = 0                # Counter driving the periodic background loop
# Dictionary holding the current icon/status state for the app.
icon_settings = {'status':'INIT',    # Current status code (INIT, GOOD, PUSH, PULL, BOTH, BUSY)
                 'old status':'',    # Previously displayed status (to detect changes)
                 'ready':False}      # True once the UI is fully initialized

# --- Icon update helper -------------------------------------------------------
def __set_icon():
    # Update the tray icon and the window titlebar icon to match the current status.
    status = icon_settings['status']             # Read current status
    icon_settings['old status'] = status         # Remember it as the "old" status
    txt = 'Repo Status App\nStatus: {}'.format(icon_settings['status'])  # Tray tooltip text
    taskbar_icon.title = txt                     # Set the tray tooltip
    taskbar_icon.icon = imgs[status]             # Swap the tray icon image
    root.iconphoto(True,window_imgs[status])     # Swap the window taskbar/title icon

# --- Background auto-loop thread -----------------------------------------------
def __auto_loop():
    # Runs on a daemon thread. Continuously sleeps and, once the app is 'ready',
    # performs status checks and refreshes the icon / notifications.
    global __auto_loop_count
    global cli_manager
    while(True):
        time.sleep(2)                            # Poll every 2 seconds
        if icon_settings['ready']:               # Only act once UI is ready
            __auto_loop_count += 1
            if __auto_loop_count < 2: pass        # First cycles: do nothing yet
            elif __auto_loop_count == 2:         # On the 2nd cycle: bootstrap the CLI manager
                update_status('BUSY')            # Show "busy" status
                __set_icon()                     # Refresh icon
                cli_manager = CLIManagerClass(printout,clearout,update_status)  # Create manager
                cli_manager.Start(not window_is_shown)                          # Start background checks
            else:
                # Every 300 loops (~10m) after startup:
                if __auto_loop_count % 300 == 0:
                    if not window_is_shown and cli_manager.repos.root_directory_set:      # Only when window is hidden (in background)
                        update_status('BUSY')    # Mark as busy while checking
                        cli_manager.user_response('resetUI')  # Trigger a fresh status check
                # If the status changed since last time, refresh the icon.
                if icon_settings['status'] != icon_settings['old status']:
                    __set_icon()
# Launch the auto-loop on a daemon thread so it stops when the main app exits.
__auto_loop_thread = threading.Thread(target=__auto_loop,daemon=True)
__auto_loop_thread.start()

# --- Window show / quit / hide handlers -----------------------------------------
def show_window(icon=None, item=None):
    # Callback for the tray "Show" menu item: bring the main window back to the foreground.
    global window_is_shown
    window_is_shown = True
    root.after(0, root.deiconify)    # Restore/redisplay the window
    user_entry.focus_set()           # Put the cursor in the input field
    if cli_manager:
        if cli_manager.repos:        # If repos are loaded, disable toasts while visible
            cli_manager.repos.allow_toasts = False

def quit_window(icon=None, item=None):
    # Callback for the tray "Quit" menu item: exit the application entirely.
    root.destroy()                   # Destroy the main Tk window
    import sys
    sys.exit(0)                      # Exit the process cleanly
    import os
    os._exit()                       # Fallback hard exit (unreachable after sys.exit)

def hide_window():
    # Hide the main window (called on startup and when the close button is pressed).
    global window_is_shown
    window_is_shown = False
    root.withdraw()                  # Withdraw/hide the window from the screen
    if cli_manager:
        if cli_manager.repos:        # If repos are loaded, re-enable toasts (background mode)
            cli_manager.repos.allow_toasts = True
            user_entry.delete(0,tk.END)      # Clear the input field
            cli_manager.user_response('resetUI')   # Reset the user interface

# --- Status setter --------------------------------------------------------------
def update_status(status):
    # Central place to update the app status. Also handles the special
    # 'SHOW WINDOW' command that brings the window back to the foreground.
    if not status: return            # Ignore empty status
    if status == 'SHOW WINDOW':      # Special command to reveal the window
        show_window()
        return
    icon_settings['status'] = status # Record the new status
    user_entry.focus_set()           # Keep focus on the input field

# --- Icon image loading ----------------------------------------------------------
# Map each status code to its corresponding tray icon image (loaded from disk).
imgs = {
    'INIT':Image.open(cwd+'/icons/status_init.png'),   # Initial/starting state
    'GOOD':Image.open(cwd+'/icons/status_good.png'),   # All up to date
    'PUSH':Image.open(cwd+'/icons/status_push.png'),   # Local commits to push
    'PULL':Image.open(cwd+'/icons/status_pull.png'),   # Remote commits to pull
    'BOTH':Image.open(cwd+'/icons/status_both.png'),   # Both push and pull needed
    'BUSY':Image.open(cwd+'/icons/status_busy.png')    # Checking / working
}
# Build the system tray menu with "Show" and "Quit" actions.
menu = pystray.Menu(
    pystray.MenuItem('Show', show_window),   # Show the main window
    pystray.MenuItem('Quit', quit_window)    # Exit the application
)
# Create and run the system tray icon on its own daemon thread.
taskbar_icon = pystray.Icon("RepoStatus", imgs['INIT'], "Repo Status App", menu)
taskbar_thread = threading.Thread(target=taskbar_icon.run, daemon=True)
taskbar_thread.start()


# --- Main window (Tkinter) setup -------------------------------------------------
root = tk.Tk()                       # Create the root Tk window
root.title("Repo Status App")        # Window title
root.geometry("1024x800")            # Default window size
root.attributes('-toolwindow',True)  # Style as a tool window (no taskbar button)
# Tk-flavored versions of the status icons, used for the window title/taskbar icon.
window_imgs = {
    'INIT':tk.PhotoImage(file=cwd+'/icons/status_init.png'),
    'GOOD':tk.PhotoImage(file=cwd+'/icons/status_good.png'),
    'PUSH':tk.PhotoImage(file=cwd+'/icons/status_push.png'),
    'PULL':tk.PhotoImage(file=cwd+'/icons/status_pull.png'),
    'BOTH':tk.PhotoImage(file=cwd+'/icons/status_both.png'),
    'BUSY':tk.PhotoImage(file=cwd+'/icons/status_busy.png')
}
root.iconphoto(True,window_imgs['INIT'])  # Set the initial window icon

# Bind close button to hide window instead of quitting
root.protocol("WM_DELETE_WINDOW", hide_window)

# --- Output console (scrolled text widget) ----------------------------------------
# Scrollable text area that displays command output from the CLI manager.
output_text = scrolledtext.ScrolledText(root,wrap=tk.NONE,background='lightgray')
output_text.pack(fill=tk.BOTH, ipady=150, padx=10, pady=5, expand=True)
# Define color "tags" used by printout() to colorize different kinds of output.
output_text.tag_config('black',foreground='black')                                  # Plain text
output_text.tag_config('green',foreground='green',font=('Helvetica',10,'bold'))     # Success/OK
output_text.tag_config('blue',foreground='blue',font=('Helvetica',10,'bold'))       # Info
output_text.tag_config('orange',foreground='orange',font=('Helvetica',10,'bold'))   # Warning
output_text.tag_config('red',foreground='red',font=('Helvetica',10,'bold'))         # Error

# --- User command input -------------------------------------------------------------
def run_user_entry(*args):
    # Callback when the user presses Enter in the input field.
    # Reads the typed command, clears the field, and hands it to the CLI manager.
    txt = user_entry.get()           # Get the typed text
    user_entry.delete(0,tk.END)      # Clear the input field
    cli_manager.user_response(txt)   # Send the command to the CLI manager
user_entry = tk.Entry(root,text='')  # Single-line text entry for user commands
user_entry.pack(fill='x', ipady=5, padx=10, pady=5, expand=True)
user_entry.bind('<Return>',run_user_entry)  # Bind Enter key to submit the command

# Version label shown at the bottom of the window.
version_label = tk.Label(root,text='Version {}'.format(__version))
version_label.pack()


# --- Console output helpers -----------------------------------------------------------
def clearout():
    # Clear all text currently shown in the output console.
    output_text.config(state='normal')   # Make the widget editable
    output_text.delete("1.0",tk.END)     # Delete all content
    output_text.config(state='disabled') # Lock it again (read-only)

def printout(text,color='black'):
    # Append text to the output console with the given color tag.
    output_text.config(state='normal')   # Make the widget editable
    output_text.insert(tk.END,text,color)# Insert the text with its color tag
    output_text.config(state='disabled') # Lock it again (read-only)


# --- Application startup ---------------------------------------------------------------
icon_settings['ready'] = True        # Mark the app as fully initialized (starts auto-loop)
hide_window()                        # Start in the background (hidden, tray-only)
root.mainloop()                      # Run the Tkinter event loop
