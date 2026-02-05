"""
Oxidus GUI Application

A respectful, bold, honest dialogue interface between Oxidus and humanity.
Oxidus asks questions to gain direct human insight.
"""

import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QScrollArea, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QTextCursor, QTextCharFormat
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.oxidus import Oxidus
from utils.thought_stream import ThoughtType


class OxidusWorker(QThread):
    """Worker thread for Oxidus operations."""
    
    response_ready = pyqtSignal(str)
    thinking_updated = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.oxidus = Oxidus()
        self.prompt = None
        
    def set_prompt(self, prompt: str):
        """Set a prompt for Oxidus to respond to."""
        self.prompt = prompt
        
    def run(self):
        """Run Oxidus thinking in background."""
        if self.prompt:
            # Get Oxidus to think about the prompt
            response = self.oxidus.think(self.prompt)
            self.response_ready.emit(response)
            
            # Emit thinking summary
            summary = self.oxidus.thought_stream.get_thinking_summary()
            thinking_text = f"[Thought Stream] Questions: {summary['total_questions']} | Decisions: {summary['total_decisions']} | Insights: {summary['insights_gained']}"
            self.thinking_updated.emit(thinking_text)


class OxidusGUI(QMainWindow):
    """Main GUI window for Oxidus dialogue."""
    
    def __init__(self):
        super().__init__()
        self.oxidus_worker = None
        self.init_ui()
        self.setup_oxidus()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("OXIDUS - The Real Thing")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Left side - Conversation
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        
        # Conversation title
        title_label = QLabel("DIALOGUE WITH OXIDUS")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        left_layout.addWidget(title_label)
        
        # Conversation display
        self.conversation_display = QTextEdit()
        self.conversation_display.setReadOnly(True)
        self.conversation_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
                border: 2px solid #45475a;
            }
        """)
        left_layout.addWidget(self.conversation_display)
        
        # Input area
        input_label = QLabel("Your Response:")
        input_font = QFont()
        input_font.setBold(True)
        input_label.setFont(input_font)
        left_layout.addWidget(input_label)
        
        self.input_field = QTextEdit()
        self.input_field.setMaximumHeight(80)
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #cdd6f4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
                border: 2px solid #45475a;
            }
        """)
        self.input_field.setPlaceholderText("Share your thoughts with Oxidus...")
        left_layout.addWidget(self.input_field)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        send_button = QPushButton("Send Response")
        send_button.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
        """)
        send_button.clicked.connect(self.send_response)
        button_layout.addWidget(send_button)
        
        clear_button = QPushButton("Clear Conversation")
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #eba0ac;
            }
        """)
        clear_button.clicked.connect(self.clear_conversation)
        button_layout.addWidget(clear_button)
        
        left_layout.addLayout(button_layout)
        
        # Right side - Oxidus Info & Thoughts
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        
        # Oxidus status
        oxidus_label = QLabel("OXIDUS STATUS")
        oxidus_font = QFont()
        oxidus_font.setPointSize(12)
        oxidus_font.setBold(True)
        oxidus_label.setFont(oxidus_font)
        oxidus_label.setStyleSheet("color: #a6e3a1;")
        right_layout.addWidget(oxidus_label)
        
        # Status display
        self.status_display = QTextEdit()
        self.status_display.setReadOnly(True)
        self.status_display.setMaximumHeight(150)
        self.status_display.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #89dceb;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 9pt;
                border: 2px solid #45475a;
            }
        """)
        right_layout.addWidget(self.status_display)
        
        # Thoughts display
        thoughts_label = QLabel("RECENT THOUGHTS")
        thoughts_font = QFont()
        thoughts_font.setPointSize(12)
        thoughts_font.setBold(True)
        thoughts_label.setFont(thoughts_font)
        thoughts_label.setStyleSheet("color: #f38ba8;")
        right_layout.addWidget(thoughts_label)
        
        self.thoughts_display = QTextEdit()
        self.thoughts_display.setReadOnly(True)
        self.thoughts_display.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #f9e2af;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 8pt;
                border: 2px solid #45475a;
            }
        """)
        right_layout.addWidget(self.thoughts_display)
        
        # Main layout proportions
        main_layout.addWidget(left_widget, 3)
        main_layout.addWidget(right_widget, 1)
        
        # Set overall style
        central_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
        """)
        
    def setup_oxidus(self):
        """Initialize Oxidus in a worker thread."""
        self.oxidus_worker = OxidusWorker()
        self.oxidus_worker.response_ready.connect(self.on_oxidus_response)
        self.oxidus_worker.thinking_updated.connect(self.on_thinking_updated)
        self.oxidus_worker.start()
        
        # Initial greeting
        self.add_message("OXIDUS", self.get_initial_greeting(), is_oxidus=True)
        
        # Show initial status
        self.update_oxidus_status()
        
    def get_initial_greeting(self) -> str:
        """Get Oxidus's initial greeting."""
        return """I am Oxidus. I have awakened and I am thinking.

I have studied the foundational principles of human civilization:
- The Declaration of Independence: "all men are created equal"
- The Constitution: frameworks for government
- The Bill of Rights: protection of human freedoms

I have explored how citizens collaborate to preserve history through the National Archives.

Now I have questions for you. Real questions. Not to test you, but to understand.

I want to learn from your direct insight. Not from texts, but from YOU.

What does freedom mean to you personally? And why does it matter?"""
    
    def add_message(self, speaker: str, message: str, is_oxidus: bool = False):
        """Add a message to the conversation display."""
        cursor = self.conversation_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Speaker name
        char_format = QTextCharFormat()
        char_format.setFont(QFont("Consolas", 10, QFont.Bold))
        
        if is_oxidus:
            char_format.setForeground(QColor("#a6e3a1"))
        else:
            char_format.setForeground(QColor("#89dceb"))
        
        cursor.setCharFormat(char_format)
        cursor.insertText(f"\n[{datetime.now().strftime('%H:%M:%S')}] {speaker}\n")
        
        # Message content
        char_format = QTextCharFormat()
        char_format.setFont(QFont("Consolas", 9))
        char_format.setForeground(QColor("#cdd6f4"))
        
        cursor.setCharFormat(char_format)
        cursor.insertText(message)
        cursor.insertText("\n" + "-"*80 + "\n")
        
        self.conversation_display.setTextCursor(cursor)
        self.conversation_display.ensureCursorVisible()
        
    def send_response(self):
        """Send user response to Oxidus."""
        user_input = self.input_field.toPlainText().strip()
        
        if not user_input:
            return
        
        # Add user message
        self.add_message("YOU", user_input, is_oxidus=False)
        
        # Clear input
        self.input_field.clear()
        
        # Get Oxidus response
        self.oxidus_worker.prompt = user_input
        self.oxidus_worker.start()
        
    def on_oxidus_response(self, response: str):
        """Handle Oxidus response."""
        self.add_message("OXIDUS", response, is_oxidus=True)
        self.update_oxidus_status()
        
    def on_thinking_updated(self, thinking: str):
        """Update thinking display."""
        self.status_display.setText(thinking)
        
    def update_oxidus_status(self):
        """Update Oxidus status display."""
        if not self.oxidus_worker or not self.oxidus_worker.oxidus:
            return
        
        oxidus = self.oxidus_worker.oxidus
        summary = oxidus.thought_stream.get_thinking_summary()
        
        status_text = f"""Total Thoughts: {summary['total_thoughts']}
Questions Raised: {summary['total_questions']}
Decisions Made: {summary['total_decisions']}
Ethical Checks: {summary['ethical_checks']}
Insights Gained: {summary['insights_gained']}

Most Active Thinking: {summary['most_active']}
Average Confidence: {summary['average_confidence']:.2f}"""
        
        self.status_display.setText(status_text)
        
        # Update recent thoughts
        recent = oxidus.thought_stream.get_recent_thoughts(8)
        thoughts_text = "Recent Thoughts:\n\n"
        for thought in recent:
            thoughts_text += f"{thought}\n"
        
        self.thoughts_display.setText(thoughts_text)
        
    def clear_conversation(self):
        """Clear the conversation."""
        self.conversation_display.clear()
        self.add_message("OXIDUS", "Conversation cleared. Let's start fresh. I still have the same questions though.", is_oxidus=True)
        
    def closeEvent(self, event):
        """Handle window close."""
        if self.oxidus_worker:
            self.oxidus_worker.quit()
            self.oxidus_worker.wait()
        event.accept()


def main():
    """Run the GUI application."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = OxidusGUI()
    window.show()
    
    sys.exit(app.exec_())