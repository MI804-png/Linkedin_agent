# LinkedIn AutoApply – Chrome Extension

## How to install

1. Keep the local AutoApply dashboard running on your PC
2. Open Chrome and go to `chrome://extensions/`
3. Turn on **Developer mode**
4. Click **Load unpacked** and select this folder
5. The extension icon appears in your toolbar

## How to use

1. Click the extension icon
2. Make sure the **Server URL** points to your local dashboard
	- Default: `http://localhost:5000`
	- Alternate local launcher: `http://localhost:5001`
3. Enter the same AutoApply email and password you use in the local dashboard
4. Toggle **Auto-apply daily** on, or click **Run Now**

## How it works

- Runs inside your own browser on your own machine
- Uses your local AutoApply dashboard for profile data and run reporting
- Finds jobs matching your keywords, clicks Easy Apply, fills the form, and submits
- Keeps the workflow local instead of relying on a hosted cloud deployment

## Notes

- Your PC and browser must be open at the scheduled time for automatic runs
- Configure CV, keywords, and location in the local dashboard first
- If you start the dashboard with `run_5001.py`, update the popup Server URL to `http://localhost:5001`
