import socket, ast, threading
from utils.server import TCPServer, recv_udp, recv_tcp, wait_for_udp_server, wait_for_tcp_server, send_udp, send_tcp, emergency_kill
  

HOST = '127.0.0.1'

class Filter:
    def __init__(self, managerPort=25798):
        self.host = HOST
        self.name = 'Filter'
        self.filter = []

        neededPorts = ['InfoDictionary', 'EEGData', 'FilteredData']
        self.init_sockets(managerPort=managerPort,neededPorts=neededPorts)

        threading.Thread(target=emergency_kill, daemon=True).start()


    def init_sockets(self, managerPort, neededPorts):
        portDict = {port: None for port in neededPorts}
        wait_for_udp_server(self.host, managerPort)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
            for port_name in portDict.keys():
                send_udp(udp_sock, (self.host, managerPort), f"GET_PORT/{port_name}")
                _, port_info, _ = recv_udp(udp_sock)
                portDict[port_name] = int(port_info)
        
        self.EEGPort = portDict['EEGData']
        self.InfoDictPort = portDict['InfoDictionary']
        self.Filtered_socket = TCPServer(host=self.host, port=portDict['FilteredData'], serverName=self.name, node=self)


    def run(self):
        self.Filtered_socket.start()

        wait_for_udp_server(self.host, self.InfoDictPort)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
            send_udp(udp_sock, (self.host,self.InfoDictPort), "GET_INFO")  
            _, raw_info, _ = recv_udp(udp_sock)
            try:
                self.info = ast.literal_eval(raw_info) 
            except Exception as e:
                print(f"[{self.name}] Failed to parse info: {e}")
                self.info = {}
        print(f"[{self.name}] Received info dictionary")

        try:
            tcp_sock = wait_for_tcp_server(self.host, self.EEGPort)
            send_tcp(b'', tcp_sock)
            print(f"[{self.name}] Connected to data source. Starting filter loop...")

            while not self.Filtered_socket._stopEvent.is_set():
                try:
                    _, matrix = recv_tcp(tcp_sock)

                    if self.filter: 
                        for filt in self.filter: matrix = filt.filter(matrix)
                
                    try:    self.Filtered_socket.broadcast(matrix)
                    except Exception as e:
                        print(f"[{self.name}] Broadcast error: {e}")
                        self.Filtered_socket._stopEvent.set()

                except Exception as e:
                    if not self.Filtered_socket._stopEvent.is_set():   print(f"[{self.name}] Data processing error: {e}")
                    self.Filtered_socket._stopEvent.set()

                    
        finally:
            tcp_sock.close()
        

    def close(self):
        try:
            self.Filtered_socket.close()
            if self.Filtered_socket.is_alive(): self.Filtered_socket.join(timeout=0.5)
        except Exception as e:
            print(f"[{self.name}] Socket close error: {e}")

    def __del__(self):
        if not self.Filtered_socket._stopEvent.is_set():     self.close()
