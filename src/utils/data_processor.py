import os
import pandas as pd
from datetime import datetime
import re
import csv

class LogDataProcessor:
    COLUMNS = [
        'time', 'HT [kV]', 'HT Setpoint [kV]', 'Beam Current [uA]', 'Filament Current [A]',
        'Penning PeG1', 'Column PiG1', 'Gun PiG2', 'Detector PiG3',
        'Specimen PiG4', 'RT1 PiG5', 'Bias coarse', 'Bias fine',
        'Stage X [um]', 'Stage Y [um]', 'Stage Z [um]', 'Stage TX [deg]', 'Stage TY [deg]'
    ]
    
    NUMERIC_COLUMNS = [
        'HT [kV]', 'HT Setpoint [kV]', 'Beam Current [uA]', 'Filament Current [A]',
        'Penning PeG1', 'Column PiG1', 'Gun PiG2', 'Detector PiG3',
        'Specimen PiG4', 'RT1 PiG5', 'Bias coarse', 'Bias fine',
        'Stage X [um]', 'Stage Y [um]', 'Stage Z [um]', 'Stage TX [deg]', 'Stage TY [deg]'
    ]

    def __init__(self):
        local_appdata = os.environ.get('LOCALAPPDATA')
        dynamic_jeol_log_dir = None
        if local_appdata:
            dynamic_jeol_log_dir = os.path.join(local_appdata, 'JEOL_logger', 'logs')

        preferred_dirs = [
            dynamic_jeol_log_dir,
            r"C:\Xcalibur\log\SynergyED_DiagnosticData",
        ]
        self.base_dir = next((path for path in preferred_dirs if path and os.path.exists(path)), os.getcwd())
        
        # Cache for file metadata (time ranges and modification times)
        # Format: {file_path: {'start': datetime, 'end': datetime, 'mtime': float}}
        self.file_metadata_cache = {}

        # Header mapping from JEOL CSV logger columns to the plotter's internal schema.
        self.csv_column_map = {
            'HT actual': 'HT [kV]',
            'Emission current': 'Beam Current [uA]',
            'Filament current': 'Filament Current [A]',
            'PiG1 Gun': 'Gun PiG2',
            'PiG2 Column': 'Column PiG1',
            'PiG3 Specimen': 'Specimen PiG4',
            'PiG4 Detector': 'Detector PiG3',
            'PiG5 RT1': 'RT1 PiG5',
            'Penning': 'Penning PeG1',
            'Bias current': 'Bias coarse',
            'Stage X': 'Stage X [um]',
            'Stage Y': 'Stage Y [um]',
            'Stage Z': 'Stage Z [um]',
            'Stage TX': 'Stage TX [deg]',
            'Stage TY': 'Stage TY [deg]',
            'HT setpoint': 'HT Setpoint [kV]'
        }

    def _is_supported_log_filename(self, filename):
        """Return True if filename looks like a supported SynergyED/JEOL logger file."""
        lower_name = filename.lower()
        if lower_name == 'edautolog.dat':
            return True
        if lower_name.endswith('_jeol_microed.dat'):
            return True
        if lower_name.endswith('.csv'):
            return True
        return False

    def _detect_file_format(self, file_path):
        """Detect known file formats for lightweight parsing decisions."""
        lower_path = file_path.lower()
        if lower_path.endswith('.csv'):
            return 'jeol_csv'

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
                if first_line.startswith('['):
                    return 'legacy_dat'
                if ',' in first_line:
                    return 'jeol_csv'
                if '\t' in first_line:
                    return 'legacy_dat'
        except Exception:
            pass

        return 'unknown'

    def _split_row(self, line, delimiter):
        """Split a row into cells, trimming whitespace around each cell."""
        row = next(csv.reader([line], delimiter=delimiter, skipinitialspace=True), [])
        return [cell.strip() for cell in row]

    def _get_timestamp_cell_index(self, file_path, file_format):
        """Get timestamp column index for quick first/last timestamp reads."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if file_format == 'legacy_dat':
                    f.readline()  # [Jeol_MicroED 2]
                    header_line = f.readline().strip()
                    columns = self._split_row(header_line, '\t')
                    return columns.index('time') if 'time' in columns else 0

                # Assume csv-like header for JEOL logger or unknown csvs
                header_line = f.readline().strip()
                columns = self._split_row(header_line, ',')

                if 'timestamp_utc' in columns:
                    return columns.index('timestamp_utc')
                if 'time' in columns:
                    return columns.index('time')
                return 0
        except Exception:
            return 0

    def _parse_timestamp_from_line(self, line, delimiter, timestamp_index):
        """Parse timestamp from a data row using a known delimiter/index."""
        if not line:
            return None

        cells = self._split_row(line, delimiter)
        if not cells:
            return None

        if timestamp_index >= len(cells):
            return None

        timestamp_str = cells[timestamp_index].strip()
        if not timestamp_str:
            return None

        try:
            return pd.to_datetime(timestamp_str)
        except Exception:
            return None

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

    def _read_first_timestamp(self, file_path):
        """
        Read only the first timestamp without loading the full file.
        Much faster than reading entire file.
        """
        try:
            file_format = self._detect_file_format(file_path)
            delimiter = '\t' if file_format == 'legacy_dat' else ','
            timestamp_index = self._get_timestamp_cell_index(file_path, file_format)

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if file_format == 'legacy_dat':
                    f.readline()  # Skip [Jeol_MicroED 2]
                    f.readline()  # Skip header line
                else:
                    f.readline()  # Skip csv header line

                for line in f:
                    parsed = self._parse_timestamp_from_line(line.strip(), delimiter, timestamp_index)
                    if parsed is not None:
                        return parsed
        except Exception as e:
            print(f"Error reading first timestamp from {file_path}: {str(e)}")
        return None

    def _read_last_timestamp(self, file_path):
        """
        Read only the last timestamp without loading the full file.
        Reads last ~2KB to find the last line. Much faster than reading entire file.
        """
        try:
            file_format = self._detect_file_format(file_path)
            delimiter = '\t' if file_format == 'legacy_dat' else ','
            timestamp_index = self._get_timestamp_cell_index(file_path, file_format)

            with open(file_path, 'rb') as f:
                # Go to end of file
                f.seek(0, 2)
                file_size = f.tell()
                
                # Read last ~2KB to find last line
                read_size = min(2048, file_size)
                f.seek(max(0, file_size - read_size))
                last_chunk = f.read().decode('utf-8', errors='ignore')
                
                # Split into lines and get the last non-empty line
                lines = last_chunk.splitlines()
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith('['):
                        continue

                    # Skip likely header rows
                    lower_line = line.lower()
                    if 'timestamp_utc' in lower_line or lower_line.startswith('time'):
                        continue

                    parsed = self._parse_timestamp_from_line(line, delimiter, timestamp_index)
                    if parsed is not None:
                        return parsed
        except Exception as e:
            print(f"Error reading last timestamp from {file_path}: {str(e)}")
        return None

    def get_file_time_range(self, file_path):
        """
        Get the time range (start, end) for a file using cache when possible.
        Only reads the file if it's not cached or has been modified.
        
        Returns:
            tuple: (start_datetime, end_datetime) or (None, None) if error
        """
        try:
            # Get file modification time
            mtime = os.path.getmtime(file_path)
            
            # Check if we have a valid cached entry
            if file_path in self.file_metadata_cache:
                cached = self.file_metadata_cache[file_path]
                if cached['mtime'] == mtime:
                    # File hasn't changed, use cached values
                    return cached['start'], cached['end']
            
            # Need to read the file (not cached or modified)
            start_time = self._read_first_timestamp(file_path)
            end_time = self._read_last_timestamp(file_path)
            
            if start_time is not None and end_time is not None:
                # Update cache
                self.file_metadata_cache[file_path] = {
                    'start': start_time,
                    'end': end_time,
                    'mtime': mtime
                }
                return start_time, end_time
        except Exception as e:
            print(f"Error getting time range for {file_path}: {str(e)}")
        
        return None, None

    def read_log_file(self, file_path):
        """Read and parse an EDAutoLog.dat file"""
        try:
            file_format = self._detect_file_format(file_path)

            if file_format == 'legacy_dat':
                # Read the file and get header lines
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Skip the first line with [Jeol_MicroED 2]
                    f.readline()
                    # Read the header line with column names
                    header_line = f.readline().strip()

                # Get column names from header line, removing empty strings
                columns = [col.strip() for col in header_line.split('\t') if col.strip()]

                # Read the data using the extracted column names
                df = pd.read_csv(file_path, sep='\t', skiprows=2, names=columns, index_col=False)
            else:
                # JEOL logger CSV format
                df = pd.read_csv(file_path, sep=',', skipinitialspace=True, index_col=False)
                df.columns = [str(col).strip() for col in df.columns]

                # Rename timestamp and mapped telemetry columns to internal schema
                if 'timestamp_utc' in df.columns:
                    df.rename(columns={'timestamp_utc': 'time'}, inplace=True)

                rename_map = {
                    source: target for source, target in self.csv_column_map.items() if source in df.columns
                }
                if rename_map:
                    df.rename(columns=rename_map, inplace=True)

                # Ensure expected columns exist even if source logger omitted some fields
                for required_column in self.COLUMNS:
                    if required_column == 'time':
                        continue
                    if required_column not in df.columns:
                        df[required_column] = pd.NA

                # Convert HT columns from volts to kV when needed
                for ht_col in ('HT [kV]', 'HT Setpoint [kV]'):
                    if ht_col in df.columns:
                        ht_numeric = pd.to_numeric(df[ht_col], errors='coerce')
                        max_abs = ht_numeric.abs().max(skipna=True)
                        if max_abs is not None and not pd.isna(max_abs) and max_abs > 1000:
                            df[ht_col] = ht_numeric / 1000.0

                # Keep only internal columns in a stable order
                ordered_cols = [col for col in self.COLUMNS if col in df.columns]
                df = df[['time'] + [col for col in ordered_cols if col != 'time']]

            # Convert timestamp column to datetime
            df['time'] = pd.to_datetime(df['time'], errors='coerce')
            df = df.dropna(subset=['time'])
            df.set_index('time', inplace=True)

            # Convert numeric columns and handle any whitespace
            for col in self.NUMERIC_COLUMNS:
                if col in df.columns:
                    # Remove any leading/trailing whitespace if column is string type
                    if df[col].dtype == 'object':
                        df[col] = df[col].str.strip()
                    # Convert to numeric, handling any conversion errors
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Bias fine does not exist in JEOL logger files; populate with NaN if absent.
            if 'Bias fine' not in df.columns:
                df['Bias fine'] = pd.NA

            return df

        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
            return None

    def extract_file_date_range(self, file_path):
        """
        Extract the date range from file contents.
        Now uses fast timestamp reading instead of loading entire file.
        """
        try:
            start_time, end_time = self.get_file_time_range(file_path)
            if start_time is not None and end_time is not None:
                return {
                    'start': start_time,
                    'end': end_time,
                    'representative': start_time  # Use first timestamp as representative
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

                    # Check for any supported log file
                    if self._is_supported_log_filename(filename):
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

    def process_multiple_files(self, file_paths, start_datetime=None, end_datetime=None):
        """Process multiple log files and combine their data, optionally filtering by datetime range"""
        combined_data = {}
        
        for file_path in file_paths:
            df = self.read_log_file(file_path)
            if df is None:
                continue
                
            # Apply datetime filtering if specified
            if start_datetime is not None or end_datetime is not None:
                if start_datetime is not None:
                    df = df[df.index >= start_datetime]
                if end_datetime is not None:
                    df = df[df.index <= end_datetime]
                
                # Skip file if no data remains after filtering
                if df.empty:
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
        
        # If we have combined data, sort by index (datetime) to ensure proper chronological order
        if combined_data:
            # Create a DataFrame from the combined data and sort by index
            result_df = pd.DataFrame(combined_data)
            result_df = result_df.sort_index()
            
            # Convert back to the expected dictionary format with Series
            combined_data = {col: result_df[col] for col in result_df.columns}
        
        return combined_data if combined_data else None

    def read_file_with_time_filter(self, file_path, start_datetime=None, end_datetime=None):
        """Read a log file and apply time filtering. Useful for reading constantly updating files."""
        df = self.read_log_file(file_path)
        if df is None or df.empty:
            return None
        
        # Apply datetime filtering if specified
        if start_datetime is not None:
            df = df[df.index >= start_datetime]
        if end_datetime is not None:
            df = df[df.index <= end_datetime]
        
        return df if not df.empty else None

    def process_multiple_files_live(self, file_paths, start_datetime=None, end_datetime=None, 
                                     force_reread_latest=True):
        """
        Process multiple log files with special handling for live updates.
        
        Args:
            file_paths: List of file paths to process
            start_datetime: Start of time range filter
            end_datetime: End of time range filter
            force_reread_latest: If True, always re-read the most recent file to catch new data
        
        Returns:
            Dictionary of combined data with time filtering applied
        """
        if not file_paths:
            return None
        
        combined_data = {}
        
        # Sort files by path to ensure consistent ordering
        sorted_paths = sorted(file_paths)
        
        for i, file_path in enumerate(sorted_paths):
            is_latest = (i == len(sorted_paths) - 1)
            
            # Always re-read the latest file in live mode to catch new data
            if is_latest and force_reread_latest:
                df = self.read_file_with_time_filter(file_path, start_datetime, end_datetime)
            else:
                df = self.read_file_with_time_filter(file_path, start_datetime, end_datetime)
            
            if df is None or df.empty:
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
        
        # If we have combined data, sort by index (datetime) to ensure proper chronological order
        if combined_data:
            # Create a DataFrame from the combined data and sort by index
            result_df = pd.DataFrame(combined_data)
            result_df = result_df.sort_index()
            
            # Remove any duplicate timestamps (keep last occurrence)
            result_df = result_df[~result_df.index.duplicated(keep='last')]
            
            # Convert back to the expected dictionary format with Series
            combined_data = {col: result_df[col] for col in result_df.columns}
        
        return combined_data if combined_data else None
