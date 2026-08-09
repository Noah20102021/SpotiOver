# Step-by-Step Guide to Getting the Widget Running

From "downloaded ZIP" to "popup appears on every song change".  
Takes about 15 minutes the first time (most of it waiting for the build process).

---

## Prerequisites

* Windows 10 or 11
* **Python 3.11 or newer** – https://www.python.org/downloads/
  ✅ **During installation, make sure to check "Add python.exe to PATH"**
  🔍 Verify: Open `cmd`, type `python --version` → it should show a version number.
* A Spotify account (Free tier is sufficient – Premium is not required)

---

## Step 1 – Create a Spotify App

1. Go to https://developer.spotify.com/dashboard and sign in with your Spotify account
2. Click **Create app**
3. Fill in:
   * **App name**: Any name, e.g. `Spotify Popup`
   * **App description**: Any text
   * **Redirect URI**: Enter **exactly** this and click **Add**:
     ```
     http://127.0.0.1:8888/callback
     ```
     ⚠️ **Do NOT use `localhost`** – Spotify now rejects it. Also, no trailing slash.
   * **Which API/SDKs are you planning to use?** → Check **Web API**
4. Save, then open the app’s **Settings**
5. Copy the **Client ID** (keep the window open – you’ll need it in Step 4)

> You **do not need** the Client Secret. The app uses PKCE (Proof Key for Code Exchange) when the field is left empty – meaning **no secret is ever stored on your disk**.

---

## Step 2 – Extract the Project

Unzip the downloaded file to a permanent location, e.g. `C:\Tools\spotify-popup`.

❌ **Do NOT extract to Downloads** – you’ll want the final `.exe` to stay there and not get accidentally deleted during cleanup.

---

## Step 3 – Build the Executable

In the extracted folder, **double-click `build.bat`**.

This script:
- Creates a virtual environment
- Installs PyQt6, requests, pynput, keyring, and PyInstaller
- Generates the icon
- Builds the `.exe`

The first time takes several minutes (PyQt6 download is the biggest bottleneck).

✅ Result: **`dist\SpotifyPopup.exe`**

If the window closes immediately and you can’t read anything:  
Open `cmd` in the project folder (type `cmd` in the address bar → press Enter), then run `build.bat` there – the error message will stay visible.

> **Want to test without building?** See the section at the bottom.

---

## Step 4 – Initial Setup

Double-click `dist\SpotifyPopup.exe`.

1. **Language prompt**: Choose **German** or **English** (default is your Windows language)
2. A short info appears: "The app has registered itself in Autostart and Start menu" → Click OK
3. The settings window opens on the **Spotify** tab:
   * Paste your **Client ID**
   * Leave **Client Secret** blank
   * Confirm the **Redirect URI** shown matches exactly what you entered in Step 1
     (If port 8888 is taken, change it here **and** in the Spotify Dashboard)
   * Click **Save Credentials**
4. Click **Sign in with Spotify** → your browser opens → click **Agree**
   → The page says "Login successful" → you can close the browser

Now, the field above shows the **expiration date** of your current session (approx. 6 months).

⚠️ **Windows SmartScreen warning?**  
The first time, Windows Defender may block the app ("Windows prevented the start of an unknown app").  
This is because the `.exe` is not signed.  
👉 Click **More info** → **Run anyway**.

---

## Step 5 – It’s Running!

The background service has been running all along – look in the system tray (bottom-right).  
Play a song in Spotify – the popup should slide in from the top-left corner.

✅ You can close the settings window – the service stays in the tray.  
🛑 To stop it: Right-click the tray icon → **Exit**.  
🔁 It will start automatically again on every Windows boot.

### Test the popup without waiting for a song change:

- Press **Ctrl + `<`** (the key left of `Y` on a German keyboard), or  
- Go to **System** tab → **Test Popup Now**, or  
- Click the tray icon

---

## Step 6 – Customize to Your Taste

**Tab Display**:  
Adjust display duration, position, polling interval, and the hotkey.  
To change the hotkey: Click **Record**, then press your desired key combination – it will be saved.

**Tab Experimental** (both disabled by default):  
- *Progress Bar*: The bottom 3 pixels fill green with song progress (within rounded corners)  
- *Animations*: 5 modes – use **Preview** to see the effect instantly with a dummy track

**Tab System**:  
Autostart (enabled by default), Start menu shortcut, "Installed Apps" entry, language.

After changes, click **Save** – the running service applies them immediately. No restart needed.

---

## Where Everything Is Stored After Setup

| Location | Purpose |
|--------|--------|
| Settings | `%APPDATA%\SpotifyPopup\settings.json` |
| Logs (check here first if something goes wrong) | `%APPDATA%\SpotifyPopup\app.log` |
| Client ID + Access/Refresh Tokens | Windows Credential Manager (entry: `SpotifyPopup`) |
| Autostart | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |

💡 You can move the `dist\` folder (with the `.exe`) to another location.  
Just open the settings once and **Save** – this updates the autostart and shortcuts to the new path.

---

## Troubleshooting

**"INVALID_CLIENT: Invalid redirect URI"**  
The URI in the Spotify Dashboard does **not match exactly** what’s shown in the settings.  
Common causes:
- Using `localhost` instead of `127.0.0.1`
- Trailing slash (`/`) at the end
- Wrong port number

**Browser says "This page can’t be reached"**  
Port 8888 is already in use. Change the port in settings (e.g., 8899), update the Redirect URI in the Spotify Dashboard, then re-authenticate.

**Popup doesn’t appear**  
Check the log file (`app.log`). Is the service running? Is the tray icon present?  
If the icon is **gray**, the app needs re-authentication – click it.

**Hotkey does nothing**  
Try recording a different combination (e.g., Ctrl+Alt+M).  
Some apps running with admin rights (games, Task Manager) can block global hotkeys – this is normal.

**"Login expired"** – normal after ~6 months  
Spotify changed this policy in July 2026.  
👉 Open settings → **Sign in with Spotify** → done.

**Reset everything**:  
Go to **System** tab → **Delete all data**

**Remove completely**:  
Run `SpotifyPopup.exe --uninstall`, then delete the files.

---

## Appendix – Test Without Building the .exe

```bat
cd C:\Tools\spotify-popup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m spotify_popup              :: Opens settings window
python -m spotify_popup --service    :: Starts background service (in second window)
```

Works identically. The only difference:  
Autostart and Start menu shortcuts point to your Python interpreter in the virtual environment.

Once you build the `.exe`, open the settings once and **Save** – all paths will update to point to the `.exe`.