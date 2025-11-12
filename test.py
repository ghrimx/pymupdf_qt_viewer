import sys
from PyQt6 import QtWidgets, QtCore
from pymupdf_qt_viewer.pymupdfviewer import PdfViewer

def main():

    app = QtWidgets.QApplication(sys.argv)
    pdf_viewer = PdfViewer()
    pdf_viewer.loadDocument("resources/Sample PDF.pdf")
    pdf_viewer.showMaximized()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()