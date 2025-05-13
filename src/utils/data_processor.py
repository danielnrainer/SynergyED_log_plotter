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
        """Parse datetime from folder name format: Mon-May-12-12-48-37-2025_EDAutoLog"""
        try:
            date_part = folder_name.split('_')[0]
            return datetime.strptime(date_part, '%a-%b-%d-%H-%M-%S-%Y')
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
            
            for folder_name in os.listdir(self.base_dir):
                if not folder_name.endswith('_EDAutoLog'):
                    continue
                    
                folder_date = self.parse_folder_name(folder_name)
                if folder_date is None:
                    continue
                    
                if start_date and folder_date.date() < start_date:
                    continue
                if end_date and folder_date.date() > end_date:
                    continue
                
                log_file = os.path.join(self.base_dir, folder_name, 'EDAutoLog.dat')
                if os.path.exists(log_file):
                    log_files.append({
                        'path': log_file,
                        'date': folder_date,
                        'folder_name': folder_name
                    })
        
        except Exception as e:
            print(f"Error scanning log directory: {str(e)}")
        
        return sorted(log_files, key=lambda x: x['date'])

    def process_multiple_files(self, file_paths):
        """Process multiple log files and combine their data"""
        dfs = []
        for file_path in file_paths:
            df = self.read_log_file(file_path)
            if df is not None:
                dfs.append(df)
        
        if not dfs:
            return None
            
        # Combine all dataframes
        combined_df = pd.concat(dfs, sort=True)
        # Sort by timestamp
        combined_df.sort_index(inplace=True)
        return combined_df
