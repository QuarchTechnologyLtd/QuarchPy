from quarchpy.connection_specific.connection_QPS import QpsInterface as qpsInterface
from quarchpy.connection_specific.connection_QIS import QisInterface as qisInterface

class QISConnection: 
     
    def __init__(self, ConString, host, port): 
        self.qis = qisInterface(host, port)     # Create an instance of QisInterface. Before this is ran QIS needs to have been started 
 
 
class PYConnection: 
     
    def __init__(self, ConString): 
        
        # Finds the separator. 
        Pos = ConString.find (':') 
        if Pos == -1:
            raise ValueError ('Please check your module name!') 
        # Get the connection type and target. 
        self.ConnTypeStr = ConString[0:Pos].upper()

        self.ConnTarget = ConString[(Pos+1):]
        if "SERIAL" not in self.ConnTypeStr:
            self.ConnTarget = ConString[(Pos + 1):].upper()

        
        if self.ConnTypeStr.lower() == 'rest': 
            from quarchpy.connection_specific.connection_ReST import ReSTConn
            if "qtl" in self.ConnTarget.lower():
                self.ConnTarget.replace("qtl", "")
            self.connection = ReSTConn(self.ConnTarget)
             
        elif self.ConnTypeStr.lower() == 'usb': 
            from quarchpy.connection_specific.connection_USB import USBConn
            self.connection = USBConn(self.ConnTarget)            
         
        elif self.ConnTypeStr.lower() == 'serial': 
            from quarchpy.connection_specific.connection_Serial import SerialConn 
            self.connection = SerialConn(self.ConnTarget)             
         
        elif self.ConnTypeStr.lower() == 'telnet': 
            from quarchpy.connection_specific.connection_Telnet import TelnetConn
            self.connection = TelnetConn(self.ConnTarget)

        elif self.ConnTypeStr.lower() == 'tcp':
            from quarchpy.connection_specific.connection_TCP import TCPConn
            self.connection = TCPConn(self.ConnTarget)
         
        else: 
            raise ValueError ("Invalid connection type in module string!")  
 
 
class QPSConnection: 
 
    def __init__(self, host, port): 
        self.qps = qpsInterface(host, port)