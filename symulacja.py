import sys
import time
import random
import math
import threading
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QThread, Qt
from PyQt6 import QtGui
from dataclasses import dataclass
from typing import List

@dataclass
class User:
    id: int
    files: List[int]
    time: int

class Worker(QThread):
    progress_signal = pyqtSignal(int, int)
    label_signal = pyqtSignal(int, str) 
    file_signal = pyqtSignal(int, int) 

    def __init__(self, index, get_clients_priority, clients, lock):
        super().__init__()
        self.index = index
        self.working = True
        self.get_clients_priority = get_clients_priority
        self.clients = clients
        self.lock = lock

    def run(self):
        while self.working:
            self.lock.acquire()
            if len(self.clients) > 0:
                index = self.get_clients_priority()
                upload_time = self.clients[index].files[0]
                client_id = self.clients[index].id
                file = self.clients[index].files[0]
                self.clients[index].files.pop(0)
                if len(self.clients[index].files) < 1:
                    self.clients.pop(index)
                self.lock.release()
                
                self.label_signal.emit(self.index, f"Klient {client_id}")
                self.file_signal.emit(self.index, file)

                for i in range(10):
                    if not self.working:
                        break
                    time.sleep(upload_time / 75.0)
                    self.progress_signal.emit(self.index, (i + 1) * 10)
                
                if len(self.clients) == 0:
                    self.progress_signal.emit(self.index, 0)
                    self.label_signal.emit(self.index, "Wolne")
                    self.file_signal.emit(self.index, 0)
            else:
                self.lock.release()
                self.label_signal.emit(self.index, "Wolne")
            time.sleep(0.1)  

    def stop(self):
        self.working = False


class RefreshTableThread(QThread):
    refresh_table_signal = pyqtSignal()

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.working = True

    def run(self):
        while self.working:
            self.refresh_table_signal.emit()
            time.sleep(0.5)

    def stop(self):
        self.working = False

class IncrementTimeThread(QThread):
    def __init__(self, clients, lock):
        super().__init__()
        self.clients = clients
        self.lock = lock
        self.working = False

    def run(self):
        self.working = True
        while self.working:
            self.lock.acquire()
            for client in self.clients:
                client.time += 1
            self.lock.release()
            time.sleep(1)


    def stop(self):
        self.working = False

class Window(QMainWindow):
    def __init__(self):
        super().__init__()

        self.clients = []
        self.workers = []
        self.work = False

        self.setMinimumSize(1080, 640)
        self.setMaximumSize(1080, 640)
        self.centralwidget = QWidget()
        self.setCentralWidget(self.centralwidget)

        labelFont = QtGui.QFont()
        labelFont.setFamily("Arial")
        labelFont.setPointSize(14)
        labelFont.setBold(True)

        labelFont2 = QtGui.QFont()
        labelFont2.setFamily("Arial")
        labelFont2.setPointSize(10)
        labelFont2.setBold(True)

        self.startButton = QPushButton(parent=self.centralwidget)
        self.startButton.setGeometry(550, 15, 200, 40)
        self.startButton.setFont(labelFont)
        self.startButton.setStyleSheet("border-radius : 12px; background-color: #1D1F25; color: white")
        self.startButton.setText("START")
        self.startButton.clicked.connect(self.start_stop)

        self.progressBars = []
        self.clientsLabels = []
        self.fileLabels = []

        for i in range(5):
            folder = QWidget(parent=self.centralwidget)
            folder.setGeometry(10 + 214 * i, 70, 204, 150)
            folder.setStyleSheet("background-color: #1D1F25; border-radius: 15px;")
            label = QLabel(f"Folder {i+1}", folder)
            label.setStyleSheet("background-color: rgba(0, 0, 0, 0); color: #FFFFFF")
            label.setGeometry(10, 10, 204, 20)
            label.setFont(labelFont)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            clientLabel = QLabel("Wolne", folder)
            clientLabel.setStyleSheet("background-color: rgba(0, 0, 0, 0); color: #FFFFFF")
            clientLabel.setGeometry(10, 40, 204, 20)
            clientLabel.setFont(labelFont)
            clientLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.clientsLabels.append(clientLabel)

            fileLabel = QLabel("Rozmiar pliku: 0 MB", folder)
            fileLabel.setStyleSheet("background-color: rgba(0, 0, 0, 0); color: #FFFFFF")
            fileLabel.setGeometry(10, 70, 204, 20)
            fileLabel.setFont(labelFont2)
            fileLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fileLabels.append(fileLabel)

            progressBar = QProgressBar(folder)
            progressBar.setValue(0)
            progressBar.setGeometry(10, 110, 184, 20)
            progressBar.setStyleSheet("background-color: #FFFFFF;")
            self.progressBars.append(progressBar)

        self.clientsTable = QTableWidget(parent=self.centralwidget)
        self.clientsTable.setGeometry(10, 230, 1060, 400)
        self.clientsTable.setRowCount(20)
        self.clientsTable.setColumnCount(3)
        self.clientsTable.setColumnWidth(0, 100)
        self.clientsTable.setColumnWidth(1, 800)
        self.clientsTable.setColumnWidth(2, 140)

        self.addButton = QPushButton(parent=self.centralwidget)
        self.addButton.setGeometry(330, 15, 200, 40)
        self.addButton.setFont(labelFont)
        self.addButton.setStyleSheet("border-radius : 12px; background-color: #1D1F25; color: white")
        self.addButton.setText("DODAJ")
        self.addButton.clicked.connect(lambda: self.add_client())

        for i in range(5):
            self.clients.append(self.generate_random_user())

        self.refresh_table()

        self.refresh_thread = RefreshTableThread(self)
        self.refresh_thread.refresh_table_signal.connect(self.refresh_table)
        self.refresh_thread.start()

        self.increment_time_thread = IncrementTimeThread(self.clients, lock)


    def generate_random_files(self):
        filesNumber = random.randint(1, 10)
        files = []
        for i in range(filesNumber):
            files.append(random.randint(1, 100))
        files.sort()
        return files

    def generate_random_user(self):
        global id
        files = self.generate_random_files()
        time = random.randint(1, 300)
        user = User(id, files, time)
        id += 1
        return user

    def add_client(self):
        user = self.generate_random_user()
        if(len(self.clients)<20):
            lock.acquire()
            self.clients.append(user)
            lock.release()
        if not self.work:
            self.refresh_table()

    def refresh_table(self):
        self.clients.sort(key=lambda x: x.time, reverse = True)

        self.clientsTable.clear()

        xlabels = ["Klient", "Pliki", "Czas oczekiwania"]
        self.clientsTable.setHorizontalHeaderLabels(xlabels)
        self.clientsTable.verticalHeader().setVisible(False)

        for i in range(len(self.clients)):
            user_at_index = self.clients[i]
            files_for_user = ",".join(str(item) for item in user_at_index.files)
            self.clientsTable.setItem(i, 0, QTableWidgetItem(str(user_at_index.id)))
            self.clientsTable.setItem(i, 1, QTableWidgetItem(files_for_user))
            self.clientsTable.setItem(i, 2, QTableWidgetItem(str(user_at_index.time)))

    def get_clients_priority(self):
        client_num = len(self.clients)
        best_index = 0
        best_priority = 0
        for i in range(client_num):
            if len(self.clients[i].files) > 0:
                priority = client_num / self.clients[i].files[0] + math.log(self.clients[i].time)
                if priority > best_priority:
                    best_priority = priority
                    best_index = i
        return best_index

    def start_stop(self):
        if self.work:
            self.stop_threads()
            self.startButton.setText("START")
        else:
            self.start_threads()
            self.startButton.setText("STOP")

    def start_threads(self):
        self.work = True
        self.increment_time_thread.start()
        for i in range(5):
            worker = Worker(i, self.get_clients_priority, self.clients, lock)
            worker.progress_signal.connect(self.update_progress)
            worker.label_signal.connect(self.update_label)
            worker.file_signal.connect(self.update_file)
            worker.start()
            self.workers.append(worker)

    def stop_threads(self):
        self.work = False
        for worker in self.workers:
            worker.stop()
            worker.wait()
        self.workers.clear()
        self.increment_time_thread.stop()
        
        for progressBar in self.progressBars:
            progressBar.setValue(0)

    @pyqtSlot(int, int)
    def update_progress(self, index, value):
        self.progressBars[index].setValue(value)

    @pyqtSlot(int, str)
    def update_label(self, index, text):
        self.clientsLabels[index].setText(text)

    @pyqtSlot(int, int)
    def update_file(self, index, file_size):
        self.fileLabels[index].setText(f"Rozmiar pliku: {file_size} MB")

if __name__ == '__main__':
    id = 1
    lock = threading.Lock()
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())