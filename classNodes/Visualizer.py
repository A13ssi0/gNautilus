import numpy as np
import pyqtgraph as pg
import socket, ast, threading
from utils.buffer import BufferVisualizer
from utils.server import recv_tcp, recv_udp, wait_for_udp_server, wait_for_tcp_server, send_udp, send_tcp, get_serversPort



class Visualizer:
    def __init__(self, managerPort=25798, lenWindow=10, host='127.0.0.1'): 
        self.name = 'Visualizer'
        self.lenWindow = lenWindow
        self.host = host
        self.last_plot_time = 0
        self.applyCAR = False
        self.scale = 1000
        neededPorts = ['FilteredData', 'InfoDictionary', 'host']
        self.init_sockets(managerPort=managerPort,neededPorts=neededPorts)

        self._stopEvent = threading.Event()


    def init_sockets(self, managerPort, neededPorts):
        portDict = get_serversPort(host=self.host, managerPort=managerPort, neededPorts=neededPorts)
        if portDict['host'] is not None:    self.host = portDict['host']

        self.FilteredPort = portDict['FilteredData']
        self.InfoDictPort = portDict['InfoDictionary']
            

    def close(self):
        self._stopEvent.set()
        self.dataSocket.close()
        self.app.quit()
        print(f"[{self.name}] Closed.")


    def keyPressEvent(self, event):
        if event.key() == pg.QtCore.Qt.Key.Key_F4:  self.close()


    def run(self):
        wait_for_udp_server(self.host, self.InfoDictPort)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            send_udp(sock, (self.host,self.InfoDictPort), "GET_INFO")  
            _, info_str, _ = recv_udp(sock)
            try:
                self.info = ast.literal_eval(info_str)
            except Exception as e:
                print(f"[{self.name}] Failed to parse info: {e}")
                return
            print(f"[{self.name}] Received info dictionary")
            

        self.dataSocket = wait_for_tcp_server(self.host, self.FilteredPort)
        send_tcp(b'FILTERS', self.dataSocket)
        print(f"[{self.name}] Connected. Waiting for data...")
        self.setup()
        print(f"[{self.name}] Starting the visualization")
        self.app.exec()


    def on_number_entered(self):
        if self.filter_checkbox.isChecked():
            hp = self.left_input.text()
            lp = self.right_input.text()
            cutHp = f'/hp{hp}' if hp else ''
            cutLp = f'/lp{lp}' if lp else ''
            message = f'FILTERS{cutHp}{cutLp}'
            send_tcp(message.encode('utf-8'), self.dataSocket)
        else:
            send_tcp('FILTERS', self.dataSocket)

    def on_scale_entered(self):
        self.scale = int(self.input_scale.text())
        

    def on_filter_toggled(self):
        self.on_number_entered()

    def on_car_toggled(self):
        self.applyCAR = self.car_checkbox.isChecked()
        status = "Applying CAR" if self.applyCAR else "Disabling CAR"
        print(f"[{self.name}] {status}")

    def setup(self):
        self.nChannels = len(self.info['channels'])
        bufferSize = self.info['SampleRate'] * self.lenWindow
        self.buffer = BufferVisualizer((bufferSize, self.nChannels))
        self.setupWindow()

    def setupWindow(self):
        pg.setConfigOptions(background='w', foreground='k')
        self.app = pg.mkQApp()
        self.main_widget = pg.QtWidgets.QWidget()
        layout = pg.QtWidgets.QVBoxLayout(self.main_widget)

        # Input row
        input_row = pg.QtWidgets.QHBoxLayout()
        self.filter_checkbox = pg.QtWidgets.QCheckBox("Enable Filters")
        self.filter_checkbox.setChecked(False)
        self.filter_checkbox.stateChanged.connect(self.on_filter_toggled)
        input_row.addWidget(self.filter_checkbox)

        self.left_input = self._create_input("CutOff HighPass:", input_row, self.on_number_entered, placeholder="/")
        self.right_input = self._create_input("CutOff LowPass:", input_row, self.on_number_entered, placeholder="/")

        self.car_checkbox = pg.QtWidgets.QCheckBox("CAR")
        self.car_checkbox.setChecked(False)
        self.car_checkbox.stateChanged.connect(self.on_car_toggled)
        input_row.addWidget(self.car_checkbox)

        self.input_scale = self._create_input("Scale:", input_row, self.on_scale_entered,placeholder="1000")
        input_row.addWidget(self.input_scale)

        input_row.addStretch()

        layout.addLayout(input_row)

        self.win = pg.GraphicsLayoutWidget()
        layout.addWidget(self.win)
        self.main_widget.setLayout(layout)
        self.main_widget.setWindowTitle("Real-time Plot with Inputs")
        self.main_widget.show()

        self.plot = self.win.addPlot()
        self.plot.invertY(True)
        self.plot.setXRange(0, self.buffer.data.shape[0], padding=0)
        self.plot.setYRange(-0.5, self.nChannels-0.5, padding=0)
        self.plot.enableAutoRange(x=False, y=False)

        y_axis = self.plot.getAxis('left')
        custom_ticks = list(zip(np.arange(self.nChannels)[::-1], self.info['channels'][::-1]))
        y_axis.setTicks([custom_ticks])
        y_axis.setStyle(tickLength=0)

        x_axis = self.plot.getAxis('bottom')
        x_axis.setTicks([])

        self.curves = [
            self.plot.plot(pen=pg.mkPen(color=pg.intColor(i), width=1))
            for i in range(self.buffer.data.shape[1])
        ]

        interval = 1000 * self.info['dataChunkSize'] // self.info['SampleRate']
        self.plot_timer = pg.QtCore.QTimer()
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start(max(5, interval // 2))

        self.data_timer = pg.QtCore.QTimer()
        self.data_timer.timeout.connect(self.handle_data)
        self.data_timer.start(1)

        self.main_widget.keyPressEvent = self.keyPressEvent


    def _create_input(self, label_text, layout, function, placeholder="/"):
        label = pg.QtWidgets.QLabel(label_text)
        input_field = pg.QtWidgets.QLineEdit()
        input_field.setFixedWidth(60)
        input_field.setPlaceholderText(placeholder)
        input_field.returnPressed.connect(function)
        layout.addWidget(label)
        layout.addWidget(input_field)
        return input_field


    def update_plot(self):
        data = self.buffer.data
        for i, curve in enumerate(self.curves):
            curve.setData(data[:, i]/self.scale + i)

    def handle_data(self):
        try:
            _, matrix = recv_tcp(self.dataSocket)
            if self.applyCAR:
                matrix -= np.mean(matrix, axis=1, keepdims=True)
            self.buffer.add_data(matrix)

        except Exception as e:
            if not self._stopEvent.is_set(): print("[Visualizer] Error or disconnected:", e)
            self.app.quit()

    def __del__(self):
        if not self._stopEvent.is_set():    self.close()


