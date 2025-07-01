from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel,
                             QListWidget, QSplitter, QDateEdit,
                             QComboBox, QCheckBox, QGroupBox,
                             QFileDialog)
from PyQt6.QtCore import Qt, QDate, QTimer
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
from utils.data_processor import LogDataProcessor

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SynergyED Log Plotter")
        self.setGeometry(100, 100, 1400, 800)
        
        # Create the central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)
        
        # Initialize the data processor
        self.data_processor = LogDataProcessor()
        self.available_files = []
        self.current_data = None
        
        # Timer for live plotting
        self.live_plot_timer = QTimer(self)
        self.live_plot_timer.timeout.connect(self.update_live_plot)
        self.live_plot_enabled = False
        
        # Create panels
        self.create_left_panel()
        self.create_right_panel()
        
        # Split the panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([400, 1000])  # Set initial split sizes
        self.layout.addWidget(splitter)
        
    def create_left_panel(self):
        self.left_panel = QWidget()
        layout = QVBoxLayout(self.left_panel)
        
        # Directory selection
        dir_group = QGroupBox("Log Directory")
        dir_layout = QVBoxLayout(dir_group)
        
        self.dir_label = QLabel(self.data_processor.base_dir)
        self.dir_label.setWordWrap(True)
        dir_layout.addWidget(self.dir_label)
        
        change_dir_btn = QPushButton("Change Directory")
        change_dir_btn.clicked.connect(self.change_directory)
        dir_layout.addWidget(change_dir_btn)
        
        layout.addWidget(dir_group)
        
        # Date selection group
        date_group = QGroupBox("Date Selection")
        date_layout = QVBoxLayout(date_group)
        
        date_widget = QWidget()
        date_input_layout = QHBoxLayout(date_widget)
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        date_input_layout.addWidget(QLabel("Start:"))
        date_input_layout.addWidget(self.start_date)
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        date_input_layout.addWidget(QLabel("End:"))
        date_input_layout.addWidget(self.end_date)
        
        date_layout.addWidget(date_widget)
        
        refresh_btn = QPushButton("Refresh Files")
        refresh_btn.clicked.connect(self.refresh_file_list)
        date_layout.addWidget(refresh_btn)
        
        layout.addWidget(date_group)
        
        # File selection group
        file_group = QGroupBox("Available Log Files")
        file_layout = QVBoxLayout(file_group)
        
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        file_layout.addWidget(self.file_list)
        
        layout.addWidget(file_group)
        
        # Plot settings group
        settings_group = QGroupBox("Plot Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Parameter selection
        self.param_list = QListWidget()
        self.param_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.param_list.addItems([
            'HT [kV]', 'Beam Current [uA]', 'Filament Current [A]',
            'Penning PeG1', 'Column PiG1', 'Gun PiG2', 'Detector PiG3',
            'Specimen PiG4', 'RT1 PiG5', 'Bias coarse', 'Bias fine',
            'Stage X [um]', 'Stage Y [um]', 'Stage Z [um]', 'Stage TX [deg]'
        ])
        settings_layout.addWidget(QLabel("Parameters to Plot (select multiple):"))
        settings_layout.addWidget(self.param_list)
        
        # Plot type
        self.plot_type = QComboBox()
        self.plot_type.addItems(["Line Plot", "Scatter Plot", "Both"])
        settings_layout.addWidget(QLabel("Plot Type:"))
        settings_layout.addWidget(self.plot_type)
        
        # Additional options
        self.show_grid = QCheckBox("Show Grid")
        self.show_grid.setChecked(True)
        settings_layout.addWidget(self.show_grid)
        
        self.show_legend = QCheckBox("Show Legend")
        self.show_legend.setChecked(True)
        settings_layout.addWidget(self.show_legend)
        
        layout.addWidget(settings_group)
        
        # Plot button
        plot_button = QPushButton("Plot Selected")
        plot_button.clicked.connect(self.plot_selected)
        layout.addWidget(plot_button)
        
        # Add statistics checkbox
        self.show_stats = QCheckBox("Show Statistics")
        self.show_stats.setChecked(False)
        layout.addWidget(self.show_stats)
        
        # Add Live Plot toggle button
        self.live_plot_btn = QPushButton("Enable Live Plot")
        self.live_plot_btn.setCheckable(True)
        self.live_plot_btn.setChecked(False)
        self.live_plot_btn.clicked.connect(self.toggle_live_plot)
        layout.addWidget(self.live_plot_btn)
        
        # Add stretch to push everything up
        layout.addStretch()
        
    def create_right_panel(self):
        self.right_panel = QWidget()
        layout = QVBoxLayout(self.right_panel)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        # Add statistics display
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)
        
    def refresh_file_list(self):
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        
        self.available_files = self.data_processor.get_log_files(start_date, end_date)
        
        self.file_list.clear()
        for file_info in self.available_files:
            # Format the date nicely
            date_str = file_info['date'].strftime('%Y-%m-%d %H:%M:%S')
            # Create display text with date and filename
            display_text = f"{date_str} - {file_info['folder_name']}"
            self.file_list.addItem(display_text)    
    
    def get_axis_label(self, param):
        """Return formatted axis label with units"""
        # The units are already in square brackets in the parameter name
        return param
    
    def plot_selected(self):
        selected_indices = self.file_list.selectedIndexes()
        if not selected_indices:
            return
            
        # Use the original file paths from available_files
        selected_files = [self.available_files[idx.row()]['path'] for idx in selected_indices]
        
        # Process the data
        self.current_data = self.data_processor.process_multiple_files(selected_files)
        if self.current_data is None:
            return
            
        # Get selected parameters
        selected_params = [item.text() for item in self.param_list.selectedItems()]
        if not selected_params:
            return
        
        # Get the selected plot type
        plot_type = self.plot_type.currentText()
        
        # Clear the current figure
        self.figure.clear()
        
        # Create a single plot for all parameters with extra space on right for multiple axes
        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(right=0.85)  # Adjust for multiple y-axes
        
        # Get default color cycle from matplotlib
        prop_cycle = plt.rcParams['axes.prop_cycle']
        colors = prop_cycle.by_key()['color']
        
        # Create the first y-axis
        main_ax = ax
        main_param = selected_params[0]
        axes = [main_ax]  # Keep track of all axes for grid settings
        param_data = {}  # Store data ranges for each parameter
        
        # Plot first parameter on main axis
        color = colors[0]
        for j, file_path in enumerate(selected_files):
            df = self.data_processor.read_log_file(file_path)
            if df is not None:
                label = f"{main_param} - Dataset {j+1}"
                if plot_type in ["Line Plot", "Both"]:
                    main_ax.plot(df.index, df[main_param], '-', color=color, label=label if self.show_legend.isChecked() else "")
                if plot_type in ["Scatter Plot", "Both"]:
                    main_ax.scatter(df.index, df[main_param], color=color, alpha=0.5, label=label if self.show_legend.isChecked() else "")
                # Store data range
                if main_param not in param_data:
                    param_data[main_param] = {'min': float('inf'), 'max': float('-inf')}
                param_data[main_param]['min'] = min(param_data[main_param]['min'], df[main_param].min())
                param_data[main_param]['max'] = max(param_data[main_param]['max'], df[main_param].max())
        
        # Set main axis properties
        main_ax.set_xlabel("Time")
        main_ax.set_ylabel(self.get_axis_label(main_param), color=color)
        main_ax.tick_params(axis='y', labelcolor=color)
        
        # Add padding to data range
        y_pad = (param_data[main_param]['max'] - param_data[main_param]['min']) * 0.1
        main_ax.set_ylim(param_data[main_param]['min'] - y_pad, param_data[main_param]['max'] + y_pad)
        
        # Create additional axes for other parameters
        for i, param in enumerate(selected_params[1:], 1):
            # Create new axis sharing x-axis with main plot
            new_ax = main_ax.twinx()
            
            # If this is not the first additional axis, offset it to the right
            if i > 1:
                # Calculate offset based on number of parameters
                offset = (i - 1) * 60  # Offset in points
                new_ax.spines['right'].set_position(('outward', offset))
            
            color = colors[i % len(colors)]
            
            # Plot the parameter on the new axis
            for j, file_path in enumerate(selected_files):
                df = self.data_processor.read_log_file(file_path)
                if df is not None:
                    label = f"{param} - Dataset {j+1}"
                    if plot_type in ["Line Plot", "Both"]:
                        new_ax.plot(df.index, df[param], '-', color=color, label=label if self.show_legend.isChecked() else "")
                    if plot_type in ["Scatter Plot", "Both"]:
                        new_ax.scatter(df.index, df[param], color=color, alpha=0.5, label=label if self.show_legend.isChecked() else "")
                    # Store data range
                    if param not in param_data:
                        param_data[param] = {'min': float('inf'), 'max': float('-inf')}
                    param_data[param]['min'] = min(param_data[param]['min'], df[param].min())
                    param_data[param]['max'] = max(param_data[param]['max'], df[param].max())
            
            # Set axis properties
            new_ax.set_ylabel(self.get_axis_label(param), color=color)
            new_ax.tick_params(axis='y', labelcolor=color)
            new_ax.spines['right'].set_color(color)
            
            # Add padding to data range
            y_pad = (param_data[param]['max'] - param_data[param]['min']) * 0.1
            new_ax.set_ylim(param_data[param]['min'] - y_pad, param_data[param]['max'] + y_pad)
            
            # Set number of ticks based on axis height
            new_ax.yaxis.set_major_locator(plt.MaxNLocator(6))
        
        # Set common x-axis label
        ax.set_xlabel("Time")
        
        # Set grid for all axes
        for a in axes:
            a.grid(self.show_grid.isChecked())
        
        # Add legend outside the plot area
        if self.show_legend.isChecked():
            # Create a single legend for all axes
            handles, labels = ax.get_legend_handles_labels()
            for a in axes[1:]:
                h, l = a.get_legend_handles_labels()
                handles.extend(h)
                labels.extend(l)
            # Remove duplicate labels
            by_label = dict(zip(labels, handles))
            ax.legend(by_label.values(), by_label.keys(), loc='upper left', bbox_to_anchor=(1, 1))
        
        # Draw the updated figure
        self.canvas.draw()
        
        # Show statistics if enabled
        if self.show_stats.isChecked():
            self.show_statistics(param_data)
        else:
            self.stats_label.setText("")
    
    def show_statistics(self, param_data):
        """Display statistics of the plotted data"""
        stats_text = "<b>Data Statistics:</b><br>"
        for param, data in param_data.items():
            stats_text += f"{param}: Min = {data['min']:.2f}, Max = {data['max']:.2f}<br>"
        self.stats_label.setText(stats_text)
    
    def change_directory(self):
        new_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Log Files Directory",
            self.data_processor.base_dir,
            QFileDialog.Option.ShowDirsOnly
        )
        
        if new_dir:
            self.data_processor.base_dir = new_dir
            self.dir_label.setText(new_dir)
            self.refresh_file_list()  # Refresh the file list with the new directory
    
    def toggle_live_plot(self):
        if self.live_plot_btn.isChecked():
            self.live_plot_btn.setText("Disable Live Plot")
            self.live_plot_enabled = True
            self.live_plot_timer.start(2000)  # Update every 2 seconds
        else:
            self.live_plot_btn.setText("Enable Live Plot")
            self.live_plot_enabled = False
            self.live_plot_timer.stop()

    def update_live_plot(self):
        import os
        base_dir = self.data_processor.base_dir
        # Search for all EDAutoLog.dat files in subfolders and directly
        candidates = []
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file == 'EDAutoLog.dat':
                    candidates.append(os.path.join(root, file))
        if not candidates:
            return
        # Find the most recently modified file
        latest_file = max(candidates, key=os.path.getmtime)
        # Update the file list selection to this file
        self.file_list.clear()
        self.file_list.addItem(os.path.basename(latest_file))
        self.available_files = [{
            'path': latest_file,
            'date': self.data_processor.parse_folder_name(os.path.basename(os.path.dirname(latest_file))),
            'folder_name': os.path.basename(os.path.dirname(latest_file))
        }]
        # Select the only file
        self.file_list.setCurrentRow(0)
        # Plot with currently selected parameters (or default if none)
        if not self.param_list.selectedItems():
            # Select the first parameter by default
            self.param_list.setCurrentRow(0)
        self.plot_selected()
