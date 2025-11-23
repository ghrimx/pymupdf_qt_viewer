import pymupdf
import logging

from enum import Enum
from dataclasses import dataclass, InitVar

from PyQt6.QtWidgets import (QApplication, QWidget, QGraphicsView, QGraphicsScene, 
                             QGraphicsPixmapItem, QGraphicsLineItem, QVBoxLayout, 
                             QToolBar, QTabWidget, QTreeView, QAbstractItemView, 
                             QLabel, QLineEdit, QSplitter, QSizePolicy, QComboBox,
                             QHBoxLayout, QLayout, QToolButton, QSpacerItem,
                             QGraphicsItem, QGraphicsObject, QGraphicsRectItem)
from PyQt6.QtGui import (QPainter, QColor, QShowEvent, QPixmap, QKeyEvent, 
                         QWheelEvent, QPen, QKeySequence, QStandardItem, 
                         QStandardItemModel, QActionGroup, QAction, QIcon)
from PyQt6.QtCore import (Qt, pyqtSignal as Signal, pyqtSlot as Slot, 
                          QObject, QEvent, QPointF, QRectF, QSize, 
                          QItemSelection)

from qt_theme_manager import theme_icon_manager


SUPPORTED_FORMART = (".pdf", ".epub")

logger = logging.getLogger(__name__)

class ZoomSelector(QWidget):

    class ZoomMode(Enum):
        Custom = 0
        FitToWidth = 1
        FitInView = 2

    zoomModeChanged = Signal(ZoomMode)
    zoomFactorChanged = Signal(float)
    zoom_levels = ["Fit Width", "Fit Page", "12%", "25%", "33%", "50%", "66%", "75%", "100%", "125%", "150%", "200%", "400%"]
    max_zoom_factor = 3.0
    min_zoom_factor = 0.5
    zoom_factor_step = 0.25

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom_factor: float = 1.0

    def zoomWidgets(self):
        self._selector = QComboBox()
        self._selector.setEditable(True)
        for zoom_level in self.zoom_levels:
            self._selector.addItem(zoom_level)
        self._selector.currentTextChanged.connect(self.onCurrentTextChanged)
        self._selector.lineEdit().editingFinished.connect(self._editingFinished)
        self.action_zoom_in = QAction(theme_icon_manager.get_icon(":zoom-in"), "Zoom In", self)
        self.action_zoom_in.setToolTip("Zoom In")
        self.action_zoom_out = QAction(theme_icon_manager.get_icon(":zoom-out"), "Zoom Out", self)
        self.action_zoom_out.setToolTip("Zoom Out")
        return self.action_zoom_in, self.action_zoom_out, self._selector

    @property
    def zoomFactor(self) -> float:
        return self._zoom_factor

    @zoomFactor.setter
    def zoomFactor(self, zoom_factor):
        self._zoom_factor = zoom_factor
        self.setZoomFactor(self._zoom_factor)

    @Slot()
    def zoomIn(self):
        if self.zoomFactor < ZoomSelector.max_zoom_factor:
            self.zoomFactor += self.zoom_factor_step

    @Slot()
    def zoomOut(self):
        if self.zoomFactor > ZoomSelector.min_zoom_factor:
            self.zoomFactor -= self.zoom_factor_step

    @Slot()
    def _editingFinished(self):
        self.onCurrentTextChanged(self._selector.lineEdit().text())

    @Slot(float)
    def setZoomFactor(self, zf):
        zoom_level = int(100 * zf)
        self._selector.setCurrentText(f"{zoom_level}%")

    @Slot()
    def reset(self):
        self._selector.setCurrentIndex(8)  # 100%

    @Slot(str)
    def onCurrentTextChanged(self, text: str):
        if text == "Fit Width":
            self.zoomModeChanged.emit(ZoomSelector.ZoomMode.FitToWidth)
        elif text == "Fit Page":
            self.zoomModeChanged.emit(ZoomSelector.ZoomMode.FitInView)
        else:
            factor = 1.0
            withoutPercent = text.replace('%', '')
            zoomLevel = int(withoutPercent)
            if zoomLevel:
                factor = zoomLevel / 100.0

            self.zoomModeChanged.emit(ZoomSelector.ZoomMode.Custom)
            self.zoomFactorChanged.emit(factor)


class PageNavigator(QWidget):
    currentPnoChanged = Signal(int)
    currentLocationChanged = Signal(QPointF)

    def __init__(self, parent: QWidget = None):
        super().__init__()
        self._current_pno: int = None  # pno : page number
        self._current_page_label: str = ""
        self._current_location: QPointF = QPointF()
        self._page_index:  dict[str, int] = {}

        hbox = QHBoxLayout()
        hbox.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.setLayout(hbox)
        self.setContentsMargins(0, 0, 0, 0)
        hbox.setContentsMargins(5, 0, 5, 0)
        
        self.currentpage_lineedit = QLineEdit()
        self.currentpage_lineedit.setFixedWidth(40)
        self.currentpage_lineedit.editingFinished.connect(self.onPageLineEditChanged)
        self.pagecount_label = QLabel()
        # self.pagecount_label.setFixedWidth(40)

        self.previous_page = QAction(theme_icon_manager.get_icon(':arrow-up-s-line'), "Previous page", self, triggered=self.previous)
        self.next_page = QAction(theme_icon_manager.get_icon(':arrow-down-s-line'), "Next page", self, triggered=self.next)
    
    def navigatorWidgets(self) -> tuple[QAction, QAction]:
        return self.previous_page, self.next_page

    def setDocument(self, document: pymupdf.Document):
        self._document: pymupdf.Document = document
        self.indexPages()

    def indexPages(self):
        page: pymupdf.Page
        for page in self._document:
            self._page_index.update({page.get_label() : page.number})
    
    def pageNumberFromLabel(self, label) -> int | None:
        return self._page_index.get(label)

    def updatePageLineEdit(self):
        page_label = self.currentPageLabel()

        if page_label != "":
            self.currentpage_lineedit.setText(page_label)
        else:
            self.currentpage_lineedit.setText(f"{self.currentPno() + 1}")
        
        self.pagecount_label.setText(f"{self.currentPno() + 1} of {self._document.page_count}")
    
    def document(self):
        return self._document
    
    def _setCurrentPno(self, index: int):
        old_index = self._current_pno

        if 0<= index < self._document.page_count:
            self._current_pno = index
            self.updatePageLineEdit()

            if old_index != self._current_pno:
                self.currentPnoChanged.emit(self._current_pno)

    def currentPageLabel(self) -> str:
        page: pymupdf.Page = self._document[self.currentPno()]
        return page.get_label()

    def currentPno(self) -> int:
        return self._current_pno
    
    def jump(self, page: int, location = QPointF()):
        self._setCurrentPno(page)
        self._current_location = location
        self.currentLocationChanged.emit(location)  

    @Slot()
    def onPageLineEditChanged(self):
        p = self.currentpage_lineedit.text()  #  page requested by user
        pno = self.pageNumberFromLabel(p)
 
        if pno is None:
            try:
                pno = int(p) - 1
            except:
                ...
        
        if isinstance(pno, int):
            self.jump(pno)
  
    @Slot()
    def next(self):
        self.jump(self.currentPno() + 1, QPointF())

    @Slot()
    def previous(self):
        self.jump(self.currentPno() - 1, QPointF())

class Kind(Enum):
    LINK_NONE = 0
    LINK_GOTO = 1
    LINK_URI = 2
    LINK_LAUNCH = 3
    LINK_NAMED = 4
    LINK_GOTOR = 5

class OutlineItem(QStandardItem):
    def __init__(self, data: list):
        super().__init__()
        self.lvl: int = data[0]
        self.title: str = data[1]
        self.page: int = int(data[2]) - 1

        try:
            self.details: dict = data[3]
        except IndexError as e:
            # data[2] is 1-based source page number
            pass

        self.setData(self.title, role=Qt.ItemDataRole.DisplayRole)

    def getDetails(self):
        return self.details


class OutlineModel(QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def setupModelData(self, outline: list[list]):    
        parents: list[OutlineItem] = []

        prev_child = OutlineItem([0, "", 0, {}])
        parents.append(prev_child)

        for item in outline:
            child = OutlineItem(item)

            if child.lvl == 1:
                parent = self.invisibleRootItem()
            elif child.lvl > prev_child.lvl:
                parents.append(prev_child)
                parent = parents[-1]
            elif child.lvl < prev_child.lvl:
                parents.pop()
                parent = parents[-1]

            parent.appendRow(child)

            prev_child = child

    def setDocument(self, doc: pymupdf.Document):
        self._document = doc
        self.setupModelData(self.getToc())

    def getToc(self):
        toc = self._document.get_toc(simple=False)
        return toc

@dataclass
class GoToLink:
    kind: Kind = Kind.LINK_GOTO
    xref: int = 0
    hotspot: pymupdf.Rect = None
    page_to: int = 0
    to: pymupdf.Point = None
    zoom: float = 1.0
    id: str = ""
    page: InitVar[pymupdf.Page | None] = None
    page_from: int = 0
    label: str = ""

    def __post_init__(self, page: pymupdf.Page):
        self.page_from = page.number
        height_correction = self.hotspot.height * 0.1
        rect = self.hotspot + [0, height_correction, 0, -height_correction]
        label: str = page.get_textbox(rect)
        self.label = label.strip().replace("\n", " ")

@dataclass
class UriLink:
    kind: Kind = Kind.LINK_URI
    xref: int = 0
    hotspot: pymupdf.Rect = None
    uri: str = ""
    id: str = ""
    page: InitVar[pymupdf.Page | None] = None
    page_from: int = 0
    label: str = ""

    def __post_init__(self, page: pymupdf.Page):
        self.page_from = page.number
        height_correction = self.hotspot.height * 0.1
        rect = self.hotspot + [0, height_correction, 0, -height_correction]
        label: str = page.get_textbox(rect)
        self.label = label.strip().replace("\n", " ")

@dataclass
class NamedLink:
    kind: Kind = Kind.LINK_NAMED
    xref: int = 0
    hotspot: pymupdf.Rect = None
    page_to: int = 0
    to: pymupdf.Point = None
    zoom: float = 1.0
    nameddest: str = ""
    id: str = ""
    page: InitVar[pymupdf.Page | None] = None
    page_from: int = 0
    label: str = ""

    def __post_init__(self, page: pymupdf.Page):
        self.page_from = page.number
        height_correction = - self.hotspot.height * 0.1
        rect = self.hotspot + [0, height_correction, 0, -height_correction]
        label: str = page.get_textbox(rect)
        self.label = label.strip().replace("\n", " ")

class LinkFactory:
    def __init__(self):
        self.link_types = {}

        link_type: GoToLink | UriLink | NamedLink
        for link_type in [GoToLink, UriLink, NamedLink]:
            self.link_types[link_type.kind] = link_type

    def createLink(self, link: dict, page: pymupdf.Page) -> GoToLink | UriLink | NamedLink:
        val: GoToLink | UriLink | NamedLink
        # val = self.link_types.get(link['kind'])
        for key, val in self.link_types.items():
            if link['kind'] == key.value:
                return val(*link.values(), page)
            
class LinkItem(QStandardItem):
    def __init__(self, link: GoToLink | UriLink | NamedLink):
        super().__init__()
        self._link = link

        self.setData(self._link.label, role=Qt.ItemDataRole.DisplayRole)
    
    def link(self):
        return self._link

class LinkModel(QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def setDocument(self, doc: pymupdf.Document):
        self._document = doc
        self.setupModelData()

    def setupModelData(self):    
        parent = self.invisibleRootItem()

        link_factory = LinkFactory()

        for page in self._document:
            for link in page.links([pymupdf.LINK_GOTO, pymupdf.LINK_NAMED]):
                link_object = link_factory.createLink(link, page)

                link_item = LinkItem(link_object)
                parent.appendRow(link_item)

class SearchItem(QStandardItem):
    def __init__(self, result: dict):
        super().__init__()

        self.pno = result['pno']
        self.quads = result['quads']
        self.page_label = result['label']

        self.setData(f"index: {self.pno}\tlabel: {self.page_label}", role=Qt.ItemDataRole.DisplayRole)
    
    def results(self):
        return self.pno, self.quads, self.page_label


class SearchModel(QStandardItemModel):
    sigTextFound = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._search_results: dict[int, list] = {}

    def setDocument(self, doc: pymupdf.Document):
        self._document = doc

    def searchFor(self, text: str):
        self.clear()
        self._search_results.clear()
        
        self._found_count = 0

        if text != "":
            root_item = self.invisibleRootItem()
            page: pymupdf.Page
            for page in self._document:
                quads: list = page.search_for(text, quads=True)
                
                if len(quads) > 0:
                    self._found_count = self._found_count + len(quads)
                    page_result = {"pno" : page.number, "label": page.get_label(), "quads" : quads}
                    self._search_results.update({page.number: quads})
                    search_item = SearchItem(page_result)
                    root_item.appendRow(search_item)
        
        self.sigTextFound.emit(f"Hits: {self._found_count}")

    def foundCount(self):
        return self._found_count
    
    def getSearchResults(self):
        return self._search_results
    
class MetaDataWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._metadata = None
        self.metadata_label = QLabel()
        self.metadata_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.metadata_label.setWordWrap(True)
        vbox = QVBoxLayout()
        self.setLayout(vbox)

        vbox.addWidget(self.metadata_label)

        spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum,
                             QSizePolicy.Policy.Expanding)
        vbox.addSpacerItem(spacer)
    
    def setMetadata(self, metadata: dict):
        self._metadata = '\n'.join(f"{key} : {val}" for key, val in metadata.items())
        self.metadata_label.setText(self._metadata.strip())


class TextSelection:
    """ 
        Class that holds the selected text as string and its corresponding quad.
        Quad represents a four-sided mathematical shape (also called “quadrilateral” or “tetragon”) in the plane, defined as a sequence of four Point objects.
        Quad is used to display the selected text.
    """
    def __init__(self, s: str = ""):
        self._text: str = s
        self._quads = []

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, s: str):
        self._text = s

    @property
    def quads(self):
        return self._quads

    @quads.setter
    def quads(self, q):
        self._quads = q

class BaseAnnotation:
    """Base class for annotation"""

    def __init__(self):
        self._pno: int = -1
        self._text: str = ""
        self._zfactor = 1.0

    @property
    def text(self):
        return self._text
    
    @text.setter
    def text(self, s: str):
        self._text = s

    @property
    def pno(self):
        return self._pno
    
    @pno.setter
    def pno(self, i: int):
        self._pno = i 

    @property
    def zfactor(self):
        return self._zfactor
    
    @zfactor.setter
    def zfactor(self, z: float):
        self._zfactor = z


class RectItem(QGraphicsRectItem, BaseAnnotation):
    def __init__(self, parent=None):
        super(RectItem, self).__init__(parent)

        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

class LinkBox(QGraphicsObject):
    sigJumpTo = Signal(int)

    def __init__(self, link: pymupdf.Link, pno: int, zfactor: float, parent=None):
        super(LinkBox, self).__init__(parent)
        self.pno = pno
        self.zfactor = zfactor
        self.to_page: int = link["page"]
        rect: pymupdf.Rect = link["from"]
        a0 = QPointF(rect.x0,rect.y0) * self.zfactor
        b1 = QPointF(rect.x1,rect.y1) * self.zfactor
        self.rect = QRectF(a0, b1)

        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def boundingRect(self):
        return self.rect

    def paint(self, painter, option, widget):
        painter.setPen(QPen(Qt.GlobalColor.cyan))
        painter.drawRect(self.rect)

    def mousePressEvent(self, event):
        self.sigJumpTo.emit(self.to_page)
        event.accept()

class MouseInteraction:

    class InteractionType(Enum):
        NONE = 0
        TEXTSELECTION = 1
        SCREENCAPTURE = 2
        HIGHLIGHT = 3
        WRITESIMPLETEXT = 4 

    def __init__(self, i: InteractionType = InteractionType.NONE):
        self._interaction = i

    @property
    def interaction(self):
        return self._interaction

    @interaction.setter
    def interaction(self, i: InteractionType):
        self._interaction = i

################################################################################
#                             View
################################################################################

class PdfView(QGraphicsView):
    sig_mouse_position = Signal(QPointF)
    sig_annotation_added = Signal(object)
    sig_annotation_removed = Signal('qint64')
    sig_annotation_selected = Signal(object)

    def __init__(self, parent=None):
        super(PdfView, self).__init__(parent)
        # screen = self.window().windowHandle().screen()
        handle = self.window().windowHandle()
        if handle is not None:
            screen = handle.screen()
        else:
            screen = QApplication.primaryScreen()
        self.dpr = screen.devicePixelRatio() if screen else 1.0

        # Mouse coordinate
        self.mouse_interaction = MouseInteraction()
        self.a0 = QPointF()
        self.b1 = QPointF()

        self.graphic_items = {} # dict of QGraphicItem
        self.link_boxes = {} # {pno:[RectItems]}
        self._current_graphic_item = None

        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
    
        self._page_navigator = PageNavigator(parent)
        self._zoom_selector = ZoomSelector(parent)

        self.page_count: int = 0
        self.page_dlist: pymupdf.DisplayList = None
 
        self.annotations = {}

        self.doc_scene = QGraphicsScene(self)
        self.setScene(self.doc_scene)

        self.page_pixmap_item = self.createPixmapItem()
        self.doc_scene.addItem(self.page_pixmap_item)

        self.setBackgroundBrush(QColor(242, 242, 242))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        self.doc_scene.setSceneRect(self.page_pixmap_item.boundingRect()) 
        self.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignHCenter)

        self._page_navigator.currentPnoChanged.connect(self.renderPage) # Render page at init time
        self._page_navigator.currentLocationChanged.connect(self.scrollTo)
    
    def showEvent(self, event: QShowEvent | None) -> None:
        return super().showEvent(event)
    
    def setDocument(self, doc: pymupdf.Document):
        self.fitzdoc: pymupdf.Document = doc
        self._page_navigator.setDocument(self.fitzdoc)
        self.page_count = len(self.fitzdoc)
        self.dlist: list[pymupdf.DisplayList] = [None] * self.page_count
        self._page_navigator._setCurrentPno(0)

    def pageNavigator(self) -> PageNavigator:
        return self._page_navigator
    
    def zoomSelector(self) -> ZoomSelector:
        return self._zoom_selector
    
    @Slot(ZoomSelector.ZoomMode)
    def setZoomMode(self, mode: ZoomSelector.ZoomMode):
        view_width = self.width()
        view_height = self.height()

        content_margins = self.contentsMargins()

        page_width = self.dlist[self.pageNavigator().currentPno()].rect.width
        page_height = self.dlist[self.pageNavigator().currentPno()].rect.height
        
        if mode == ZoomSelector.ZoomMode.FitToWidth:
            self._zoom_selector.zoomFactor = (view_width - content_margins.left() - content_margins.right() - 20) / page_width
            self.renderPage(self.pageNavigator().currentPno())
        elif mode == ZoomSelector.ZoomMode.FitInView:
            self._zoom_selector.zoomFactor = (view_height - content_margins.bottom() - content_margins.top() - 20) / page_height
            self.renderPage(self.pageNavigator().currentPno())
    
    @Slot()
    def zoomIn(self):
        self._zoom_selector.zoomIn()
        self.renderPage(self.pageNavigator().currentPno())
    
    @Slot()
    def zoomOut(self):
        self._zoom_selector.zoomOut()
        self.renderPage(self.pageNavigator().currentPno())

    def toQPixmap(self, fitzpix:pymupdf.Pixmap) -> QPixmap:
        """Convert pymupdf.Pixmap to QtGui.QPixmap"""
        fitzpix_bytes = fitzpix.tobytes()
        pixmap = QPixmap()
        r = pixmap.loadFromData(fitzpix_bytes)
        pixmap.setDevicePixelRatio(self.dpr)
        if not r:
            logger.error(f"Cannot load pixmap from data")
        return pixmap
    
    def createPixmapItem(self, pixmap=None, position=None, matrix=None) -> QGraphicsPixmapItem:
        item = QGraphicsPixmapItem(pixmap)

        if position is not None:
            item.setPos(position)
        if matrix is not None:
            item.setTransform(matrix)
        return item
    
    def createFitzpix(self, page_dlist: pymupdf.DisplayList, zoom_factor=1) -> pymupdf.Pixmap:
        """Create pymupdf.Pixmap applying zoom factor"""
        zf = zoom_factor * self.dpr
        mat = pymupdf.Matrix(zf, zf)  # zoom matrix
        fitzpix: pymupdf.Pixmap = page_dlist.get_pixmap(alpha=0, matrix=mat)
        return fitzpix
    
    def setAnnotations(self, annotations: dict):
        self.annotations.clear()
        self.annotations.update(annotations)

    def renderLinks(self, pno: int):
        boxes: list = self.link_boxes.get(pno)

        if boxes is None:
            boxes: list = []
            page = self.fitzdoc[pno]
            for link in page.links([pymupdf.LINK_GOTO, pymupdf.LINK_NAMED]):
                linkbox = LinkBox(link, pno, self.zoomSelector().zoomFactor)
                linkbox.sigJumpTo.connect(self.onLinkClicked)
                self.doc_scene.addItem(linkbox)
                boxes.append(linkbox)
            self.link_boxes[pno] = boxes
    
    def renderPage(self, pno: int = 0):
        """
            Render the image
            Convert the pymupdf Displaylist to QPixmap
        """
        page_dlist: pymupdf.DisplayList = self.dlist[pno]

        if not page_dlist :  # create if not yet there
            fitzpage = self.fitzdoc.load_page(pno)
            self.dlist[pno] = fitzpage.get_displaylist()
            page_dlist = self.dlist[pno]

        # Remove annotations
        page = self.fitzdoc.load_page(pno)
        self.fitzdoc.xref_set_key(page.xref, "Annots", "null")    

        add_annotations = self.annotations.get(pno)
        if add_annotations is not None:

            quads: pymupdf.Quad
            for quads in add_annotations:
                page.add_highlight_annot(quads)
            page_dlist = page.get_displaylist()

        fitzpix = self.createFitzpix(page_dlist, self._zoom_selector.zoomFactor)
        pixmap = self.toQPixmap(fitzpix)
        self.page_pixmap_item.setPixmap(pixmap)

        self.renderLinks(pno)

        # Show/Hide/Transform graphic annotation items
        items = self.doc_scene.items()
        for item in items:
            if isinstance(item, QGraphicsPixmapItem):
                continue
            elif isinstance(item, QGraphicsLineItem):
                continue
            elif item.pno == pno:
                item.setVisible(True)
                item.setScale(self.zoomSelector().zoomFactor / item.zfactor)
            else:
                item.setVisible(False)
                
        self.centerOn(self.page_pixmap_item)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignCenter)
        self.doc_scene.setSceneRect(self.page_pixmap_item.boundingRect()) 
        self.viewport().update()

    @Slot()
    def setRotation(self, degree):
        """Rotate current page"""
        self.rotate(degree)

    def next(self):
        self.pageNavigator().jump(self.pageNavigator().currentPno() + 1)

    def previous(self):
        self.pageNavigator().jump(self.pageNavigator().currentPno() - 1)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Left:
            self.previous()
        elif event.key() == Qt.Key.Key_Right:
            self.next()

    def wheelEvent(self, event: QWheelEvent) -> None:
        #Zoom : CTRL + wheel
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            anchor = self.transformationAnchor()
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            if event.angleDelta().y() > 0:
                self._zoom_selector.zoomIn()
            else:
                self._zoom_selector.zoomOut()
            while self._zoom_selector.zoomFactor >= self._zoom_selector.max_zoom_factor:
                self._zoom_selector.zoomOut()
            while self._zoom_selector.zoomFactor < self._zoom_selector.min_zoom_factor:
                self._zoom_selector.zoomIn()
            self.renderPage(self.pageNavigator().currentPno())
            self.setTransformationAnchor(anchor)
            # self.doc_view.centerOn(self.doc_view.mapFromGlobal(pointer_position))
        else:
            # Scroll Down
            if event.angleDelta().y() < 0 and self.verticalScrollBar().sliderPosition() == self.verticalScrollBar().maximum():
                if self.pageNavigator().currentPno() < self.fitzdoc.page_count - 1:
                    location = QPointF()
                    location.setY(self.verticalScrollBar().minimum())
                    self.pageNavigator().jump(self.pageNavigator().currentPno() + 1, location)
            # Scroll Up
            elif  event.angleDelta().y() > 0 and self.verticalScrollBar().sliderPosition() == self.verticalScrollBar().minimum():
                if self.pageNavigator().currentPno() > 0:
                    location = QPointF()
                    location.setY(self.verticalScrollBar().maximum())
                    self.pageNavigator().jump(self.pageNavigator().currentPno() - 1, location)
            else:
                self.verticalScrollBar().setValue(self.verticalScrollBar().sliderPosition() - event.angleDelta().y())

    def getPage(self) -> pymupdf.Page:
        """Return Pymupdf current Page"""
        return self.fitzdoc.load_page(self.pageNavigator().currentPno())

    def loadGraphicItems(self, d: dict):
        self.graphic_items = d

    def getGraphicItems(self) -> dict:
        return self.graphic_items
    
    def getSelection(self, pno: int, a0: QPointF, b1: QPointF) -> TextSelection:
        """Return TextSelection from selection points"""
        page: pymupdf.Page = self.fitzdoc.load_page(pno)
        zf = self._zoom_selector.zoomFactor
        rect = pymupdf.Rect(a0.x() / zf, a0.y() / zf, b1.x() / zf, b1.y() / zf)
        text_selection = TextSelection()
        text_selection.text = page.get_textbox(rect)
        return text_selection
    
    @Slot(QPointF)
    def scrollTo(self, location: QPointF | int):
        if isinstance(location, QPointF):
            location = location.toPoint().y()
        self.verticalScrollBar().setValue(location)

    @Slot(int)
    def onLinkClicked(self, pno: int):
        self._page_navigator.jump(pno)

    def mousePressEvent(self, event):
        self.a0 = self.mapToScene(event.position().toPoint())
        self.startMouseInteraction()
        self.update()
        return super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        self.cursor_position = event.position()

        if self._current_graphic_item is not None:
            r = QRectF(self.a0, self.mapToScene(event.position().toPoint())).normalized()
            self._current_graphic_item.setRect(r)
            self.update()
        self.sig_mouse_position.emit(self.mapToScene(event.position().toPoint()))
        return super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        self.b1: QPointF = self.mapToScene(self.cursor_position.toPoint())
        
        if self._current_graphic_item is not None:
            self.endMouseInteraction()
            self.update()
        return super().mouseReleaseEvent(event)
    
    def startMouseInteraction(self):
        if self.mouse_interaction.interaction == MouseInteraction.InteractionType.TEXTSELECTION:
            self._current_graphic_item = RectItem()
            self._current_graphic_item.setPen(QPen(Qt.GlobalColor.red))
            r = QRectF(self.a0, self.a0)
            self._current_graphic_item.setRect(r)
            self._current_graphic_item.pno = self.pageNavigator().currentPno()
            self._current_graphic_item.zfactor = self.zoomSelector().zoomFactor
            self.doc_scene.addItem(self._current_graphic_item)

    def endMouseInteraction(self):
        self._current_graphic_item.text = self.getSelection(self.pageNavigator().currentPno(), self.a0, self.b1)

        # save graphics
        if self._page_navigator.currentPno() in self.graphic_items:
            self.graphic_items[self._page_navigator.currentPno()].update({id(self._current_graphic_item) : self._current_graphic_item})
        else:
            self.graphic_items[self._page_navigator.currentPno()] = {id(self._current_graphic_item) : self._current_graphic_item}

        self.sig_annotation_added.emit(self._current_graphic_item)

        self._current_graphic_item = None

    def keyPressEvent(self, event: QKeyEvent):
        if event == QKeySequence.StandardKey.Delete:
            items = self.doc_scene.selectedItems()
            for item in items:
                self.graphic_items[self._page_navigator.currentPno()].pop(id(item))
                self.sig_annotation_removed.emit(id(item))
                self.doc_scene.removeItem(item)


################################################################################
#                             Viewer
################################################################################


class PdfViewer(QWidget):
    def __init__(self, parent=None):
        super(PdfViewer, self).__init__(parent)
        self.setWindowTitle("Pymupdf4Qt")
        self.initViewer()
        self._filepath = None

    def filepath(self) -> str:
        return self._filepath
    
    @classmethod
    def supportedFormats(cls) -> list[str]:
        return SUPPORTED_FORMART

    def loadDocument(self, filepath: str = ""):
        if filepath == "":
            return
        
        self._filepath = filepath
        self.fitzdoc: pymupdf.Document = pymupdf.Document(filepath)
        self.pdfview.setDocument(self.fitzdoc)
        self.outline_model.setDocument(self.fitzdoc)
        self.search_model.setDocument(self.fitzdoc)
        self.metadata_tab.setMetadata(self.fitzdoc.metadata)

    def initViewer(self):
        self.fold = False
        vbox = QVBoxLayout()

        self.toolbar = QToolBar(self)
        self.toolbar.setFixedHeight(36)

        self.pdfview = PdfView(self)
        self.outline_model = OutlineModel()
        self.search_model = SearchModel()

        # --- Toolbar ---
        self.mouse_action_group = QActionGroup(self)
        self.mouse_action_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        self.mouse_action_group.triggered.connect(self.triggerMouseAction)

        self.text_selector = QAction(theme_icon_manager.get_icon(':text-block'), "Text Selection", self)
        self.text_selector.setCheckable(True)
        self.text_selector.setShortcut(QKeySequence("ctrl+alt+t"))
        self.text_selector.triggered.connect(self.triggerMouseAction)

        self.capture_area = QAction(theme_icon_manager.get_icon(':capture_area'), "Capture", self)
        self.capture_area.setCheckable(True)
        self.capture_area.setShortcut(QKeySequence("ctrl+alt+s"))
        self.capture_area.triggered.connect(lambda: self.triggerMouseAction)

        self.mark_pen = QAction(theme_icon_manager.get_icon(':mark_pen'), "Mark Text", self)
        self.mark_pen.setCheckable(True)
        self.mark_pen.triggered.connect(lambda: self.triggerMouseAction)

        self.mouse_action_group.addAction(self.text_selector)
        self.mouse_action_group.addAction(self.capture_area)
        self.mouse_action_group.addAction(self.mark_pen)

        self.page_navigator = self.pdfview.pageNavigator()
        self.zoom_selector = self.pdfview.zoomSelector()
        
        # Zoom
        self.action_fitwidth = QAction(theme_icon_manager.get_icon(':expand-width-fill'), "Fit Width", self)
        self.action_fitwidth.triggered.connect(self.fitwidth)

        self.action_fitheight = QAction(theme_icon_manager.get_icon(':expand-height-line'), "Fit Height", self)
        self.action_fitheight.triggered.connect(self.fitheight)
        
        # Zoom In/Out
        zoom_in, zoom_out, _ = self.pdfview.zoomSelector().zoomWidgets()
        zoom_in.triggered.connect(self.pdfview.zoomIn)
        zoom_out.triggered.connect(self.pdfview.zoomOut)

        # Rotate
        self.rotate_anticlockwise = QAction(theme_icon_manager.get_icon(":anticlockwise"), "Rotate left", self)
        self.rotate_anticlockwise.setToolTip("Rotate anticlockwise")
        self.rotate_anticlockwise.triggered.connect(lambda: self.pdfview.setRotation(-90))

        self.rotate_clockwise = QAction(theme_icon_manager.get_icon(":clockwise"), "Rotate right", self)
        self.rotate_clockwise.setToolTip("Rotate clockwise")
        self.rotate_clockwise.triggered.connect(lambda: self.pdfview.setRotation(90))

        # Collapse Left pane
        self.fold_left_pane = QAction(theme_icon_manager.get_icon(':sidebar-fold-line'), "Fold pane", self, triggered=self.onFoldLeftSidebarTriggered)

        self.toolbar.addAction(self.fold_left_pane)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.pdfview.pageNavigator().currentpage_lineedit)
        self.toolbar.addAction(self.pdfview.pageNavigator().previous_page)
        self.toolbar.addAction(self.pdfview.pageNavigator().next_page)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_fitwidth)
        self.toolbar.addAction(self.action_fitheight)
        self.toolbar.addAction(zoom_in)
        self.toolbar.addAction(zoom_out)
        self.toolbar.addAction(self.rotate_anticlockwise)
        self.toolbar.addAction(self.rotate_clockwise)
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.toolbar.addWidget(spacer)
        self.toolbar.addAction(self.text_selector)
        self.toolbar.addAction(self.capture_area)
        self.toolbar.addAction(self.mark_pen)
        self.toolbar.addWidget(spacer)
        
        # Left Sidebar
        self.left_pane = QTabWidget(self)
        self.left_pane.setTabPosition(QTabWidget.TabPosition.West)
        self.left_pane.setMovable(False)

        # Outline Tab
        self.outline_tab = QTreeView(self.left_pane)
        self.outline_tab.setModel(self.outline_model)
        self.outline_tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.outline_tab.setHeaderHidden(True)
        self.outline_tab.selectionModel().selectionChanged.connect(self.onOutlineSelected)
        self.left_pane.addTab(self.outline_tab, "Outline")

        # Search Tab
        search_tab = QWidget(self.left_pane)
        search_tab_layout = QVBoxLayout()
        search_tab.setLayout(search_tab_layout)

        self.search_LineEdit = QLineEdit()
        self.search_LineEdit.setPlaceholderText("Find in document")
        self.search_LineEdit.editingFinished.connect(self.searchFor)
        
        self.search_count = QLabel("Hits: ")

        self.search_results = QTreeView(self.left_pane)
        self.search_results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)  # Make ReadOnly
        self.search_results.setModel(self.search_model)
        self.search_results.setHeaderHidden(True)
        self.search_results.setRootIsDecorated(False)
        self.search_results.selectionModel().selectionChanged.connect(self.onSearchResultSelected)

        search_tab_layout.addWidget(self.search_LineEdit)
        search_tab_layout.addWidget(self.search_count)
        search_tab_layout.addWidget(self.search_results)
        self.left_pane.addTab(search_tab, "Search")

        # Metadata
        self.mouse_position = QLabel()         # for debug
        self.mouse_position.setEnabled(False)
        self.pdfview.sig_mouse_position.connect(self.updateMousePositionLabel)
        self.metadata_tab = MetaDataWidget(self.left_pane)
        self.metadata_tab.layout().insertWidget(1, self.mouse_position)
        self.left_pane.addTab(self.metadata_tab, "Metadata")

        # Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.left_pane)
        self.splitter.addWidget(self.pdfview)
        self.splitter_sizes = [100, 700]
        self.splitter.setSizes(self.splitter_sizes)

        vbox.addWidget(self.toolbar)
        vbox.addWidget(self.splitter)
        self.setLayout(vbox)
        
        # Signals
        self.search_model.sigTextFound.connect(self.onSearchFound)

        self.installEventFilter(self.pdfview)

        # Collapse Left Side pane by default
        self.onFoldLeftSidebarTriggered()

    # for debug
    @Slot(QPointF)
    def updateMousePositionLabel(self, pos):
        self.mouse_position.setText(f"x: {pos.x()}, y: {pos.y()}")

    @Slot()
    def triggerMouseAction(self):
        if self.text_selector.isChecked():
            self.pdfview.mouse_interaction.interaction = MouseInteraction.InteractionType.TEXTSELECTION
        elif self.capture_area.isChecked():
            self.pdfview.mouse_interaction.interaction = MouseInteraction.InteractionType.SCREENCAPTURE
        elif self.mark_pen.isChecked():
            self.pdfview.mouse_interaction.interaction = MouseInteraction.InteractionType.HIGHLIGHT
        else:
            self.pdfview.mouse_interaction.interaction = MouseInteraction.InteractionType.NONE

    @Slot(str)
    def onSearchFound(self, count: str):
        self.search_count.setText(count)
        self.pdfview.setAnnotations(self.search_model.getSearchResults())
        self.pdfview.renderPage(self.page_navigator.currentPno())
        self.search_results.resizeColumnToContents(0)

    def pdfViewSize(self) -> QSize:
        idx = self.splitter.indexOf(self.pdfview)
        return self.splitter.widget(idx).size()

    def showEvent(self, event):
        self.pdfview.scrollTo(self.pdfview.verticalScrollBar().minimum())
        super().showEvent(event)

    def eventFilter(self, object: QObject, event: QEvent):
        if object == self and event.type() == QEvent.Type.Wheel:
            return True
        return False
    
    @Slot()
    def searchFor(self):
        self.search_model.searchFor(self.search_LineEdit.text())
    
    @Slot()
    def fitwidth(self):
        self.pdfview.setZoomMode(ZoomSelector.ZoomMode.FitToWidth)

    @Slot()
    def fitheight(self):
        self.pdfview.setZoomMode(ZoomSelector.ZoomMode.FitInView)
    
    @Slot(QItemSelection, QItemSelection)
    def onOutlineSelected(self, selected: QItemSelection, deseleted: QItemSelection):
        for idx in selected.indexes():
            item: OutlineItem = self.outline_tab.model().itemFromIndex(idx)
            if item.details is not None:
                self.page_navigator.jump(item.page)

    @Slot(QItemSelection, QItemSelection)
    def onSearchResultSelected(self, selected: QItemSelection, deseleted: QItemSelection):
        for idx in selected.indexes():
            item: SearchItem = self.search_results.model().itemFromIndex(idx)
            page, quads, page_label = item.results()
            self.page_navigator.jump(page)

    @Slot()
    def onFoldLeftSidebarTriggered(self):
        if not self.fold:
            self.fold = True
        else:
            self.fold = False

        if self.fold:
            self.splitter_sizes = self.splitter.sizes()
            self.splitter.setSizes([0, 800])
            self.fold_left_pane.setIcon(theme_icon_manager.get_icon(':sidebar-unfold-line'))
        else:
            self.fold_left_pane.setIcon(theme_icon_manager.get_icon(':sidebar-fold-line'))
            self.splitter.setSizes(self.splitter_sizes)
