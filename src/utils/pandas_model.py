# src/utils/pandas_model.py
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
import pandas as pd


class PandasModel(QAbstractTableModel):
    def __init__(self, dataframe: pd.DataFrame):
        super().__init__()
        self._dataframe = dataframe.copy()

    def rowCount(self, parent=QModelIndex()):
        return len(self._dataframe)

    def columnCount(self, parent=QModelIndex()):
        return len(self._dataframe.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.DisplayRole:
            value = self._dataframe.iloc[index.row(), index.column()]
            # Format numeric values
            if pd.api.types.is_float(value):
                return f"{value:.2f}"
            return str(value)

        elif role == Qt.TextAlignmentRole:
            value = self._dataframe.iloc[index.row(), index.column()]
            if pd.api.types.is_numeric_dtype(type(value)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return str(self._dataframe.columns[section])
        elif orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(self._dataframe.index[section])
        return None