"""
Shell around Mozilla’s PDF.js

Since QtWebkit doesn’t know about requestFullscreen yet,
I hacked halfway support into it.
"""

import sys
import os.path as p

from argparse import ArgumentParser
from base64 import b64encode
from urllib.parse import urlparse
from functools import partial

from PyQt4.QtGui import QApplication
from PyQt4.QtCore import Qt, QUrl
from PyQt4.QtWebKit import QWebView, QWebSettings
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest

here = partial(p.join, p.dirname(__file__))

with open(here('insert_fullscreen.js')) as f:
	INSERT_FULLSCREEN_JS = f.read()

CSS_URL = here('pdf.js/web/viewer.css')
VIEWER_URL = here('pdf.js/web/viewer.html')


class FullscreenCSSFixer(QNetworkAccessManager):
	"""
	Fixes loaded CSS for hacked implementation of requestFullscreen:
	1. replace peudoclass with class
	2. add style for fullscreen’d element
	"""
	def __init__(self, url):
		super().__init__()
		self.url = url
		
		with open(self.url) as f:
			css = f.read().replace(':fullscreen', '.fullscreen')
		
		# fake maximizing of #viewerContainer
		css += """.fullscreen {
			position: absolute;
			top: 0; left: 0;
			height:100%; width: 100%;
			z-index: 10000;
		}"""
		
		uri = 'data:text/css;charset=utf-8;base64,'
		uri += b64encode(css.encode('utf-8')).decode('utf-8')
		
		self.data_uri = QUrl(uri)
	
	def createRequest(self, op, req, outgoingData=None):
		if req.url().path().endswith(self.url):
			return super().createRequest(QNetworkAccessManager.GetOperation, QNetworkRequest(self.data_uri))
		else:
			return super().createRequest(op, req, outgoingData)

#TODO: canvas.mozPrintCallback


class PDFView(QWebView):
	def __init__(self, url, parent=None):
		super().__init__(parent)
		
		self.access_manager = FullscreenCSSFixer(CSS_URL)
		self.page().setNetworkAccessManager(self.access_manager)
		
		self.page().mainFrame().initialLayoutCompleted.connect(self.extend_window)
		self.titleChanged.connect(self.setWindowTitle)
		
		if urlparse(url).scheme in ('', 'file'):
			url = p.realpath(url)
		
		qurl = QUrl(VIEWER_URL)
		qurl.addQueryItem('file', url)  # TODO: fix http urls
		self.load(qurl)
	
	def extend_window(self):
		self.page().mainFrame().addToJavaScriptWindowObject('view', self)
		self.page().mainFrame().evaluateJavaScript(INSERT_FULLSCREEN_JS)
	
	def keyPressEvent(self, event):
		js = self.page().mainFrame().evaluateJavaScript
		if event.key() == Qt.Key_Escape:
			js('document.exitFullscreen()')
		elif event.key() == Qt.Key_F11:
			if self.windowState() == Qt.WindowFullScreen:
				js('document.exitFullscreen()')
			else:
				js('document.getElementById("viewerContainer").requestFullscreen()')

if __name__ == '__main__':
	app = QApplication(sys.argv)
	
	parser = ArgumentParser()
	parser.add_argument('-d', '--debug', action='store_true', help='Debug applications')
	parser.add_argument('file', help='File to open')
	args = parser.parse_args(app.arguments()[1:])
	
	if args.debug:
		QWebSettings.globalSettings().setAttribute(QWebSettings.DeveloperExtrasEnabled, True)
	
	view = PDFView(args.file)
	view.show()
	
	sys.exit(app.exec())
