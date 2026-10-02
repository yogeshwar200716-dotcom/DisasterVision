DISASTERVISION - UPDATED FINAL BUILD
=====================================

This package keeps the existing DisasterVision UI and calculation flow.

REQUESTED CHANGES
-----------------
1. Earth drag direction now follows the cursor direction.
2. Predicted disaster year is shown at the top-right of the Analysis results box.
3. Location list follows the latest uploaded Satellite_data.zip folder names exactly.
4. The corrupted spelling "Brei├░amerkurj├╢kull, Iceland" is NOT used.
   The folder name is the exact Unicode name from the uploaded ZIP:
   "Breiðamerkurjökull, Iceland".
5. No photo upload is required.

CLIENT
------
- GLACIER is selected by default.
- Select a location.
- Enter a future year.
- Click Run analysis.

LOCATION FOLDERS FROM THE UPLOADED ZIP
--------------------------------------
BEAR, ALASKA
Breiðamerkurjökull, Iceland
Brunt Ice Shelf, Antarctica
CULOMBIA
Kilimanjaro,tanzania
Petermann, greenland
Svalbard, NORWAY
VERDI,ANTARCTICA

CULOMBIA is present because it is a folder in the uploaded ZIP, but it
currently contains no dated satellite images. If selected, the application
reports that no dated satellite images are available instead of inventing data.

SERVER DATA
-----------
satellite_data/GLACIER/<LOCATION>/

The server automatically selects the latest dated image in the selected
location as the baseline and compares earlier dated images against it.

ANALYSIS
--------
- Historical image change percentages
- Future-year predicted change
- LOW / MODERATE / HIGH risk
- Estimated disaster-risk window
- Mathematical prediction equation
- Predicted disaster year shown in the Analysis results header

EARTH
-----
The Earth globe is local and does not require a CDN or internet connection.
It starts zoomed out.
Dragging the cursor moves the Earth in the same direction as the cursor.
Mouse wheel controls zoom.

RUN ON WINDOWS
--------------
1. Extract this ZIP.
2. Double-click run.bat.
3. Wait for the terminal.
4. Open http://127.0.0.1:8000 in a fresh browser tab.
5. Do not run an older DisasterVision copy at the same time.

MANUAL
------
python -m pip install -r requirements.txt
python client.py

client.py automatically starts Server.py on the internal analysis port 5517.
