@echo off
TITLE Google Earth Engine Authentication
COLOR 0A
ECHO ========================================================
ECHO      Google Earth Engine Authentication Helper
ECHO ========================================================
ECHO.
ECHO This script will open a browser window.
ECHO 1. Log in with your Google Account.
ECHO 2. Copy the authorization code provided.
ECHO 3. Paste it back here and press Enter.
ECHO.
ECHO Starting authentication...
ECHO.

py -c "import ee; ee.Authenticate()"

ECHO.
ECHO ========================================================
ECHO Authentication step finished.
ECHO If you saw "Successfully saved authorization token", you are good to go!
ECHO ========================================================
PAUSE
