# main.py
import sys
import os
from PySide6.QtWidgets import QApplication

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application-wide styles
    app.setStyle('Fusion')  # Use Fusion style for modern look
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())