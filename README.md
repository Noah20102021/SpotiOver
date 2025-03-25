# SpotiOver: Your Spotify Now Playing Overlay

![SpotiOver Screenshot](https://github.com/Noah20102021/SpotiOver/blob/main/Screenshot%202024-10-24%20153210%20(1).png)

<img src="https://developer.spotify.com/images/guidelines/design/logo-size.svg" alt="Spotify logo" style="width:70px">

SpotiOver is a lightweight Python application that provides a convenient pop-up overlay displaying the currently playing song from Spotify. Stay informed about your music without interrupting your workflow.

## Features

-   **Automatic Song Display:** A pop-up notification appears whenever a new song starts playing on Spotify.
-   **Manual Pop-Up Trigger:** Press `CTRL + <` to manually display the current song information at any time.

## Installation

Follow these steps to get SpotiOver up and running on your system:

### 1. Download the Python Script

1.  Download the `spotiover.py` file from this repository.
2.  Create a new folder and place the downloaded file inside.

### 2. Configure Spotify API Credentials

1.  Navigate to the Spotify Developer Dashboard: [developer.spotify.com](developer.spotify.com) and log in with your Spotify account.
2.  Click "Create App" and fill in the following details:
    -   **App name:** `SpotiOver`
    -   **App description:** `Spotify Now Playing Overlay`
    -   **Redirect URIs:** `http://localhost:8888/callback`
    -   **Which API/SDKs are you planning to use?:** `Web API`
3.  Go to your newly created app, and under "Settings," copy the "Client ID" and "Client Secret."
4.  Open the `spotiover.py` file in a text editor.
5.  Locate line 199 and replace `"Your-Client-ID"` with your copied Client ID:

    ```python
    client_id = "YOUR_CLIENT_ID"
    ```

6.  Locate line 200 and replace `"Your-Client-Secret"` with your copied Client Secret:

    ```python
    client_secret = "YOUR_CLIENT_SECRET"
    ```

### 3. Build and Add to Autostart

1.  Ensure you have Python and `pip` installed.
2.  Open your terminal or PowerShell and install PyInstaller:

    ```bash
    pip install pyinstaller
    ```

3.  Use `cd` to navigate to the folder containing `spotiover.py`.
4.  Run the following PyInstaller command to create an executable:

    ```bash
    pyinstaller --onefile --windowed --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 --name SpotiOver spotiover.py
    ```

5.  Wait for the build process to complete. You'll see the message "Building EXE from exe-00.toc completed successfully."
6.  Press `WIN + R` and type `shell:startup` to open the Startup folder.
7.  Create a shortcut to the generated `SpotiOver.exe` file located in the `dist` folder within your project directory (e.g., `yourpath/folder/pythonfile/dist/SpotiOver.exe`).

## Ready to Go!

SpotiOver will now automatically launch when you start your computer and display Spotify's current song in a pop-up window. Enjoy your music with instant visual feedback!
