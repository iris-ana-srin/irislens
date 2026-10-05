# irislens
This repo contains 3 modules of IrisLens. 
- cameramgmt (handles all the camera connections)
- identity (facial recognition module)  
&emsp; **NOTE:** Download recognition model from [here]() and unzip it to `<PROJECT_DIR>\identity\models` before running the module.
- surveillance (dvr module)

All modules run independent to each other. They run in both Windows environments and Linux environments (tested through WSL).  
  **NOTE:** Works only with gthread worker class (`gunicorn --bind 0.0.0.0:5051 --worker-class gthread --threads 8 --timeout 0 cameramgmt.app:app`)

Things to do:
1. (dvr) Fix 5s before and 5s after video stitching
2. Containerize
3. (identity) Check tracking and if sort.py is required
4. (identity) Check if app accepts static images of people 
6. (identity) Dynamic fields for db
7. (identity) Single backend ↔ MQTT ↔ WebUI/Optix
5. Fix UI. Unify UI for all 3 modules.