import os
import pandas as pd
from datetime import datetime
import re

class LogDataProcessor:
    COLUMNS = [
        'time', 'HT [kV]', 'Beam Current [uA]', 'Filament Current [A]',
        'Penning PeG1', 'Column PiG1', 'Gun PiG2', 'Detector PiG3',
        'Specimen PiG4', 'RT1 PiG5', 'Bias coarse', 'Bias fine',
        'Stage X [um]', 'Stage Y [um]', 'Stage Z [um]', 'Stage TX [deg]'
    ]
    
    NUMERIC_COLUMNS = [
        'HT [kV]', 'Beam Current [uA]', 'Filament Current [A]',
        'Penning PeG1', 'Column PiG1', 'Gun PiG2', 'Detector PiG3',
        'Specimen PiG4', 'RT1 PiG5', 'Bias coarse', 'Bias fine',
        'Stage X [um]', 'Stage Y [um]', 'Stage Z [um]', 'Stage TX [deg]'
    ]

    def __init__(self):
        self.base_dir = r"C:\Xcalibur\log\SynergyED_DiagnosticData"
        if not os.path.exists(self.base_dir):
            self.base_dir = os.getcwd()

    def parse_folder_name(self, folder_name):
        """Parse datetime from folder name in any supported format."""
        # Format 1: 2025-07-01_08-23-56_EDAutoLog
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", folder_name)
        if m:
            try:
                return datetime(
                    int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    int(m.group(4)), int(m.group(5)), int(m.group(6))
                )
            except ValueError:
                return None
        # Format 2: Mon-Jun-30-2025_EDAutoLog
        m = re.match(r"^(\w{3})-(\w{3})-(\d{2})-(\d{4})", folder_name)
        if m:
            try:
                return datetime.strptime("-".join(m.groups()), "%a-%b-%d-%Y")
            except ValueError:
                return None
        # Format 3: Mon-Jun-23-08-56-11-2025_EDAutoLog
        m = re.match(r"^(\w{3})-(\w{3})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{4})", folder_name)
        if m:
            try:
                return datetime.strptime("-".join(m.groups()), "%a-%b-%d-%H-%M-%S-%Y")
            except ValueError:
                return None
        return None

    def read_log_file(self, file_path):
        """Read and parse an EDAutoLog.dat file"""
        try:
            # Read the file and get header lines
            with open(file_path, 'r') as f:
                # Skip the first line with [Jeol_MicroED 2]
                f.readline()
                # Read the header line with column names
                header_line = f.readline().strip()

            # Get column names from header line, removing empty strings
            columns = [col.strip() for col in header_line.split('\t') if col.strip()]

            # Read the data using the extracted column names
            df = pd.read_csv(file_path, sep='\t', skiprows=2, names=columns, index_col=False)

            # Convert timestamp column to datetime
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)

            # Convert numeric columns and handle any whitespace
            for col in self.NUMERIC_COLUMNS:
                if col in df.columns:
                    # Remove any leading/trailing whitespace if column is string type
                    if df[col].dtype == 'object':
                        df[col] = df[col].str.strip()
                    # Convert to numeric, handling any conversion errors
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
            return None

    def get_log_files(self, start_date=None, end_date=None):
        """Get all log files within the specified date range"""
        log_files = []
        
        try:
            if not os.path.exists(self.base_dir):
                print(f"Warning: Base directory {self.base_dir} not found.")
                return log_files
            
            # Look for files in both old and new formats
            for item_name in os.listdir(self.base_dir):
                file_date = None
                file_path = None
                
                # Check for old format (folder with EDAutoLog.dat inside)
                if item_name.endswith('_EDAutoLog'):
                    old_log_file = os.path.join(self.base_dir, item_name, 'EDAutoLog.dat')
                    if os.path.exists(old_log_file):
                        file_date = self.parse_folder_name(item_name)
                        file_path = old_log_file
                
                # Check for new format (direct .dat file)
                elif item_name.endswith('_Jeol_MicroED.dat'):
                    new_log_file = os.path.join(self.base_dir, item_name)
                    if os.path.exists(new_log_file):
                        file_date = self.parse_folder_name(item_name)
                        file_path = new_log_file
                
                # If we found a valid file and could parse its date
                if file_date and file_path:
                    # Apply date range filters
                    if start_date and file_date.date() < start_date:
                        continue
                    if end_date and file_date.date() > end_date:
                        continue
                    
                    log_files.append({
                        'path': file_path,
                        'date': file_date,
                        'folder_name': os.path.basename(file_path)
                    })
        
        except Exception as e:
            print(f"Error scanning log directory: {str(e)}")
        
        return sorted(log_files, key=lambda x: x['date'])

    def process_multiple_files(self, file_paths):
        """Process multiple log files and combine their data"""
        combined_data = {}
        
        for file_path in file_paths:
            df = self.read_log_file(file_path)
            if df is None:
                continue
                
            # Initialize combined data on first file
            if not combined_data:
                for col in df.columns:
                    combined_data[col] = df[col]
            else:
                # Add data from subsequent files
                for col in df.columns:
                    if col in combined_data:
                        combined_data[col] = pd.concat([combined_data[col], df[col]])
        
        return combined_data if combined_data else None
