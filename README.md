# irislens
This repo contains 3 modules of IrisLens. 
- cameramgmt (handles all the camera connections)
- identity (facial recognition module)  
&emsp; **NOTE:** Download recognition model from [here]() and unzip it to `<PROJECT_DIR>\identity\models` before running the module.
- surveillance (dvr module)

All modules run independent of each other. They run in both Windows environments and Linux environments (tested through WSL).  
&emsp; **NOTES:**  
&emsp; * Linux Env - Works only with gthread worker class (`gunicorn --bind <IP ADDRESS>:<PORT> --worker-class gthread --threads 8 --timeout 0 app:app`)  
&emsp; * Windows Env - only tested using Flask's dev server (requires waitress to test production env).   

### To Do:
1. ~~Containerize~~
2. (identity) Single backend ↔ MQTT ↔ WebUI/Optix
1. Fix UI. Unify UI for all 3 modules.
1. Check if gevent can be used instead of gthread --thread 8 and --timeout 0 (infinite hang risk -- deadlocked threads would never be killed by gunicorn) [Check](#the-golden-rule-for-choosing-workers-when-using-gevent)
4. (identity) Check if app accepts static images of people 
3. (dvr) Fix 5s before and 5s after video stitching
3. (identity) Check tracking and if sort.py is required
6. (identity) Dynamic fields for db  
  

#### Rule for Choosing Workers When Using Gevent
For asynchronous workers like gevent, you do not scale workers based on the number of streams (N). Instead, you scale based on the server's hardware. The standard recommendation is:  
`Workers=(2 x (Number of CPU Cores)+1)`  
If the server has 2 CPU cores, you would typically use --workers 5.