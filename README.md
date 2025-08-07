# SynergyED Log Plotter

A graphical tool for plotting and analyzing logging data collected from CrysAlisPRO (Rigaku) SynergyED devices.

## Features

- Plot multiple parameters from SynergyED log files
- Support for both automatic and manual log files
- Flexible date/time range selection
- Customizable axis ranges with auto-scaling option
- Multiple plotting modes (line, scatter, or both)
- Legend and grid options
- Live plotting capability
- Individual parameter range control with auto-scaling options

## Usage

1. Launch the application and select your log directory using the "Change Directory" button.
   - default directory is C:\Xcalibur\log\SynergyED_DiagnosticData

2. Select files to plot using either method:
   - Use the date/time range selector and "Refresh Files" to find files
   - Use "Quick Plot by Time Range" for direct time-based plotting

3. Select parameters to plot:
   - Choose parameters by checking their corresponding checkboxes
   - For each parameter:
     - Use "Auto" for automatic Y-axis scaling
     - Uncheck "Auto" to set manual min/max values
   - Select plot type (Line Plot, Scatter Plot, or Both)

4. Plot Options:
   - Show/hide grid
   - Show/hide legend
   - Enable live plotting for real-time updates

## File Support

- Works with both "old" and "new" log file naming schemes
- Supports manual log files (no specific naming requirements)
- Automatically extracts dates from file contents when needed

## Parameters Available

- High Tension (HT) [kV]
- Beam Current [uA]
- Filament Current [A]
- Pressure Gauges:
  - Penning PeG1
  - Column PiG1
  - Gun PiG2
  - Detector PiG3
  - Specimen PiG4
  - RT1 PiG5
- Stage Positions:
  - X [um]
  - Y [um]
  - Z [um]
  - TX [deg]

## Installation

1. Ensure Python 3.8 or higher is installed
2. Install requirements:
   ```
   pip install -r requirements.txt
   ```

## Running from Source

```
python src/main.py
```
