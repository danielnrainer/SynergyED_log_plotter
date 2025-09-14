from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QSpinBox, QPushButton, QLabel, QGroupBox,
                             QComboBox, QDoubleSpinBox, QMessageBox, QListWidget,
                             QListWidgetItem, QCheckBox, QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from utils.email_notifier import EmailNotifier, TriggerCondition
import threading
import copy


class EmailTestThread(QThread):
    """Thread for testing email connection without blocking UI"""
    result_ready = pyqtSignal(bool, str)
    
    def __init__(self, notifier):
        super().__init__()
        self.notifier = notifier
        
    def run(self):
        success, message = self.notifier.test_connection()
        self.result_ready.emit(success, message)


class EmailConfigDialog(QDialog):
    """Dialog for configuring email notifications"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Email Notification Configuration")
        self.setModal(True)
        self.resize(600, 700)
        
        self.email_notifier = EmailNotifier()
        self.trigger_conditions = []
        
        self.setup_ui()
        self.load_common_smtp_settings()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # SMTP Configuration Group
        smtp_group = QGroupBox("Email Server Configuration")
        smtp_layout = QFormLayout()
        
        # Common provider dropdown
        self.provider_combo = QComboBox()
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        smtp_layout.addRow("Email Provider:", self.provider_combo)
        
        # SMTP settings
        self.smtp_server_edit = QLineEdit()
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(587)
        
        smtp_layout.addRow("SMTP Server:", self.smtp_server_edit)
        smtp_layout.addRow("Port:", self.smtp_port_spin)
        
        # Sender credentials
        self.sender_email_edit = QLineEdit()
        self.sender_password_edit = QLineEdit()
        self.sender_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        smtp_layout.addRow("Sender Email:", self.sender_email_edit)
        smtp_layout.addRow("Sender Password:", self.sender_password_edit)
        
        # Test connection button
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self.test_connection)
        smtp_layout.addRow("", self.test_button)
        
        self.connection_status = QLabel("")
        smtp_layout.addRow("Status:", self.connection_status)
        
        smtp_group.setLayout(smtp_layout)
        layout.addWidget(smtp_group)
        
        # Recipient Configuration
        recipient_group = QGroupBox("Recipient Configuration")
        recipient_layout = QFormLayout()
        
        self.recipient_email_edit = QLineEdit()
        recipient_layout.addRow("Recipient Email:", self.recipient_email_edit)
        
        recipient_group.setLayout(recipient_layout)
        layout.addWidget(recipient_group)
        
        # Trigger Conditions Group
        trigger_group = QGroupBox("Alert Trigger Conditions")
        trigger_layout = QVBoxLayout()
        
        # Add trigger controls
        add_trigger_layout = QHBoxLayout()
        
        self.parameter_combo = QComboBox()
        self.load_parameters()
        
        self.condition_combo = QComboBox()
        self.condition_combo.addItems(["Greater than", "Less than", "Equals"])
        
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(-999999, 999999)
        self.threshold_spin.setDecimals(3)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 1440)  # 0 to 24 hours in minutes
        self.duration_spin.setSuffix(" minutes")
        self.duration_spin.setSpecialValueText("Immediate")
        
        # Monitoring type selector
        self.monitoring_type_combo = QComboBox()
        self.monitoring_type_combo.addItems([
            "Alert if condition persists (continuous)",
            "Monitor for next X minutes (time-bounded)",
            "Wait X minutes, then alert (delayed)"
        ])
        self.monitoring_type_combo.setCurrentIndex(0)  # Default to continuous (original behavior)
        
        add_trigger_btn = QPushButton("Add Trigger")
        add_trigger_btn.clicked.connect(self.add_trigger)
        
        add_trigger_layout.addWidget(QLabel("Parameter:"))
        add_trigger_layout.addWidget(self.parameter_combo)
        add_trigger_layout.addWidget(self.condition_combo)
        add_trigger_layout.addWidget(self.threshold_spin)
        add_trigger_layout.addWidget(QLabel("Duration:"))
        add_trigger_layout.addWidget(self.duration_spin)
        add_trigger_layout.addWidget(QLabel("Monitoring Type:"))
        add_trigger_layout.addWidget(self.monitoring_type_combo)
        add_trigger_layout.addWidget(add_trigger_btn)
        
        trigger_layout.addLayout(add_trigger_layout)
        
        # Triggers list
        self.triggers_list = QListWidget()
        trigger_layout.addWidget(QLabel("Active Triggers:"))
        trigger_layout.addWidget(self.triggers_list)
        
        # Remove trigger button
        remove_trigger_btn = QPushButton("Remove Selected Trigger")
        remove_trigger_btn.clicked.connect(self.remove_trigger)
        trigger_layout.addWidget(remove_trigger_btn)
        
        trigger_group.setLayout(trigger_layout)
        layout.addWidget(trigger_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Save Configuration")
        self.save_btn.clicked.connect(self.save_configuration)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.test_alert_btn = QPushButton("Send Test Alert")
        self.test_alert_btn.clicked.connect(self.send_test_alert)
        
        button_layout.addWidget(self.test_alert_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def load_common_smtp_settings(self):
        """Load common email provider settings"""
        providers = {
            "Custom": ("", 587),
            "Gmail": ("smtp.gmail.com", 587),
            "Outlook/Hotmail": ("smtp-mail.outlook.com", 587),
            "Yahoo": ("smtp.mail.yahoo.com", 587),
            "Exchange/Office365": ("smtp.office365.com", 587)
        }
        
        self.provider_settings = providers
        self.provider_combo.addItems(providers.keys())
        
    def on_provider_changed(self, provider_name):
        """Update SMTP settings when provider is changed"""
        if provider_name in self.provider_settings:
            server, port = self.provider_settings[provider_name]
            self.smtp_server_edit.setText(server)
            self.smtp_port_spin.setValue(port)
            
    def load_parameters(self):
        """Load available parameters from LogDataProcessor"""
        from utils.data_processor import LogDataProcessor
        
        # Use the exact parameter names from the data processor
        params = LogDataProcessor.NUMERIC_COLUMNS
        
        self.parameter_combo.addItems(params)
        
    def test_connection(self):
        """Test the email connection"""
        # Configure the notifier with current settings
        self.email_notifier.configure_smtp(
            self.smtp_server_edit.text(),
            self.smtp_port_spin.value(),
            self.sender_email_edit.text(),
            self.sender_password_edit.text()
        )
        
        # Update UI to show testing
        self.test_button.setEnabled(False)
        self.test_button.setText("Testing...")
        self.connection_status.setText("Testing connection...")
        
        # Test connection in separate thread
        self.test_thread = EmailTestThread(self.email_notifier)
        self.test_thread.result_ready.connect(self.on_test_result)
        self.test_thread.start()
        
    def on_test_result(self, success, message):
        """Handle test connection result"""
        self.test_button.setEnabled(True)
        self.test_button.setText("Test Connection")
        
        if success:
            self.connection_status.setText("✓ " + message)
            self.connection_status.setStyleSheet("color: green;")
        else:
            self.connection_status.setText("✗ " + message)
            self.connection_status.setStyleSheet("color: red;")
            
    def add_trigger(self):
        """Add a new trigger condition"""
        parameter = self.parameter_combo.currentText()
        condition_text = self.condition_combo.currentText()
        threshold = self.threshold_spin.value()
        duration = self.duration_spin.value()
        monitoring_type_index = self.monitoring_type_combo.currentIndex()
        
        # Convert condition text to internal format
        condition_map = {
            "Greater than": "greater_than",
            "Less than": "less_than",
            "Equals": "equals"
        }
        
        # Convert monitoring type index to internal format
        monitoring_type_map = [
            TriggerCondition.CONTINUOUS_DURATION,  # 0: "Alert if condition persists (continuous)"
            TriggerCondition.TIME_BOUNDED,         # 1: "Monitor for next X minutes (time-bounded)"
            TriggerCondition.DELAYED_ACTIVATION    # 2: "Wait X minutes, then alert (delayed)"
        ]
        
        condition_type = condition_map[condition_text]
        monitoring_type = monitoring_type_map[monitoring_type_index]
        
        # Create trigger condition
        trigger = TriggerCondition(parameter, condition_type, threshold, duration, monitoring_type)
        self.trigger_conditions.append(trigger)
        
        # Add to list widget
        item_text = trigger.get_description()
        self.triggers_list.addItem(item_text)
        
    def remove_trigger(self):
        """Remove selected trigger condition"""
        current_row = self.triggers_list.currentRow()
        if current_row >= 0:
            self.triggers_list.takeItem(current_row)
            del self.trigger_conditions[current_row]
            
    def send_test_alert(self):
        """Send a test alert email"""
        if not self.recipient_email_edit.text():
            QMessageBox.warning(self, "Warning", "Please enter a recipient email address.")
            return
            
        self.email_notifier.set_recipient(self.recipient_email_edit.text())
        
        success = self.email_notifier.send_alert(
            "Test Alert",
            "This is a test alert from SynergyED Log Plotter to verify email notifications are working correctly."
        )
        
        if success:
            QMessageBox.information(self, "Success", "Test alert sent successfully!")
        else:
            QMessageBox.warning(self, "Failed", "Failed to send test alert. Please check your configuration.")
            
    def save_configuration(self):
        """Save the email configuration"""
        if not self.smtp_server_edit.text() or not self.sender_email_edit.text():
            QMessageBox.warning(self, "Warning", "Please fill in all required fields.")
            return
            
        if not self.recipient_email_edit.text():
            QMessageBox.warning(self, "Warning", "Please enter a recipient email address.")
            return
            
        # Configure the notifier
        self.email_notifier.configure_smtp(
            self.smtp_server_edit.text(),
            self.smtp_port_spin.value(),
            self.sender_email_edit.text(),
            self.sender_password_edit.text()
        )
        
        self.email_notifier.set_recipient(self.recipient_email_edit.text())
        
        self.accept()
        
    def get_email_notifier(self):
        """Get the configured email notifier"""
        return self.email_notifier
        
    def get_trigger_conditions(self):
        """Get the list of trigger conditions"""
        return self.trigger_conditions
        
    def set_email_notifier(self, notifier):
        """Set existing email notifier configuration"""
        if notifier and notifier.is_configured:
            self.smtp_server_edit.setText(notifier.smtp_server)
            self.smtp_port_spin.setValue(notifier.smtp_port)
            self.sender_email_edit.setText(notifier.sender_email)
            self.sender_password_edit.setText(notifier.sender_password)
            self.recipient_email_edit.setText(notifier.recipient_email)
            
            # Try to match provider
            for provider, (server, port) in self.provider_settings.items():
                if server == notifier.smtp_server and port == notifier.smtp_port:
                    self.provider_combo.setCurrentText(provider)
                    break
            else:
                self.provider_combo.setCurrentText("Custom")
                
            # Copy the notifier
            self.email_notifier = notifier
            
    def set_trigger_conditions(self, conditions):
        """Set existing trigger conditions"""
        self.trigger_conditions = copy.deepcopy(conditions) if conditions else []
        
        # Clear and populate the list widget
        self.triggers_list.clear()
        for trigger in self.trigger_conditions:
            self.triggers_list.addItem(trigger.get_description())