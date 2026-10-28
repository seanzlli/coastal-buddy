# Data (not included)

The live dashboard needs no files: it reads the VLE Global feed at `https://sp02.aveiro.vle.global` directly.

The offline scripts (`detector.inject`, `detector.evaluate`, `predictor/Telemanom`) use VLE Global's historical record, which is their data and is not part of this repository. Ask VLE Global for access, then place the CSV at:

```
data/vle/VLE_Sovereign_Data.csv
```

Columns: `ID, Timestamp, Temp_C, pH, Salinity_PSU, Turbidity_NTU, Signal_dBM, Wind_Speed_ms, Wind_Dir_Deg, Bio_Load_kgm2` (wind is in km/h despite the column name).
