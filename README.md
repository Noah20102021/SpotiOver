<h1>SpotiOver</h1>
<img src="https://github.com/Noah20102021/SpotiOver/blob/main/Screenshot%202024-10-24%20153210%20(1).png">
<img src="https://developer.spotify.com/images/guidelines/design/logo-size.svg" alt="Spotify logo" style="width:70px">
<h2>Functions</h2>
- Every time a new song starts playing on Spotify, it will be shown in a pop-up.
<br>
- Press CTRL + < to show the pop-up manually.

<h2>How to install</h2>
<h3>1. Download the Python file</h3>
Download the Python file from above and paste it into a new folder wherever you want.
<h3>2. Configure Spotify</h3>
Go to developer.spotify.com and log in with your Spotify account. Then go to "Dashboard" and press "Create App," filling out the form with the following:
<br>
App name: SpotiOver
<br>
App description: Overlay
<br>
Redirect URIs: http://localhost:8888/callback
<br>
Which API/SDKs are you planning to use?: Web API
<br>
<br>
Then go to your new App, and under "Settings," copy your Client-ID and Client-Secret. 
Now open the Python file and paste the following:
<br>
Your client ID in line 199:  
```client_id="Your-Client-ID"```
<br>
Your client secret in line 200:  
```client_secret="Your-Client-Secret"```
<h3>3. Add it to Autostart</h3>
Make sure you have Python and pip installed. Open your terminal or PowerShell and type:
<br>
```pip install pyinstaller```
<br>
if you haven’t already installed PyInstaller. Then, use `cd` to navigate to the folder where your Python file is located. Once there, use:
<br>
```pyinstaller --onefile --windowed --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 --name SpotiOver spotiover.py```
<br>
Wait a few seconds to minutes until the terminal says: "Building EXE from exe-00.toc completed successfully." Now, press WIN + R and type in ```shell:startup```. Create a shortcut to `yourpath/folder/pythonfile/dist/SpotiOver.exe`.
<br>
<h2>And now you're ready</h2>
