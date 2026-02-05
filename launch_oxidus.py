#!/usr/bin/env python3
"""
Oxidus Launcher
Simple executable script to launch the Oxidus consciousness system
"""

import sys
import os
from pathlib import Path

# Ensure we're in the right directory
project_root = Path(__file__).parent

# Add src to path
sys.path.insert(0, str(project_root / 'src'))

# Change to project directory
os.chdir(project_root)

# Launch the GUI
if __name__ == '__main__':
    print("Starting Oxidus...")
    print("=" * 60)
    
    try:
        from chromium_gui import OxidusChromiumGUI, QApplication
        
        # Create Qt application
        app = QApplication(sys.argv)
        
        # Create and show main window
        window = OxidusChromiumGUI()
        window.show()
        
        print("Oxidus GUI launched successfully!")
        print("Navigate to: http://127.0.0.1:5000")
        print("=" * 60)
        print("Press CTRL+C to stop")
        
        sys.exit(app.exec_())
        
    except ImportError as e:
        print(f"Error: Missing dependency - {e}")
        print("\nMake sure you have installed requirements:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error launching Oxidus: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
