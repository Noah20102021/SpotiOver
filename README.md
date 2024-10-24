<h1>SpotiOver</h1>
<img scr="https://github.com/Noah20102021/SpotiOver/blob/main/Screenshot%202024-10-24%20153210%20(1).png">
<h2>Functions</h2>
-Evry time a new song start playing on Spotify this will be showen in a pop-up.
<br>
-Press STRG+< to show the pop-up manulay.

<h2>How to install</h2>
<h3>1. Download the Python file</h3>
Download the Python file from above and paste it in a new folder wehrever you want.
<h3>2. Configure Spotify</h3>
Go to developer.spotify.com and log in with your Spotify account than go to "Dashboard" and press "Create App" and fill the Form with the following.
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
Then go to your new App and then to "Settings" coppy your Client-ID and your Client-Secret. 
Now open the Python file and paste the following: <br>
Your client ID in line 199   ```client_id="Your-Client-ID",```<br>
Your client secret in line 200   ```client_secret="Your-Client-Secret",```<br>

