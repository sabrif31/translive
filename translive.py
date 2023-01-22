""" Take a screenshot and copy its text content to the clipboard. """
import argparse
import sys
import cv2
import json
import os
import pyautogui

import pyperclip
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer

from termcolor import colored

import pytesseract
from deep_translator import (GoogleTranslator, DeeplTranslator)
from rich.tree import Tree
from pynput import keyboard

from lib.ocr import ensure_tesseract_installed, get_ocr_result

###############
## Draw zone ##
###############
class Transitive(QtWidgets.QWidget):
    def __init__(self, parent, langs=None, flags=Qt.WindowFlags()):
        super().__init__(parent=parent, flags=flags)
        self.setWindowTitle("TextShot")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog
        )
        self.setWindowState(self.windowState() | Qt.WindowFullScreen)

        self._screen = QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())

        palette = QtGui.QPalette()
        palette.setBrush(self.backgroundRole(), QtGui.QBrush(self.getWindow()))
        self.setPalette(palette)

        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CrossCursor))

        self.start, self.end = QtCore.QPoint(), QtCore.QPoint()
        self.langs = langs

    def setup(self, x, y, width, height):
        path = "config"
        if not os.path.exists(path):
            os.makedirs(path)

        position_settings = {"x": x, "y": y, "width": width, "height": height}

        with open('config/config.json', 'w') as outfile:
            json.dump(position_settings, outfile)

        print('[SAVED] Coordinate is saved')

    def getWindow(self):
        return self._screen.grabWindow(0)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            QtWidgets.QApplication.quit()

        return super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 100))
        painter.drawRect(0, 0, self.width(), self.height())

        if self.start == self.end:
            return super().paintEvent(event)

        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 3))
        painter.setBrush(painter.background())
        painter.drawRect(QtCore.QRect(self.start, self.end))
        return super().paintEvent(event)

    def mousePressEvent(self, event):
        self.start = self.end = event.pos()
        self.update()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()
        return super().mousePressEvent(event)

    def snipOcr(self):
        self.hide()

        ocr_result = self.ocrOfDrawnRectangle()
        if ocr_result:
            return ocr_result

    def hide(self):
        super().hide()
        QtWidgets.QApplication.processEvents()

    def ocrOfDrawnRectangle(self):
        pos1 = [self.start.x(), self.start.y()]
        pos2 = [self.end.x(), self.end.y()]
        width = pos2[0] - pos1[0]
        height = pos2[1] - pos1[1]
        self.setup(self.start.x(), self.start.y(), width, height)

class OneTimeTransitive(Transitive):
    """Take an OCR screenshot once then end execution."""

    def mouseReleaseEvent(self, event):
        if self.start == self.end:
            return super().mouseReleaseEvent(event)

        ocr_result = self.snipOcr()
        if ocr_result:
            pyperclip.copy(ocr_result)
            # log_copied(ocr_result)
            # notify_copied(ocr_result)

        QtWidgets.QApplication.quit()

class IntervalTransitive(Transitive):
    """
    Draw the screenshot rectangle once, then perform OCR there every `interval` ms.
    """
    prevOcrResult = None

    def __init__(self, parent, interval, langs=None, flags=Qt.WindowFlags()):
        super().__init__(parent, langs, flags)
        self.interval = interval

    def mouseReleaseEvent(self, event):
        if self.start == self.end:
            return super().mouseReleaseEvent(event)

        # Take a shot as soon as the rectangle has been drawn
        self.onShotOcrInterval()
        # And then every `self.interval`ms
        self.startShotOcrInterval()

    def startShotOcrInterval(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.onShotOcrInterval)
        self.timer.start(self.interval)

    def onShotOcrInterval(self):
        prev_ocr_result = self.prevOcrResult
        ocr_result = self.snipOcr()

        if not ocr_result:
            print('fail')
            # log_ocr_failure()
            return

        self.prevOcrResult = ocr_result
        if prev_ocr_result == ocr_result:
            return
        else:
            pyperclip.copy(ocr_result)

class Translator(Transitive):
    pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

    current_folder = os.getcwd()
    
    if not os.path.exists(current_folder + '\\img'):
        os.makedirs(current_folder + '\\img')
    path = r'%s\\img\\translate.png' % current_folder

    def __init__(self, box_constant = 416, collect_data = False, mouse_delay = 0.0001, debug = False):
        t = colored('''\n[INFO] PRESS 'F2' TO TRANSLATE\n[INFO] PRESS 'F3' TO QUIT''', "blue")
        print(colored('''\n[INFO] PRESS 'F2' TO TRANSLATE\n[INFO] PRESS 'F3' TO QUIT\n[INFO] PRESS 'F4' TO RESET ALL\n[INFO] PRESS 'F6' TO DELETE CONFIG.json\n[INFO] PRESS 'F7' TO RE-SELECT ZONE AT TRANSLATE''', "blue"))

    def on_take_screenshot(apiKey="", deep_translator="deepl"):
        # Get settings position of the text
        path_exists_config = os.path.exists("config/config.json")
        if path_exists_config: #  and force == False
            with open("config/config.json") as f:
                position_settings = json.load(f)

        image = pyautogui.screenshot(region=(position_settings["x"], position_settings["y"], position_settings["width"], position_settings["height"]))
        image.save(Translator.path)
        img2 = cv2.imread(Translator.path)
        img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2RGB)
        txt = pytesseract.image_to_string(img2)
        
        #################
        ### TRANSLATE ###
        #################
        if deep_translator == 'google':
            translated = GoogleTranslator(source='en', target='fr').translate(text=txt)
        if deep_translator == 'deepl':
            translated = DeeplTranslator(api_key=apiKey, source='en', target='fr', use_free_api=True).translate(txt)  # output -> Weiter so, du bist großartig

        from rich import print
        tree = Tree("\nTranslation")
        tree.add('\n' + translated)
        tree.add(' ')
        print(tree)

    def start(self):
        
        while True:
            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                cv2.destroyAllWindows()
                break

    def clean_up():
        os._exit(0)

arg_parser = argparse.ArgumentParser(description=__doc__)
arg_parser.add_argument(
    "langs",
    nargs="?",
    default="eng",
    help='languages passed to tesseract, eg. "eng+fra" (default: %(default)s)',
)
arg_parser.add_argument(
    "-i",
    "--interval",
    type=int,
    default=None,
    help="select a screen region then take textshots every INTERVAL milliseconds",
)

def take_textshot(langs, interval):
    ensure_tesseract_installed()
    QtCore.QCoreApplication.setAttribute(Qt.AA_DisableHighDpiScaling)
    app = QtWidgets.QApplication(sys.argv)

    window = QtWidgets.QMainWindow()
    if interval != None:
        transitive = IntervalTransitive(window, interval, langs)
        transitive.show()
    else:
        transitive = OneTimeTransitive(window, langs)
        transitive.show()
    app.exec_()
    # sys.exit(app.exec_())


##############
## Settings ##
##############
def setupDeeplApiKey():
    path = "config"
    if not os.path.exists(path):
        os.makedirs(path)

    print("[INFO] Select source translate (required) and set API Key (not required)")
    def prompt(str):
        valid_input = False
        while not valid_input:
            try:
                txt = input(str)
                valid_input = True
            except ValueError:
                print("[!] Invalid Input.")
        return txt

    api_key = prompt("Your API Key: ")
    source_translate = prompt("Select source for translate (deepl, google, etc..): ")
    settings = {"deepl_api_key": api_key, "source_translate": source_translate}

    with open('config/api-key.json', 'w') as outfile:
        json.dump(settings, outfile)
    print("[INFO] Settings configuration complete")


#############
## COMMAND ##
#############
def on_release(key):
    try:
        '''TAKE SCREENSHOT FOR TRANSLATE'''
        if key == keyboard.Key.f2:
            with open("config/api-key.json") as f:
                api_key = json.load(f)
            Translator.on_take_screenshot(apiKey=api_key['deepl_api_key'], deep_translator=api_key['source_translate']) # 18704e15-6cce-db4f-5b88-6928c8529b1f:fx
        '''QUIT'''
        if key == keyboard.Key.f3:
            Translator.clean_up()
        '''REMOVE ALL SETTINGS'''
        if key == keyboard.Key.f4:
            path_exists = os.path.exists("config/config.json")
            if path_exists:
                os.remove("config/config.json")
                os.remove("config/api-key.json")
            print(colored('''[INFO] Config and settings are deleted, restart app for configure''', "green"))
            os._exit(0)
        '''SETUP SETTINGS'''
        if key == keyboard.Key.f6:
            setupDeeplApiKey()
        '''SELECT NEW ZONE'''
        if key == keyboard.Key.f7:
            args = arg_parser.parse_args()
            take_textshot(args.langs, args.interval)
    except NameError:
        pass

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

    print(colored('''
    ___     _______      ________   _______ _____            _   _  _____ _            _______ ____  _____    
    | |    |_   _\ \    / /  ____| |__   __|  __ \     /\   | \ | |/ ____| |        /\|__   __/ __ \|  __ \  
    | |      | |  \ \  / /| |__       | |  | |__) |   /  \  |  \| | (___ | |       /  \  | | | |  | | |__) | 
    | |      | |   \ \/ / |  __|      | |  |  _  /   / /\ \ | . ` |\___ \| |      / /\ \ | | | |  | |  _  /  
    | |____ _| |_   \  /  | |____     | |  | | \ \  / ____ \| |\  |____) | |____ / ____ \| | | |__| | | \ \  
    |______|_____|   \/   |______|    |_|  |_|  \_\/_/    \_\_| \_|_____/|______/_/    \_\_|  \____/|_|  \_\ 
    \n(Neural Network Translate)''', "blue"))

    """Configure API KEY and source Translate"""
    path_exists_settings = os.path.exists("config/api-key.json")
    if not path_exists_settings: #  and force == False
        setupDeeplApiKey()
        
    """Select region on your screen for the area translate"""
    path_exists_config = os.path.exists("config/config.json")
    if not path_exists_config: #  and force == False
        args = arg_parser.parse_args()
        take_textshot(args.langs, args.interval)

    # from lib.translator import Translator
    listener = keyboard.Listener(on_release=on_release)
    listener.start()
    
    global translator
    translator = Translator(collect_data = "collect_data" in sys.argv)
    translator.start()

if __name__ == "__main__":
    main()