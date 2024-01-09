import socket
from pythonosc import osc_packet

class OscSocket:
    def __init__(self, host, port, timeout=0.1):
        print(f"OSC listening on {host}:{port}")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(timeout)
        
    def recv(self):
        try:
            data, addr = self.sock.recvfrom(65535)
        except socket.timeout:
            return None
        packet = osc_packet.OscPacket(data)
        for message in packet.messages:
            return message.message
        
    def close(self):
        self.sock.close()