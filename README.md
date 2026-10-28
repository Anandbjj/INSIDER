# INSIDER — multiplayer market mystery

## Run on Windows

Double-click `start.bat` and visit http://localhost:8000. Leave the terminal open while playing. Python 3 must be installed.

## Get a public link for the challenge

This is a Python **web service**, not a static website. You need a GitHub account and a Render account.

1. On GitHub, choose **New repository**, name it `insider-market-game`, and make it public or private.
2. In the new repository choose **Add file → Upload files**. Open the extracted project folder (the one with `server.py` and `render.yaml`), select **all files and the `public` folder**, drag them onto the upload area, and commit. Confirm `server.py`, `render.yaml` and `public/index.html` appear in the repository root. Do not upload only the ZIP.
3. In Render, choose **New → Blueprint**, connect GitHub, and select that repository. The included `render.yaml` configures a free Python web service. Approve deployment.
4. Once Render says **Live**, open its `https://...onrender.com` address in a browser. Create a room on one device; open the same address on a different network/device and join with the code. Use this public URL in the contest entry.

Alternative in Render: choose **New → Web Service** linked to this repo; runtime Python; build command `true`; start command `python server.py`; Free plan; health check `/api/health`.

**Hosting limitations:** Rooms live in memory. A restart/redeploy or idle sleep resets ongoing games. Render free services can sleep after 15 minutes of no traffic and wake on a request. Keep the game open while playing; for a stable long-running service, use persistent storage and a continuously running service. Keep a single instance for shared rooms.

## Game rules

3–8 players; six 75-second trading days, $10,000 virtual starting cash, three fictional stocks. The Insider sees tomorrow's headline; the Regulator can accuse after day 4 closes. Correct accusation awards $3,000 and removes the Insider's wealth; incorrect accusation costs up to $2,000 cash. At each close, the server applies news, combined trades and random movement. The host can advance at any time; otherwise the next stage starts automatically after 25 seconds. Highest final portfolio wins. Trading and investigation are fictional and simplified.

## Technical notes

No third-party packages. Python standard-library `ThreadingHTTPServer` serves both the web interface and authoritative multiplayer state. Browsers poll state every second. `PORT` is read from the deployment environment and defaults to 8000 locally. Sessions survive browser refresh on the same device.
