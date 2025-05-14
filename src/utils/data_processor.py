import os
import pandas as pd
from datetime import datetime

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
        """Parse datetime from folder name in either format:
        Old format: Mon-May-12-12-48-37-2025_EDAutoLog
        New format: 2025_05_14_08h19m10_Jeol_MicroED.dat
        """
        try:
            # Try new format first
            if folder_name.count('_') >= 3 and 'h' in folder_name and 'm' in folder_name:
                return self.parse_new_format(folder_name)
            
            # Try old format
            date_part = folder_name.split('_')[0]
            return datetime.strptime(date_part, '%a-%b-%d-%H-%M-%S-%Y')
        except (ValueError, IndexError):
            return None
            
    def parse_new_format(self, filename):
        """Parse datetime from new format: 2025_05_14_08h19m10_Jeol_MicroED.dat"""
        try:
            # Split the filename and take the first 4 parts (date and time)
            parts = filename.split('_')[:4]
            if len(parts) < 4:
                return None
                
            year, month, day = map(int, parts[:3])
            time_part = parts[3]
            
            # Parse time part (format: 08h19m10)
            hour = int(time_part.split('h')[0])
            minute = int(time_part.split('h')[1].split('m')[0])
            second = int(time_part.split('m')[1].split('_')[0])
            
            return datetime(year, month, day, hour, minute, second)
        except (ValueError, IndexError):
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
