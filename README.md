# Spotify Popup

A small Now-Playing widget for Windows: Whenever a new song starts (or on keypress), a dark popup appears in the top-left corner displaying the cover art, artist, and track title.

This is an updated version of the original script – same look and feel, but modernized with current Python/PyQt6 standards, no credentials in the code, and full Windows integration.

---

## Quick Summary

> Detailed step-by-step guide: **ANLEITUNG.md**

```bat
build.bat            :: Creates dist\SpotifyPopup.exe
```

**Renaming?** Only edit `spotify_popup/__init__.py` – change `APP_NAME` (executable name, folder, registry key) and `APP_DISPLAY_NAME` (all visible text). Everything else will follow automatically.  
⚠️ **But first run `SpotifyPopup.exe --uninstall`**, otherwise old registry entries remain and saved credentials will be stored under the old name.

Then, double-click `SpotifyPopup.exe` once:

1. Language prompt: **German** or **English**  
   (default is your Windows language)
2. The app registers itself in the startup and Start menu
3. Settings window opens → enter your Client ID → copy the Redirect URI and paste it into the Spotify Developer Dashboard → **Sign in with Spotify**

That’s it. From now on, the service runs in the background at every Windows startup.

The `.exe` contains **no credentials** and can therefore be safely uploaded to GitHub.

---

## What Each Execution Does

| Command | Behavior |
|-------|----------|
| Double-click / Windows Search / Start Menu | **Settings window** |
| `SpotifyPopup.exe --service` (in Autostart) | **Background service**, no window, only tray icon |
| `SpotifyPopup.exe --uninstall` (in "Installed Apps") | Removes autostart, Start menu shortcut, app entry, optionally deletes data |

---

## Language Support

On first launch, the app asks whether to run in German or English (default: your Windows language).  
You can change it anytime in the **System** tab → *Language* – the window instantly rebuilds in the new language. The running background service immediately updates its tray menu accordingly.

Translations are stored as simple dictionaries in `spotify_popup/i18n.py`. Adding a new language requires only one more entry.

---

## Autostart

Autostart is **enabled by default** and can be disabled in the **System** tab – along with the Start menu shortcut and the "Installed Apps" entry.  
All three checkboxes are applied immediately upon saving. They reflect the **actual** registry state, not just the stored preference.

On first launch, the app sets itself up automatically:
- Autostart entry (`HKCU\...\CurrentVersion\Run`)
- Start menu shortcut (for Windows Search visibility)
- Entry under "Installed Apps"

All done without admin rights, entirely within the user profile.

Changes to settings are applied instantly by the running service – no restart required.

---

## Spotify Setup

In the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create a new app and set the **Redirect URI** exactly as shown in the settings window:

```
http://127.0.0.1:8888/callback
```

> Important: `http://localhost:8888/callback` is now rejected by Spotify. Only the loopback **IP address** (`127.0.0.1`) is allowed for `http`.

**Client Secret is optional.** Leaving the field blank enables PKCE (Proof Key for Code Exchange), the recommended method for desktop apps. No secret is ever stored on disk.

### The 6-Month Token Expiry

From Spotify’s email: Refresh tokens expire after six months (by July 20, 2026), returning `invalid_grant`. This is handled in `spotify_auth.py`:

- `invalid_grant` → stored token is **discarded**, no retry attempt
- The service shows a tray notification and opens the settings window
- Clicking **"Sign in with Spotify"** resumes normal operation
- Network errors do **not** trigger token discard
- Rotated refresh tokens (common with PKCE) are always preserved

The settings window also displays the current session’s expiry date.

---

## Where Are Credentials Stored?

Not in code, not in the `.exe`, not in the repo:

1. **Windows Credential Manager** via `keyring` (default)
2. Fallback: `%APPDATA%\SpotifyPopup\secrets.dat`, encrypted with Windows DPAPI tied to your user account

Non-sensitive settings: `%APPDATA%\SpotifyPopup\settings.json`  
Logs: `app.log`

---

## Experimental Features (in the "Experimental" tab)

Both features are **disabled by default**. When off, the popup behaves exactly like the old version.

### Progress Bar
The bottom 3 pixels of the popup fill green from left to right, matching the song’s progress – *within* the rounded path. The bar inherits the corner radius of the bottom corners.  
No separate widget: it’s drawn directly onto the popup. Layout, size, and overall design remain unchanged (this was the main issue in the old version – now the bar is part of the drawing, not a separate element).

### Animations
Selectable modes:

| Mode | Behavior |
|------|----------|
| `Classic` | As before: slide-up from top, 300 ms, cubic easing |
| `Smooth Slide` | Gentle ease-out quint curve, slightly longer duration |
| `Overshoot` | Slides past target briefly, then bounces back |
| `Pop / Scale` | No slide – popup scales from 86% to 100% and fades in |
| `Slide + Pop` | Slide and scale-up happen simultaneously |

Base duration is adjustable. "Preview" shows the result instantly using a dummy track.

---

## Improvements Over the Old Script

- **Removed `spotipy`**: Only the needed endpoint (`/me/player/currently-playing`) is called directly. Fewer dependencies, and `invalid_grant` is handled cleanly.
- Cover images are loaded in the background (previously `requests.get` blocked the UI thread, causing janky popup animations).
- `429 Too Many Requests` is caught using `Retry-After`; `401` is retried once with refresh.
- Hotkey was broken: `'<ctrl>+<'` can’t be parsed by `pynput`. Default is now `<ctrl>+<226>` (VK_OEM_102 – the `<` key on German keyboards), and it’s configurable with a "Test" button.
- Popup is **click-through**, so it never blocks your view.
- **Single-instance lock**: The service runs only once.
- Podcast episodes are ignored (they lack an `artists` field and previously caused issues).

---

## Development Without Building

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m spotify_popup            :: Settings window
python -m spotify_popup --service  :: Background service
```

---

## Project Structure

```
main.py                     Entry point for PyInstaller
build.spec                  Build config (exe name comes from APP_NAME)
build.bat                   One-click build
spotify_popup/
  __init__.py               APP_NAME / APP_DISPLAY_NAME – only place to rename
  __main__.py               Handles arguments: --service / --uninstall
  config.py                 Settings (JSON)
  secrets_store.py          keyring + DPAPI fallback
  spotify_auth.py           OAuth, PKCE, refresh, invalid_grant handling
  spotify_client.py         currently-playing API calls
  popup.py                  The widget (drawing, animations, progress bar)
  service.py                Background service, tray, polling
  settings_window.py        Settings UI
  windows_integration.py    Autostart, Start menu, Installed Apps
  hotkey.py                 Global hotkey
  icons.py                  App and tray icons
  i18n.py                   Translations (de/en)
tools/make_icon.py          Generates assets/icon.ico
```