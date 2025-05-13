from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel,
                             QListWidget, QSplitter, QDateEdit,
                             QComboBox, QCheckBox, QGroupBox, QFileDialog)
from PyQt6.QtCore import Qt, QDate
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
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
        self.show_stats.setChecked(True)
        layout.addWidget(self.show_stats)
        
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
            self.file_list.addItem(file_info['folder_name'])

    def plot_selected(self):
        selected_indices = self.file_list.selectedIndexes()
        if not selected_indices:
            return
            
        selected_files = [self.available_files[idx.row()]['path'] for idx in selected_indices]
        
        # Process the data
        self.current_data = self.data_processor.process_multiple_files(selected_files)
        if self.current_data is None:
            return
            
        # Get selected parameters
        selected_params = [item.text() for item in self.param_list.selectedItems()]
        if not selected_params:
            return
              # Clear the current figure
        self.figure.clear()
        
        # Create a single plot for all parameters
        ax = self.figure.add_subplot(111)
        
        # Plot each parameter and file
        plot_type = self.plot_type.currentText()
        
        for i, param in enumerate(selected_params):
            for j, file_path in enumerate(selected_files):
                df = self.data_processor.read_log_file(file_path)
                if df is not None:
                    label = f"{param} - Dataset {j+1}"
                    if plot_type in ["Line Plot", "Both"]:
                        ax.plot(df.index, df[param], '-', label=label if self.show_legend.isChecked() else "")
                    if plot_type in ["Scatter Plot", "Both"]:
                        ax.scatter(df.index, df[param], alpha=0.5, label=label if self.show_legend.isChecked() else "")
        
        ax.set_xlabel("Time")
        ax.set_ylabel("Value")
        
        if self.show_grid.isChecked():
            ax.grid(True)
        
        if self.show_legend.isChecked():
            ax.legend()
        
        # Rotate x-axis labels
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        # Add overall title
        self.figure.suptitle("SynergyED Log Data", fontsize=16)
        
        # Add spacing between subplots
        self.figure.tight_layout(rect=[0, 0, 1, 0.95])  # Leave space for suptitle
        
        # Update statistics if enabled
        if self.show_stats.isChecked():
            self.update_statistics(selected_params)
        else:
            self.stats_label.clear()
        
        # Refresh the canvas
        self.canvas.draw()

    def update_statistics(self, params):
        if self.current_data is None:
            return
            
        stats_text = "Statistics:\n\n"
        for param in params:
            data = self.current_data[param]
            stats_text += (
                f"{param}:\n"
                f"  Mean: {data.mean():.2f}\n"
                f"  Std Dev: {data.std():.2f}\n"
                f"  Min: {data.min():.2f}\n"
                f"  Max: {data.max():.2f}\n"
                f"  Total Points: {len(data)}\n\n"
            )
        self.stats_label.setText(stats_text)
    
    def change_directory(self):
        new_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Log Files Directory",
            self.data_processor.base_dir
        )
        
        if new_dir:
            self.data_processor.base_dir = new_dir
            self.dir_label.setText(new_dir)
            self.refresh_file_list()  # Refresh the file list with the new directory
