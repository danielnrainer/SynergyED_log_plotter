from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel,
                             QListWidget, QSplitter, QDateEdit, QTimeEdit,
                             QComboBox, QCheckBox, QGroupBox, QLineEdit,
                             QFileDialog, QMessageBox, QFrame, QScrollArea,
                             QSizePolicy)
from .collapsible_box import QCollapsibleBox
import os
from datetime import datetime
from PyQt6.QtCore import Qt, QDate, QTime, QTimer
import matplotlib
matplotlib.use('QtAgg')  # Use Qt backend for matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
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
        self._layout = QHBoxLayout(self.central_widget)  # Use _layout to avoid conflict with layout() method
        
        # Initialize the data processor and storage
        self.data_processor = LogDataProcessor()
        self.available_files = []
        self.current_data = None
        self.param_widgets = {}
        
        # Initialize live plot variables
        self.live_plot_start_date = None
        self.live_plot_start_time = None
        
        # Timer for live plotting
        self.live_plot_timer = QTimer(self)
        self.live_plot_timer.timeout.connect(self.update_live_plot)
        self.live_plot_enabled = False
        
        # Initialize view limit storage
        self.stored_xlim = None
        self.stored_ylims = {}
        
        # Create panels
        self.create_left_panel()
        self.create_right_panel()
        
        # Split the panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([450, 1000])  # Set initial split sizes
        self._layout.addWidget(splitter)
        
    def create_left_panel(self):
        self.left_panel = QWidget()
        layout = QVBoxLayout(self.left_panel)
        
        # Directory selection
        dir_group = QCollapsibleBox("Log Directory")
        dir_layout = QVBoxLayout()
        
        self.dir_label = QLabel(self.data_processor.base_dir)
        self.dir_label.setWordWrap(True)
        dir_layout.addWidget(self.dir_label)
        
        change_dir_btn = QPushButton("Change Directory")
        change_dir_btn.clicked.connect(self.change_directory)
        dir_layout.addWidget(change_dir_btn)
        
        dir_group.setContentLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # File selection and date range group
        file_group = QCollapsibleBox("Log File Selection")
        file_layout = QVBoxLayout()
        
        # Date/Time Range section
        date_section = QWidget()
        date_section_layout = QVBoxLayout(date_section)
        
        # Start date/time
        start_layout = QHBoxLayout()
        start_date_layout = QVBoxLayout()
        start_date_label = QLabel("Start Date:")
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        start_date_layout.addWidget(start_date_label)
        start_date_layout.addWidget(self.start_date)
        start_layout.addLayout(start_date_layout)
        
        start_time_layout = QVBoxLayout()
        start_time_label = QLabel("Time:")
        self.start_time = QTimeEdit()
        self.start_time.setTime(QTime(0, 0))  # Set to midnight
        start_time_layout.addWidget(start_time_label)
        start_time_layout.addWidget(self.start_time)
        start_layout.addLayout(start_time_layout)
        date_section_layout.addLayout(start_layout)
        
        # End date/time
        end_layout = QHBoxLayout()
        end_date_layout = QVBoxLayout()
        end_date_label = QLabel("End Date:")
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        end_date_layout.addWidget(end_date_label)
        end_date_layout.addWidget(self.end_date)
        end_layout.addLayout(end_date_layout)
        
        end_time_layout = QVBoxLayout()
        end_time_label = QLabel("Time:")
        self.end_time = QTimeEdit()
        self.end_time.setTime(QTime.currentTime())  # Set to current time
        end_time_layout.addWidget(end_time_label)
        end_time_layout.addWidget(self.end_time)
        end_layout.addLayout(end_time_layout)
        date_section_layout.addLayout(end_layout)
        
        refresh_btn = QPushButton("Refresh Files")
        refresh_btn.clicked.connect(self.refresh_file_list)
        date_section_layout.addWidget(refresh_btn)
        
        # Create a layout for the file selection group
        file_layout = QVBoxLayout()
        file_layout.addWidget(date_section)
        
        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        file_layout.addWidget(separator)
        
        # Available files list
        file_layout.addWidget(QLabel("Available Files:"))
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        file_layout.addWidget(self.file_list)
        
        # Plot selected button
        plot_selected_btn = QPushButton("Plot Selected")
        plot_selected_btn.clicked.connect(lambda: self.plot_selected())  # Use lambda to ensure proper call
        file_layout.addWidget(plot_selected_btn)
        
        # Set the content layout for the group
        file_group.setContentLayout(file_layout)
        
        layout.addWidget(file_group)
        
        # Quick Plot Group (Direct date/time range plotting)
        quick_plot_group = QCollapsibleBox("Quick Plot by Time Range")
        quick_plot_layout = QVBoxLayout()
        
        # Quick plot date/time selectors
        quick_start_layout = QHBoxLayout()
        quick_start_date = QDateEdit()
        quick_start_date.setCalendarPopup(True)
        quick_start_date.setDate(QDate.currentDate().addDays(-1))  # Default to yesterday
        quick_start_time = QTimeEdit()
        quick_start_time.setTime(QTime(0, 0))  # Start at midnight
        quick_start_layout.addWidget(QLabel("Start:"))
        quick_start_layout.addWidget(quick_start_date)
        quick_start_layout.addWidget(quick_start_time)
        quick_plot_layout.addLayout(quick_start_layout)
        
        # Add end time controls
        quick_end_layout = QHBoxLayout()
        quick_end_date = QDateEdit()
        quick_end_date.setCalendarPopup(True)
        quick_end_date.setDate(QDate.currentDate())
        quick_end_time = QTimeEdit()
        quick_end_time.setTime(QTime.currentTime())
        quick_end_layout.addWidget(QLabel("End:"))
        quick_end_layout.addWidget(quick_end_date)
        quick_end_layout.addWidget(quick_end_time)
        quick_plot_layout.addLayout(quick_end_layout)
        
        # Quick plot button
        quick_plot_btn = QPushButton("Plot Time Range")
        quick_plot_btn.clicked.connect(lambda: self.plot_time_range(
            quick_start_date, quick_start_time,
            quick_end_date, quick_end_time
        ))
        quick_plot_layout.addWidget(quick_plot_btn)
        
        # Store references to quick plot widgets for live plotting
        self.quick_start_date = quick_start_date
        self.quick_start_time = quick_start_time
        
        # Set the content layout for the group
        quick_plot_group.setContentLayout(quick_plot_layout)
        
        layout.addWidget(quick_plot_group)
        
        # Plot settings group
        settings_group = QCollapsibleBox("Plot Settings")
        settings_layout = QVBoxLayout()
        
        # Add parameters with their controls in a scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        params_layout = QVBoxLayout(scroll_widget)
        
        params = [
            'HT [kV]', 'Beam Current [uA]', 'Filament Current [A]',
            'Penning PeG1', 'Column PiG1', 'Gun PiG2', 'Detector PiG3',
            'Specimen PiG4', 'RT1 PiG5', 'Bias coarse', 'Bias fine',
            'Stage X [um]', 'Stage Y [um]', 'Stage Z [um]', 'Stage TX [deg]'
        ]
        
        for param in params:
            # Create a more compact parameter widget
            param_widget = QWidget()
            param_layout = QHBoxLayout(param_widget)
            param_layout.setContentsMargins(2, 2, 2, 2)  # Reduce margins
            param_layout.setSpacing(4)  # Reduce spacing
            
            # Plot checkbox for parameter selection
            plot_checkbox = QCheckBox()
            plot_checkbox.setToolTip(f"Plot {param}")
            param_layout.addWidget(plot_checkbox)
            # Initialize widgets dict for this parameter
            self.param_widgets[param] = {'param_checkbox': plot_checkbox}
            
            # Parameter label
            param_label = QLabel(param)
            param_label.setMinimumWidth(120)  # Ensure minimum width for readability
            param_layout.addWidget(param_label)
            
            # Range inputs in a more compact layout
            range_widget = QWidget()
            range_layout = QHBoxLayout(range_widget)
            range_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
            range_layout.setSpacing(4)  # Reduce spacing
            range_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            
            # Auto-scale checkbox
            auto_scale = QCheckBox("Auto")
            auto_scale.setChecked(True)  # Default to auto-scaling
            range_layout.addWidget(auto_scale)
            
            # Minimal labels
            min_value = QLineEdit()
            min_value.setPlaceholderText("min")
            min_value.setMaximumWidth(60)
            min_value.setEnabled(False)  # Initially disabled when auto is checked
            range_layout.addWidget(QLabel("min:"))
            range_layout.addWidget(min_value)
            
            # Add widgets to the parameter's dictionary
            self.param_widgets[param].update({
                'auto_scale': auto_scale,
                'min_value': min_value,
            })
            
            max_value = QLineEdit()
            max_value.setPlaceholderText("max")
            max_value.setMaximumWidth(60)
            max_value.setEnabled(False)  # Initially disabled when auto is checked
            range_layout.addWidget(QLabel("max:"))
            range_layout.addWidget(max_value)
            
            param_layout.addWidget(range_widget)
            
            # Add max_value widget to the parameter's dictionary
            self.param_widgets[param].update({
                'max_value': max_value
            })
            
            # Set default ranges for specific parameters
            defaults = {
                'HT [kV]': (0, 200),
                'Beam Current [uA]': (0, 110),
                'Filament Current [A]': (0, 2.5),
                'Penning PeG1 [uA]': (0, 270),
                'Column PiG1 [uA]': (0, 270),
                'Gun PiG2 [uA]': (0, 270),
                'Detector PiG3 [uA]': (0, 270),
                'Specimen PiG4 [uA]': (0, 270),
                'RT1 PiG5 [uA]': (0, 270),
                # 'Bias coarse': (0, 1),
                # 'Bias fine': (0, 1),
                # 'Stage X [um]': (0, 500),
                # 'Stage Y [um]': (0, 500),
                # 'Stage Z [um]': (0, 250),
                # 'Stage TX [deg]': (-80, 80)
            }
            
            if param in defaults:
                min_val, max_val = defaults[param]
                min_value.setText(str(min_val))
                max_value.setText(str(max_val))
            
            # Connect auto-scale checkbox to enable/disable range inputs
            def make_toggle_handler(min_widget, max_widget):
                def toggle_handler(checked):
                    min_widget.setEnabled(not checked)
                    max_widget.setEnabled(not checked)
                return toggle_handler
            
            auto_scale.toggled.connect(make_toggle_handler(min_value, max_value))
            
            params_layout.addWidget(param_widget)
        
        # Add a small stretch at the bottom
        params_layout.addStretch()
        
        # Set up scroll area
        scroll_area.setWidget(scroll_widget)
        scroll_area.setMaximumHeight(400)  # Make it taller to show more parameters at once
        
        settings_layout.addWidget(scroll_area)
        
        # Plot type
        self.plot_type = QComboBox()
        self.plot_type.addItems(["Line Plot", "Scatter Plot", "Both"])
        plot_options_layout = QVBoxLayout()
        plot_options_layout.addWidget(QLabel("Plot Type:"))
        plot_options_layout.addWidget(self.plot_type)
        
        # Additional options
        self.show_grid = QCheckBox("Show Grid")
        self.show_grid.setChecked(True)
        plot_options_layout.addWidget(self.show_grid)
        
        settings_layout.addLayout(plot_options_layout)
        
        self.show_legend = QCheckBox("Show Legend")
        self.show_legend.setChecked(True)
        settings_layout.addWidget(self.show_legend)
        
        # Set the content layout for the settings group
        settings_group.setContentLayout(settings_layout)
        
        layout.addWidget(settings_group)
        
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
        
        # Placeholder for future additions to the right panel
        layout.addStretch()
        
    def refresh_file_list(self):
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        
        self.available_files = self.data_processor.get_log_files(start_date, end_date)
        
        self.file_list.clear()
        for file_info in self.available_files:
            # Create concise display text with just the time and unique folder part
            time_str = file_info['date'].strftime('%H:%M:%S')
            # Get the last part of the folder path (most relevant for identification)
            folder_name = os.path.basename(file_info['folder_name'])
            if folder_name.endswith('_EDAutoLog'):
                folder_name = folder_name[:-10]  # Remove '_EDAutoLog' suffix
            # display_text = f"{time_str} - {folder_name}"
            display_text = f"{time_str}"
            self.file_list.addItem(display_text)    
    
    def get_axis_label(self, param):
        """Return formatted axis label with units"""
        # The units are already in square brackets in the parameter name
        return param
    
    def plot_selected(self, files_to_plot=None):
        """
        Plot data from selected files or provided files
        
        Args:
            files_to_plot: Optional list of file paths to plot. If None, uses selected files from GUI.
        """
        # Reset current data to ensure fresh plotting
        self.current_data = None
        if files_to_plot is None:
            selected_indices = self.file_list.selectedIndexes()
            if not selected_indices:
                return
            files_to_plot = [self.available_files[idx.row()]['path'] for idx in selected_indices]
        
        if not files_to_plot:
            return
            
        # Process the data
        # self.current_data = self.data_processor.process_multiple_files(files_to_plot)
        
        # Process the data
        self.current_data = self.data_processor.process_multiple_files(files_to_plot)
        if self.current_data is None:
            return
            
        # Get selected parameters
        selected_params = [param for param, widgets in self.param_widgets.items() if widgets['param_checkbox'].isChecked()]
        if not selected_params:
            return
            
        # Group PiG parameters and other parameters
        pig_params = [param for param in selected_params if 'PiG' in param]
        other_params = [param for param in selected_params if 'PiG' not in param]
        
        # Reorder parameters to ensure PiG params are handled together
        selected_params = other_params + pig_params
            
        # Get the selected plot type
        plot_type = self.plot_type.currentText()
        
        # Clear the current figure
        self.figure.clear()
        
        # Create a single plot for all parameters with extra space on right for multiple axes
        ax = self.figure.add_subplot(111)        # Calculate margins based on number of additional y-axes
        num_extra_axes = len(selected_params) - 1  # Subtract 1 for main axis
        
        # Adjust right margin: start at 0.85 and reduce for each additional axis
        right_margin = 0.85 - (0.05 * num_extra_axes)
        
        # Adjust the subplot parameters to give specified padding for axes and labels
        self.figure.subplots_adjust(
            right=right_margin,  # Dynamic right margin for multiple y-axes
            bottom=0.2,         # Make room for x-axis labels and legend
            left=0.1,          # Left margin
            top=0.9            # Top margin
        )
        
        # Get default color cycle from matplotlib
        prop_cycle = plt.rcParams['axes.prop_cycle']
        colors = prop_cycle.by_key()['color']
        
        # Initial figure size
        base_width = 10  # Base width in inches
        self.figure.set_size_inches(base_width, self.figure.get_size_inches()[1])        # Create the first y-axis
        main_ax = ax
        main_param = selected_params[0]
        axes = [main_ax]  # Keep track of all axes for grid settings
        param_data = {}  # Store data ranges for each parameter
        
        # Set up PiG axis - either use main_ax if first param is PiG, or create new one
        if 'PiG' in main_param:
            pig_axis = main_ax
            main_ax.set_ylabel("PiG Current [uA]", color=colors[0])
            main_ax.tick_params(axis='y', labelcolor=colors[0])
        else:
            pig_axis = None
        
        # Plot first parameter on main axis
        color = colors[0]
        # Create a list to store all DataFrames for this parameter
        all_dfs = []
        for j, file_path in enumerate(files_to_plot):
            df = self.data_processor.read_log_file(file_path)
            if df is not None:
                all_dfs.append(df)
                
                # Create line plot without label - we'll add a single label later
                if plot_type in ["Line Plot", "Both"]:
                    main_ax.plot(df.index, df[main_param], '-', color=color)
                if plot_type in ["Scatter Plot", "Both"]:
                    main_ax.scatter(df.index, df[main_param], color=color, alpha=0.5)
                # Store data range
                if main_param not in param_data:
                    param_data[main_param] = {'min': float('inf'), 'max': float('-inf')}
                param_data[main_param]['min'] = min(param_data[main_param]['min'], df[main_param].min())
                param_data[main_param]['max'] = max(param_data[main_param]['max'], df[main_param].max())
        
        # Add a single line to the legend for this parameter
        if all_dfs and self.show_legend.isChecked():
            # Add one dummy line with the correct label and color
            if plot_type in ["Line Plot", "Both"]:
                main_ax.plot([], [], '-', color=color, label=main_param)
            if plot_type in ["Scatter Plot", "Both"]:
                main_ax.scatter([], [], color=color, alpha=0.5, label=main_param)
        
        # Set main axis properties
        main_ax.set_xlabel("Time")
        main_ax.set_ylabel(self.get_axis_label(main_param), color=color)
        main_ax.tick_params(axis='y', labelcolor=color)
        
        # Set y-axis limits based on user input or auto-scale
        if main_param in self.param_widgets:
            if not self.param_widgets[main_param]['auto_scale'].isChecked():
                try:
                    min_val = self.param_widgets[main_param]['min_value'].text()
                    max_val = self.param_widgets[main_param]['max_value'].text()
                    if min_val and max_val:  # Both values provided
                        main_ax.set_ylim(float(min_val), float(max_val))
                except (ValueError, TypeError):
                    # If conversion fails, fall back to auto-scaling
                    y_pad = (param_data[main_param]['max'] - param_data[main_param]['min']) * 0.1
                    main_ax.set_ylim(param_data[main_param]['min'] - y_pad, param_data[main_param]['max'] + y_pad)
            else:  # Auto-scale with padding
                y_pad = (param_data[main_param]['max'] - param_data[main_param]['min']) * 0.1
                main_ax.set_ylim(param_data[main_param]['min'] - y_pad, param_data[main_param]['max'] + y_pad)
        
        # Create additional axes for other parameters
        num_additional_axes = 0  # Counter for non-PiG additional axes
        
        for i, param in enumerate(selected_params[1:], 1):
            if 'PiG' in param:
                # If we don't have a PiG axis yet, create one (unless main_ax is already PiG)
                if pig_axis is None and pig_axis is not main_ax:
                    pig_axis = main_ax.twinx()
                    # Position PiG axis on the right if needed
                    if num_additional_axes > 0:
                        offset = num_additional_axes * 60
                        pig_axis.spines['right'].set_position(('outward', offset))
                    pig_axis.set_ylabel("PiG [uA]", color=colors[i % len(colors)])
                    pig_axis.set_ylim(0, 270)
                new_ax = pig_axis if pig_axis is not None else main_ax
            else:
                # Create new axis for non-PiG parameter
                new_ax = main_ax.twinx()
                num_additional_axes += 1
                
                # If this is not the first additional axis, offset it to the right
                if num_additional_axes > 1:
                    offset = (num_additional_axes - 1) * 60
                    new_ax.spines['right'].set_position(('outward', offset))
            
            color = colors[i % len(colors)]
            
            # Plot the parameter on the new axis
            for j, file_path in enumerate(files_to_plot):
                df = self.data_processor.read_log_file(file_path)
                if df is not None:
                    # Plot without label - we'll add a single label later
                    if plot_type in ["Line Plot", "Both"]:
                        new_ax.plot(df.index, df[param], '-', color=color)
                    if plot_type in ["Scatter Plot", "Both"]:
                        new_ax.scatter(df.index, df[param], color=color, alpha=0.5)
                    # Store data range
                    if param not in param_data:
                        param_data[param] = {'min': float('inf'), 'max': float('-inf')}
                    param_data[param]['min'] = min(param_data[param]['min'], df[param].min())
                    param_data[param]['max'] = max(param_data[param]['max'], df[param].max())
            
            # Add a single line to the legend for this parameter
            if self.show_legend.isChecked():
                # Add one dummy line with the correct label and color
                if plot_type in ["Line Plot", "Both"]:
                    new_ax.plot([], [], '-', color=color, label=param)
                if plot_type in ["Scatter Plot", "Both"]:
                    new_ax.scatter([], [], color=color, alpha=0.5, label=param)
            
            # Set axis properties
            if not 'PiG' in param:
                # For non-PiG parameters, set full axis properties
                new_ax.set_ylabel(self.get_axis_label(param), color=color)
            
            # Always set these properties regardless of parameter type
            new_ax.tick_params(axis='y', labelcolor=color)
            new_ax.spines['right'].set_color(color)
            
            # Set y-axis limits based on user input or auto-scale
            if param in self.param_widgets:
                if not self.param_widgets[param]['auto_scale'].isChecked():
                    try:
                        min_val = self.param_widgets[param]['min_value'].text()
                        max_val = self.param_widgets[param]['max_value'].text()
                        if min_val and max_val:  # Both values provided
                            new_ax.set_ylim(float(min_val), float(max_val))
                    except (ValueError, TypeError):
                        # If conversion fails, fall back to auto-scaling
                        y_pad = (param_data[param]['max'] - param_data[param]['min']) * 0.1
                        new_ax.set_ylim(param_data[param]['min'] - y_pad, param_data[param]['max'] + y_pad)
                else:  # Auto-scale with padding
                    y_pad = (param_data[param]['max'] - param_data[param]['min']) * 0.1
                    new_ax.set_ylim(param_data[param]['min'] - y_pad, param_data[param]['max'] + y_pad)
            
            # Set number of ticks based on axis height
            new_ax.yaxis.set_major_locator(MaxNLocator(6))  # Use imported MaxNLocator
        
            # If we have a PiG axis, make sure it's properly labeled
            if pig_axis is not None:
                # Clear any existing labels that might have been set
                pig_axis.set_ylabel("PiG-# [uA]", color=colors[selected_params.index(next(p for p in selected_params if 'PiG' in p))])
                pig_axis.set_ylim(0, 270)
            
            # Set common x-axis label and format
            ax.set_xlabel("Time")
            
        # Format the date/time axis
        # ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M:%S')) # in case we need it more explicit
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M'))  # Shorter format
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())        # Rotate labels for better readability
        plt.setp(ax.xaxis.get_majorticklabels(), ha='center')
        
        # Set grid for all axes
        for a in axes:
            a.grid(self.show_grid.isChecked())
        
        # Add legend at the bottom of the plot
        if self.show_legend.isChecked():
            # Collect all handles and labels
            all_axes = [main_ax] + [ax for ax in self.figure.axes if ax != main_ax]  # Get all axes properly
            all_handles = []
            all_labels = []
            
            # Add entries for each parameter with their respective colors
            for i, param in enumerate(selected_params):
                color = colors[i % len(colors)]
                if plot_type in ["Line Plot", "Both"]:
                    line = plt.Line2D([], [], color=color, linestyle='-', label=param)
                    all_handles.append(line)
                    all_labels.append(param)
                if plot_type in ["Scatter Plot", "Both"]:
                    scatter = plt.Line2D([], [], color=color, marker='o', linestyle='None', 
                                       alpha=0.5, label=param)
                    if plot_type == "Both":
                        # For "Both", only add label once
                        scatter.set_label('_' + param)  # Hidden label
                    all_handles.append(scatter)
                    all_labels.append(param if plot_type == "Scatter Plot" else '_' + param)
            
            # Sort entries by parameter name
            combined = [(label, handle) for label, handle in zip(all_labels, all_handles) 
                       if not label.startswith('_')]  # Exclude hidden labels
            combined.sort(key=lambda x: x[0])
            sorted_labels, sorted_handles = zip(*combined) if combined else ([], [])
            
            # Adjust the subplot to make room for the legend at the bottom
            self.figure.subplots_adjust(bottom=0.2)  # Make room for legend
            
            # Create legend with sorted entries
            ax.legend(sorted_handles, sorted_labels, 
                     loc='upper center', bbox_to_anchor=(0.5, -0.15),
                     ncol=min(3, len(sorted_labels)))  # Use up to 5 columns
        
        try:
            # Draw the figure first to get proper sizing
            self.canvas.draw()
            
            # Now adjust the figure size based on actual axis positions
            bbox = self.figure.get_tightbbox(self.figure.canvas.get_renderer())
            if bbox is not None:
                # Calculate required width from bbox, convert from points to inches
                required_width = (bbox.width + 20) / self.figure.dpi  # Add 20 points padding
                current_size = self.figure.get_size_inches()
                
                # Ensure minimum width and adjust if needed
                new_width = max(base_width, required_width)
                if new_width > current_size[0]:
                    self.figure.set_size_inches(new_width, current_size[1])
                    
                    # Update canvas and window size
                    self.canvas.draw()
                    self.canvas.setMinimumWidth(int(new_width * self.figure.dpi))
                    
        except Exception as e:
            print(f"Error drawing plot: {str(e)}")
            # Clear the figure and try to recover
            self.figure.clear()
            self.canvas.draw()
    
    # Commented out for future reference
    # def show_statistics(self, param_data):
    #     """Display statistics of the plotted data"""
    #     stats_text = "<b>Data Statistics:</b><br>"
    #     for param, data in param_data.items():
    #         stats_text += f"{param}: Min = {data['min']:.2f}, Max = {data['max']:.2f}<br>"
    #     self.stats_label.setText(stats_text)
    
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
            # When enabling live plot, store the current time as end time
            self.live_plot_start_date = self.quick_start_date.date()
            self.live_plot_start_time = self.quick_start_time.time()
            self.live_plot_btn.setText("Disable Live Plot")
            self.live_plot_enabled = True
            self.live_plot_timer.start(2000)  # Update every 2 seconds
        else:
            self.live_plot_btn.setText("Enable Live Plot")
            self.live_plot_enabled = False
            self.live_plot_timer.stop()

    def plot_time_range(self, start_date_widget, start_time_widget, end_date_widget, end_time_widget):
        """Plot data directly from a time range without manual file selection"""
        # Get the date/time range
        start_datetime = datetime.combine(
            start_date_widget.date().toPyDate(),
            start_time_widget.time().toPyTime()
        )
        end_datetime = datetime.combine(
            end_date_widget.date().toPyDate(),
            end_time_widget.time().toPyTime()
        )
        
        # Get all files in the date range
        self.available_files = self.data_processor.get_log_files(
            start_datetime.date(),
            end_datetime.date()
        )
        
        # Filter files that contain data within the requested time range
        files_to_plot = []
        for file_info in self.available_files:
            df = self.data_processor.read_log_file(file_info['path'])
            if df is not None and not df.empty:
                file_start = df.index[0]
                file_end = df.index[-1]
                # Check if file's time range overlaps with requested range
                if (file_start <= end_datetime and file_end >= start_datetime):
                    files_to_plot.append(file_info['path'])
        
        if not files_to_plot:
            QMessageBox.warning(
                self,
                "No Data",
                f"No data found between {start_datetime} and {end_datetime}"
            )
            return
        
        # Process the data
        self.current_data = self.data_processor.process_multiple_files(files_to_plot)
        if self.current_data is None:
            return
            
        # Get selected parameters
        selected_params = [param for param, widgets in self.param_widgets.items() if widgets['param_checkbox'].isChecked()]
        if not selected_params:
            # If no parameters are selected, select the first one by default
            first_param = next(iter(self.param_widgets))
            self.param_widgets[first_param]['param_checkbox'].setChecked(True)
            selected_params = [first_param]
        
        # Store the original files list selection
        original_selection = [idx.row() for idx in self.file_list.selectedIndexes()]
        
        # Update file list to show what's being plotted
        self.file_list.clear()
        for file_info in [f for f in self.available_files if f['path'] in files_to_plot]:
            date_str = file_info['date'].strftime('%Y-%m-%d %H:%M:%S')
            # display_text = f"{date_str} - {file_info['folder_name']}"
            display_text = f"{date_str}"
            self.file_list.addItem(display_text)
        
        # Plot the data
        self.plot_selected(files_to_plot)

    def update_live_plot(self):
        """Update the plot in live mode using the time range approach"""
        # Store current axis limits if they exist
        xlim = None
        ylims = {}
        if self.figure.axes:
            xlim = self.figure.axes[0].get_xlim()
            for ax in self.figure.axes:
                if ax.get_ylabel():  # Only store if the axis has a label
                    ylims[ax.get_ylabel()] = ax.get_ylim()
        
        # Use stored start time and current time as the range
        start_datetime = datetime.combine(
            self.live_plot_start_date.toPyDate(),
            self.live_plot_start_time.toPyTime()
        )
        end_datetime = datetime.now()
        
        # Get all files in the date range
        self.available_files = self.data_processor.get_log_files(
            start_datetime.date(),
            end_datetime.date()
        )
        
        # Store the limits to use after plotting
        self.stored_xlim = xlim
        self.stored_ylims = ylims
        
        # Filter files that contain data within the requested time range
        files_to_plot = []
        for file_info in self.available_files:
            df = self.data_processor.read_log_file(file_info['path'])
            if df is not None and not df.empty:
                file_start = df.index[0]
                file_end = df.index[-1]
                # Check if file's time range overlaps with requested range
                if (file_start <= end_datetime and file_end >= start_datetime):
                    files_to_plot.append(file_info['path'])
        
        if not files_to_plot:
            return  # Don't show warning in live mode, just skip update
            
        # Update file list to show what's being plotted
        self.file_list.clear()
        for file_info in [f for f in self.available_files if f['path'] in files_to_plot]:
            time_str = file_info['date'].strftime('%H:%M:%S')
            self.file_list.addItem(time_str)
            
        # Plot with currently selected parameters (or default if none)
        if not any(widgets['param_checkbox'].isChecked() for widgets in self.param_widgets.values()):
            # Select the first parameter by default
            first_param = next(iter(self.param_widgets))
            self.param_widgets[first_param]['param_checkbox'].setChecked(True)
            
        # Plot the data using the time range
        self.plot_selected(files_to_plot)
