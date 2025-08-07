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

    def extract_file_date_range(self, file_path):
        """Extract the date range from file contents"""
        try:
            df = self.read_log_file(file_path)
            if df is not None and not df.empty:
                return {
                    'start': df.index[0],
                    'end': df.index[-1],
                    'representative': df.index[0]  # Use first timestamp as representative
                }
        except Exception as e:
            print(f"Error extracting dates from {file_path}: {str(e)}")
        return None

    def get_log_files(self, start_date=None, end_date=None):
        """Get all log files within the specified date range"""
        log_files = []
        
        try:
            if not os.path.exists(self.base_dir):
                print(f"Warning: Base directory {self.base_dir} not found.")
                return log_files
            
            # Recursively look for log files in any folder structure
            for root, _, files in os.walk(self.base_dir):
                for filename in files:
                    file_path = None
                    file_date = None
                    
                    # Check for any potential log file
                    if filename == 'EDAutoLog.dat' or filename.endswith('_Jeol_MicroED.dat'):
                        file_path = os.path.join(root, filename)
                        
                        # Try to get date from folder name first
                        folder_name = os.path.basename(os.path.dirname(file_path))
                        file_date = self.parse_folder_name(folder_name)
                        
                        # If folder name parsing fails, extract dates from file contents
                        if not file_date:
                            date_info = self.extract_file_date_range(file_path)
                            if date_info:
                                file_date = date_info['representative']
                    
                    # If we found a valid file and could get its date
                    if file_path and file_date:
                        # Apply date range filters
                        if start_date and file_date.date() < start_date:
                            continue
                        if end_date and file_date.date() > end_date:
                            continue
                        
                        log_files.append({
                            'path': file_path,
                            'date': file_date,
                            'folder_name': os.path.relpath(os.path.dirname(file_path), self.base_dir)
                        })
        
        except Exception as e:
            print(f"Error scanning log directory: {str(e)}")
        
        # Sort files by date
        sorted_files = sorted(log_files, key=lambda x: x['date'])
        
        # Update the display names to be more informative
        for file_info in sorted_files:
            date_str = file_info['date'].strftime('%Y-%m-%d %H:%M:%S')
            rel_path = file_info['folder_name']
            file_info['folder_name'] = f"{date_str} - {rel_path}"
        
        return sorted_files

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
