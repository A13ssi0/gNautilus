import subprocess, sys, json
from utils.server import get_free_ports, check_free_port


# ---------------------------------------------------------------------------------------------

host = '127.0.0.1'
free_ports = get_free_ports(ip=host, n=6)
genPath = 'c:/Users/aless/Desktop/gNautilus'  # Path to the model
if not check_free_port(host, 25798): raise RuntimeError(f"Port {25798} is not free. Please choose another port.")     # Check if the first port is free
portManagerPort = str(25798)  # Port for the Port Manager

# ---------------------------------------------------------------------------------------------

recFolder = f'{genPath}/data/recordings/'
laplacianPath = f'{genPath}/lapMask16Nautilus.mat'  # Path to the laplacian mask
modelFolder = f'{genPath}/'  # Path to the model

# ---------------------------------------------------------------------------------------------

subjectCode = 'zzRecTest'  # Default subject code
runType =  "" # Default run type
task = 'mi_bfbh'  # Default task

# device = 'UN-2023.07.19'
device = 'test'  # Default device for testing
model = 'test'  # Default model for testing
lenWindowVisualizer = '10' 

# ---------------------------------------------------------------------------------------------

portDict = {}   
portDict['InfoDictionary'] = free_ports[0] 
portDict['EEGData'] = free_ports[1]  
portDict['FilteredData'] = free_ports[2] 
portDict['EventBus'] = free_ports[3] 
portDict['OutputMapper'] = free_ports[4]  
portDict['PercPosX'] = free_ports[5]  


# ---------------------------------------------------------------------------------------------

subprocess.Popen([sys.executable, "launchers\launchPortManager.py", portManagerPort, json.dumps(portDict)]) # F1
subprocess.Popen([sys.executable, "launchers\launchAcquisition.py", device, portManagerPort])  # F2
subprocess.Popen([sys.executable, "launchers\launchFilter.py", portManagerPort])  # F3
subprocess.Popen([sys.executable, "launchers\launchVisualizer.py", portManagerPort, lenWindowVisualizer]) # F4
subprocess.Popen([sys.executable, "launchers\launchRecorder.py", portManagerPort, subjectCode, recFolder, runType, task]) # F5
subprocess.Popen([sys.executable, "launchers\launchClassifier.py", f'{modelFolder}{model}', portManagerPort, laplacianPath]) # F6

