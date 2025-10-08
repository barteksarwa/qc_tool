# src/utils/visualizer.py
import matplotlib.pyplot as plt
from io import BytesIO
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel  # For embedding

def plot_discrepancies(df):
    if df.empty:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, 'No data', ha='center')
    else:
        fig, ax = plt.subplots()
        df.groupby('Year')['diff_pct'].mean().plot(kind='bar', ax=ax)
        ax.set_title('Average % Discrepancy by Year')
    
    # Convert to pixmap for QLabel
    buf = BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    pixmap = QPixmap()
    pixmap.loadFromData(buf.read())
    plt.close(fig)
    return pixmap