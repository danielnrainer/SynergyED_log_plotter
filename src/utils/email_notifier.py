import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

class EmailNotifier:
    """Handles email notifications for SynergyED Log Plotter alerts"""
    
    def __init__(self):
        self.smtp_server = ""
        self.smtp_port = 587
        self.sender_email = ""
        self.sender_password = ""
        self.recipient_email = ""
        self.is_configured = False
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
    def configure_smtp(self, smtp_server, smtp_port, sender_email, sender_password):
        """Configure SMTP settings for sending emails"""
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.is_configured = True
        
    def set_recipient(self, recipient_email):
        """Set the recipient email address"""
        self.recipient_email = recipient_email
        
    def test_connection(self):
        """Test the email configuration by attempting to connect"""
        if not self.is_configured:
            return False, "Email not configured"
            
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                return True, "Connection successful"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
            
    def send_alert(self, subject, message, parameter_name=None, value=None, threshold=None):
        """Send an alert email"""
        if not self.is_configured or not self.recipient_email:
            self.logger.error("Email not properly configured")
            return False
            
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = f"SynergyED Alert: {subject}"
            
            # Create email body
            body = f"""
SynergyED Log Plotter Alert

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Alert Details:
{message}
"""
            
            if parameter_name and value is not None and threshold is not None:
                body += f"""
Parameter: {parameter_name}
Current Value: {value}
Threshold: {threshold}
"""
            
            body += """
This is an automated message from SynergyED Log Plotter.
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
                
            self.logger.info(f"Alert email sent successfully to {self.recipient_email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            return False


class TriggerCondition:
    """Represents a trigger condition for email alerts"""
    
    # Monitoring type constants
    TIME_BOUNDED = 'time_bounded'  # Monitor for next X minutes
    DELAYED_ACTIVATION = 'delayed_activation'  # Wait X minutes, then alert
    CONTINUOUS_DURATION = 'continuous_duration'  # Alert if condition persists for X minutes (original)
    
    def __init__(self, parameter_name, condition_type, threshold_value, duration_minutes=0, monitoring_type=None):
        self.parameter_name = parameter_name
        self.condition_type = condition_type  # 'greater_than', 'less_than', 'equals'
        self.threshold_value = threshold_value
        self.duration_minutes = duration_minutes
        self.monitoring_type = monitoring_type or self.CONTINUOUS_DURATION  # Default to original behavior
        self.trigger_start_time = None
        self.monitoring_start_time = None  # For time_bounded and delayed_activation
        self.is_active = False
        self.last_triggered = None
        
    def check_condition(self, current_value, current_time):
        """Check if the trigger condition is met"""
        if current_value is None:
            return False
            
        # Check if condition is met
        condition_met = False
        if self.condition_type == 'greater_than':
            condition_met = current_value > self.threshold_value
        elif self.condition_type == 'less_than':
            condition_met = current_value < self.threshold_value
        elif self.condition_type == 'equals':
            condition_met = abs(current_value - self.threshold_value) < 0.001  # Small tolerance for floats
            
        # Handle different monitoring types
        if self.monitoring_type == self.TIME_BOUNDED:
            # Monitor for next X minutes - start monitoring when first called
            if self.monitoring_start_time is None:
                self.monitoring_start_time = current_time
                
            # Check if monitoring period has expired
            monitoring_elapsed = (current_time - self.monitoring_start_time).total_seconds() / 60
            if monitoring_elapsed > self.duration_minutes:
                return False  # Stop monitoring after duration
                
            # Alert if condition is met within monitoring period
            if condition_met and not self.is_active:
                self.is_active = True
                self.last_triggered = current_time
                return True
            elif not condition_met:
                self.is_active = False
                
        elif self.monitoring_type == self.DELAYED_ACTIVATION:
            # Wait X minutes, then alert if condition is met
            if self.monitoring_start_time is None:
                self.monitoring_start_time = current_time
                
            # Check if delay period has passed
            delay_elapsed = (current_time - self.monitoring_start_time).total_seconds() / 60
            if delay_elapsed >= self.duration_minutes:
                # Alert if condition is met after delay
                if condition_met and not self.is_active:
                    self.is_active = True
                    self.last_triggered = current_time
                    return True
                elif not condition_met:
                    self.is_active = False
                    
        else:  # CONTINUOUS_DURATION (original behavior)
            # Alert if condition persists for X minutes
            if self.duration_minutes > 0:
                if condition_met:
                    if self.trigger_start_time is None:
                        self.trigger_start_time = current_time
                    elif (current_time - self.trigger_start_time).total_seconds() >= (self.duration_minutes * 60):
                        if not self.is_active:
                            self.is_active = True
                            self.last_triggered = current_time
                            return True
                else:
                    # Reset if condition is no longer met
                    self.trigger_start_time = None
                    self.is_active = False
            else:
                # Immediate trigger
                if condition_met and not self.is_active:
                    self.is_active = True
                    self.last_triggered = current_time
                    return True
                elif not condition_met:
                    self.is_active = False
                    
        return False
        
    def get_description(self):
        """Get a human-readable description of the trigger condition"""
        condition_text = {
            'greater_than': 'greater than',
            'less_than': 'less than',
            'equals': 'equals'
        }
        
        base_desc = f"{self.parameter_name} {condition_text.get(self.condition_type, 'unknown')} {self.threshold_value}"
        
        if self.duration_minutes > 0:
            if self.monitoring_type == self.TIME_BOUNDED:
                desc = f"Alert if {base_desc} (monitoring for next {self.duration_minutes} minutes)"
            elif self.monitoring_type == self.DELAYED_ACTIVATION:
                desc = f"Wait {self.duration_minutes} minutes, then alert if {base_desc}"
            else:  # CONTINUOUS_DURATION
                desc = f"Alert if {base_desc} for {self.duration_minutes} minutes"
        else:
            desc = f"Alert immediately if {base_desc}"
            
        return desc