import sys
from PyQt6 import QtWidgets, QtCore
from pymupdf_qt_viewer.pymupdfviewer import PdfViewer

def main():

    app = QtWidgets.QApplication(sys.argv)
    m = QtWidgets.QMainWindow()
    pdf_viewer = PdfViewer()
    m.setCentralWidget(pdf_viewer)
    m.showMaximized()
    pdf_viewer.loadDocument(r"C:\Users\debru\Downloads\guideline-good-pharmacovigilance-practices-module-i-pharmacovigilance-systems-and-their-quality-systems_en.pdf")
    sys.exit(app.exec())


if __name__ == '__main__':
    main()