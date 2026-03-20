# Meteoblue Time-Series Pull

This folder stores Meteoblue time-series JSON files for forecast points.

## API Key Handling

Do not hardcode the API key in scripts.

Preferred: store key in a hidden file in this folder named `.meteoblue_api_key`.

Example file contents:

```text
your_real_key_here
```

Alternative format also supported:

```text
METEOBLUE_API_KEY=your_real_key_here
```

The script resolves API key in this order:

1. `--api-key`
2. Hidden key file (`.meteoblue_api_key`)
3. Environment variable (`METEOBLUE_API_KEY`)

Optional env-var method:

### PowerShell (current session)

```powershell
$env:METEOBLUE_API_KEY = "your_real_key_here"
```

### PowerShell (persist for your user)

```powershell
[System.Environment]::SetEnvironmentVariable("METEOBLUE_API_KEY", "your_real_key_here", "User")
```

## Run

From the repository root:

```powershell
python data/forecasts/meteoblue/pull_meteoblue_timeseries.py
```

Optional:

```powershell
python data/forecasts/meteoblue/pull_meteoblue_timeseries.py --timeout 45 --output-dir data/forecasts/meteoblue
```

Optional custom key file path:

```powershell
python data/forecasts/meteoblue/pull_meteoblue_timeseries.py --api-key-file data/forecasts/meteoblue/.meteoblue_api_key
```

## Output

- One file per point, e.g. `snoqualmie_pass.json`
- `manifest.json` summarizing fetched points

## Notes

- Snoqualmie Pass and Blewett Pass use elevations bumped by +500 ft.
- Elevation values are passed in the `asl` API parameter (feet) as requested.
