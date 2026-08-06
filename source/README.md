# Repo Status App (Git Check Tool)

A Windows desktop utility that monitors all Git repositories under a configured root directory. The app runs in the system tray, periodically (about every 60 seconds) checks every repository for local changes (push needed) and remote updates (pull needed), and shows Windows toast notifications when updates are detected.

## Features

- **System Tray Integration** – Runs in the background via a tray icon without cluttering your taskbar.
- **Automatic Repository Discovery** – Recursively scans a given root directory and builds a list of all Git repositories found.
- **Push / Pull Status Detection** – For each repo, determines whether you have local commits to push or remote commits to pull.
- **Windows Toast Notifications** – Displays a notification when a repository is found that needs to be pulled.
- **Bulk Pull** – Pull selected repositories or all repositories at once (using concurrent threads).
- **Colored Status Output** – Uses color-coded text (green / red / orange / blue) to clearly indicate repository status.
- **Persistent Settings** – Remembers the configured root directory in `settings.json`.

## Project Structure

| File              | Description                                                                 |
| ----------------- | --------------------------------------------------------------------------- |
| `GitCheckTool.py` | Main entry point. Sets up the Tkinter window, system tray icon, and the automatic background loop. |
| `CLIManagager.py` | `CLIManagerClass` – Handles the interactive text menu and forwards user input to the repo manager. |
| `RepoLibClass.py` | `RepoManager` and `RepoClass` – Core logic for repo discovery, git commands, status checks, and pulling. |
| `settings.json`   | Stores the configured root directory (e.g. `{"root dir": "C:/GIT"}`).        |
| `icons/`          | PNG icons used for the tray icon and window, representing each status state. |

## Requirements

- Python 3.x
- Windows 10 / 11 (uses `win11toast` for notifications)
- `git` installed and available on the system `PATH`

### Python Dependencies (Already bundled with EXE)

```
pystray
Pillow (PIL)
win11toast
```

Install them with:

```bash
pip install pystray Pillow win11toast
```

## Usage

1. Ensure the `icons/` folder is present in the same directory as `GitCheckTool.py`.
2. Run the application:

   ```bash
   python GitCheckTool.py
   ```

3. On first launch you will be prompted to enter the **root directory** that contains your Git repositories. The app recursively finds every repo below that folder.
4. The app hides into the system tray. Use the tray menu to **Show** or **Quit**.
5. The main window displays a numbered list of all repositories with their status and an interactive menu.

## Installation

1. Download and extract the zip folder, move the contents to desired location.
2. Make a shortcut to the .exe file by right clicking on the file and Send To > Desktop (create shortcut).
3. Navigate in File Explorer to the Startup folder by typing 'Startup' into the path bar.
4. Place the shortcut in the Startup folder and either launch the shortcut or reboot.
5. On first launch, open the window by right clicking the icon and selecting 'Show'. You will need to enter the path to the directory containing your repositories.

### Interactive Menu

```
Main Menu:
    0. Set root directory for repositories
    1. Check all repositories for changes
    2. Pull for certain repositories
    3. Pull for all repositories
```

- **0** – Change the root directory that is scanned for repositories.
- **1** – Re-scan and check the status of every repository.
- **2** – Pull only the repositories you select (enter their numbers separated by commas).
- **3** – Pull all repositories that have remote changes available.

### Status Indicators

| Status | Meaning                                                        | Color  |
| ------ | -------------------------------------------------------------- | ------ |
| GOOD   | Up to date – nothing to push or pull.                          | Green  |
| PUSH   | Local commits exist that need to be pushed.                    | Orange |
| PULL   | Remote commits exist that can be pulled.                       | Red    |
| BOTH   | Both push and pull actions are available.                      | Red / Orange |
| BUSY   | The app is currently scanning or performing git operations.    | –      |

The tray icon also changes to reflect the current aggregate status of all repositories.

## How It Works

1. **Startup** – `GitCheckTool.py` initializes the Tkinter window and the system tray icon, then starts a background daemon thread.
2. **Auto Loop** – Every ~60 seconds (30 counts of a 2-second loop) the manager checks for repository status changes while the window is hidden.
3. **Repo Discovery** – `RepoManager` recursively walks the root directory looking for `.git` folders and registers each one as a `RepoClass`.
4. **Status Check** – `RepoClass.refresh_status()` runs `git fetch` and `git status` to determine whether push and/or pull is needed.
5. **Notifications** – When a repo is discovered to have a pull available (and notifications are enabled), a Windows toast is shown with a **View** / **Dismiss All** button.
6. **Pulling** – Pulls are executed concurrently using a `ThreadPoolExecutor`, running `git pull` in each selected repository.

## Configuration

The root directory is stored in `settings.json`, Example:

```json
{
  "root dir": "C:/GIT"
}
```

You can edit this file directly, or change it from within the app using menu option **0**.

## Notes

- The `settings.json` file and the `icons/` directory must be located in the **current working directory** from which the app is launched.
- Closing the main window hides the app to the tray instead of quitting. Use the tray menu **Quit** to exit completely.
- Toast notifications are only displayed when the main window is hidden, so you are not interrupted while working.

## AI Disclaimer

- Model used was Blackbox's open-source AI.
- No running source was AI generated.
- Comments were generated.
- This README was generated.
- All AI generated material was reviewed for accuracy.

## Current Version

**1.0.0**

## Changelog
- 2026-08-061.0.0 - initial release