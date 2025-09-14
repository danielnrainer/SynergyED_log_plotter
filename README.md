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
- **Email notifications** - Automated alerts when parameters exceed thresholds during live monitoring

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

5. Email Notifications (Optional):
   - Click "Configure Email Alerts" to set up automated monitoring
   - Define trigger conditions for critical parameters
   - Enable live plotting to activate email monitoring

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

## Email Notifications

The application supports automated email alerts that trigger when specified conditions are met during live plotting. This is particularly useful for monitoring critical parameters overnight or during extended measurements.

### Setting Up Email Notifications

1. **Access Configuration**: Click "Configure Email Alerts" in the Email Notifications section
2. **Choose Email Provider**: Select from common providers or use custom SMTP settings
3. **Enter Credentials**: Provide your email address and authentication details
4. **Set Recipient**: Specify where alerts should be sent
5. **Define Triggers**: Configure parameter thresholds and conditions
6. **Test Setup**: Verify configuration with test connection and test email

### Supported Email Providers

- **Gmail** (recommended - see setup guide below)
- **Outlook/Hotmail**
- **Yahoo Mail**
- **Exchange/Office365**
- **Custom SMTP** (for other providers)

### Gmail Setup Guide

Gmail requires an **App Password** for third-party applications. Follow these steps:

#### Step 1: Enable 2-Factor Authentication
1. Go to your [Google Account settings](https://myaccount.google.com/)
2. Click "Security" in the left sidebar
3. Under "Signing in to Google", click "2-Step Verification"
4. Follow the prompts to enable 2FA if not already enabled

#### Step 2: Generate App Password
1. In Google Account Security settings, click "App passwords"
2. Select "Mail" for the app and "Windows Computer" (or appropriate device)
3. Click "Generate"
4. **Copy the 16-character password** (e.g., `abcd efgh ijkl mnop`)
5. Use this app password (not your regular Gmail password) in the application

#### Step 3: Configure in Application
1. **Email Provider**: Select "Gmail"
2. **Sender Email**: Your full Gmail address (e.g., `your.email@gmail.com`)
3. **Sender Password**: The 16-character app password from Step 2
4. **SMTP Server**: `smtp.gmail.com` (auto-filled)
5. **Port**: `587` (auto-filled)

> **Important**: Never use your regular Gmail password. Always use the app password generated specifically for this application.

### Trigger Conditions

You can set up alerts based on parameter values:

#### Condition Types
- **Greater than**: Alert when parameter exceeds a threshold
- **Less than**: Alert when parameter drops below a threshold
- **Equals**: Alert when parameter matches a specific value

#### Duration-Based Triggers
- **Immediate**: Alert triggers as soon as condition is met
- **Duration**: Alert only after condition persists for specified time
  - Example: "RT1 PiG5 > 100 for 120 minutes"

#### Example Trigger Scenarios
- **Vacuum Issue**: `RT1 PiG5 > 100` (immediate)
- **Extended High Current**: `Beam Current [uA] > 90 for 30 minutes`
- **Temperature Drift**: `HT [kV] < 180 for 60 minutes`
- **Stage Position Alert**: `Stage Z [um] > 200` (immediate)

### Email Alert Content

When a trigger condition is met, you'll receive an email containing:
- **Timestamp** of the alert
- **Parameter name** and current value
- **Threshold** that was exceeded
- **Trigger description** (condition and duration)

### Troubleshooting Email Setup

#### Common Issues
1. **Authentication Failed**
   - For Gmail: Ensure you're using app password, not regular password
   - Verify 2FA is enabled on your Google account
   - Check email address is correct

2. **Connection Failed**
   - Verify internet connection
   - Check firewall/antivirus isn't blocking SMTP
   - Ensure SMTP server and port are correct

3. **Test Email Not Received**
   - Check spam/junk folder
   - Verify recipient email address
   - Try sending a test alert after configuration

#### Security Notes
- **App passwords** are safer than using your main password
- **Email credentials** are stored locally and not transmitted elsewhere
- **Test your setup** regularly to ensure alerts will work when needed

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
