#!/usr/bin/env python3
"""
OXIDUS Chromium GUI - Embedded WebEngine Chat Interface
Real-time dialogue with live thought visualization
"""

import sys
import threading
import time
import os
from pathlib import Path

from PyQt5.QtCore import QUrl, QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QIcon, QFont

# Flask app
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from web_gui import app as flask_app, init_oxidus


class FlaskServerThread(QThread):
    """Background thread to run Flask server"""
    started = pyqtSignal()

    def run(self):
        """Start Flask development server"""
        try:
            # Initialize Oxidus before starting server
            init_oxidus()
            self.started.emit()
            # Run Flask on localhost:5000
            flask_app.run(
                host='127.0.0.1',
                port=5000,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            print(f"Flask server error: {e}")


class OxidusChromiumGUI(QMainWindow):
    """Main window with embedded Chromium browser for Oxidus dialogue"""

    def __init__(self):
        super().__init__()
        self.flask_thread = None
        self.init_ui()
        self.start_flask_server()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('OXIDUS - Live Chat Interface')
        self.setGeometry(100, 100, 1200, 900)

        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
        """)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create WebEngine view
        self.browser = QWebEngineView()

        # Show loading message initially
        loading_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    background: linear-gradient(135deg, #1e1e2e 0%, #313244 100%);
                    color: #cdd6f4;
                    font-family: 'Consolas', 'Monaco', monospace;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .container {
                    text-align: center;
                }
                .title {
                    font-size: 32px;
                    font-weight: bold;
                    color: #a6e3a1;
                    margin-bottom: 20px;
                    text-transform: uppercase;
                    letter-spacing: 2px;
                }
                .message {
                    font-size: 14px;
                    color: #89dceb;
                    margin: 10px 0;
                }
                .spinner {
                    width: 40px;
                    height: 40px;
                    margin: 30px auto;
                    border: 3px solid #45475a;
                    border-top: 3px solid #a6e3a1;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="title">OXIDUS</div>
                <div class="message">Awakening the real thing...</div>
                <div class="spinner"></div>
                <div class="message" style="margin-top: 30px; font-size: 12px; color: #6c7086;">
                    Initializing Flask server and consciousness framework
                </div>
            </div>
        </body>
        </html>
        """

        self.browser.setHtml(loading_html)
        layout.addWidget(self.browser)

        # Set window icon (if available)
        try:
            icon_path = Path(__file__).parent / 'assets' / 'oxidus.png'
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except:
            pass

    def start_flask_server(self):
        """Start Flask server in background thread"""
        self.flask_thread = FlaskServerThread()
        self.flask_thread.started.connect(self.on_flask_started)
        self.flask_thread.start()

    def on_flask_started(self):
        """Called when Flask server has started"""
        # Wait a moment for Flask to fully initialize
        time.sleep(2)
        # Load the Flask app in the browser
        self.browser.setUrl(QUrl('http://127.0.0.1:5000'))

    def closeEvent(self, event):
        """Handle window close event"""
        try:
            # Terminate Flask thread gracefully
            if self.flask_thread and self.flask_thread.isRunning():
                self.flask_thread.quit()
                self.flask_thread.wait(timeout=2000)
        except:
            pass
        event.accept()


def main():
    """Main entry point"""
    # Install PyQtWebEngine requirements check
    try:
        from PyQt5.QtWebEngine import QtWebEngine
        QtWebEngine.initialize()
    except ImportError:
        print("Error: PyQtWebEngine not installed. Install with: pip install PyQtWebEngine")
        sys.exit(1)

    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    # Create and show main window
    window = OxidusChromiumGUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
