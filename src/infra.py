import sys
import random
import socket
import threading
from math import gcd
from secret import flag

class Verifier:
    def __init__(self, y, n):
        self.y = y
        self.n = n
        self.previous_ss = set()
        self.previous_zs = set()

    def gen(self) -> int:
        return random.randint(0, 115792089237316195423570985008687907853269984665640564039457584007913129639934)

    def verify(self, s, z, b) -> bool:
        if s in self.previous_ss or z in self.previous_zs:
            print("Bad: repeated s or z")
            return False

        self.previous_ss.add(s)
        self.previous_zs.add(z)

        n = self.n
        y = self.y
        if s == 0:
            print("Bad: s = 0")
            return False
        if gcd(s, n) != 1:
            print("Bad: gcd(s, n) != 1")
            return False
        return pow(z, 2, n) == (s * pow(y, 1 - b, n)) % n


class Chall:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        
    def send(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.conn.send(data + b'\n')
        
    def recv(self):
        return self.conn.recv(1024).strip().decode()
    
    def handle(self):
        try:
            self.send("Welcome user!")
            no = 0 
            passed = 0
            n_rounds = 256

            while no < 100:
                if passed >= 100:
                    self.send("Ok, you have proven yourself. Here is your reward:")
                    self.send(flag)
                    return

                n = 10205316970729431639485797664559886873490701487420041461102004580735751585751742938892976099986403177553363193830393487376567969420541261258134979327616363126253347148610544049807204226284930907503420405166209168541128632688637445870726287383056390377377382107622861504746212131179321468457103686904634978985262225083923899729078173292553918759616384301941301278845655112236714906572052945789912210749004588396399367890793347769585000314877970596365280369362958611301633074434160115833714459835933860197771690614293763100020927442209269135680658111369923029908840001532934157556701107140402652365541506235916261071723
                self.send(f"n = {n}")

                x = random.randrange(1, n)
                y = pow(x, 2, n)
                self.send(f"y = {y}")

                self.send("\nCan you guess the secret? I will give you a chance to prove yourself.")
                self.send("1) yes\n2) no, I can't guess at the moment")
                self.send("Your choice [1/2]: ", end='')
                choice1 = self.recv()
                if choice1 == "2":
                    no += 1
                    continue 

                self.send("Now, Show me that you know the secret message without showing me the secret message!")
                verifier = Verifier(y, n)

                for i in range(n_rounds):
                    self.send("Give me an s: ", end='')
                    try:
                        s = int(self.recv()) % n
                    except ValueError:
                        self.send("Invalid input")
                        return

                    self.send("Here is b:")
                    b = verifier.gen()
                    self.send(str(b))

                    self.send("Are you ready?")
                    self.send("1) yes\n2) no, I am not ready, I need to take a moment\n3) no, I forgot it")
                    self.send("Your choice [1/2/3]: ", end='')
                    choice2 = self.recv()
                    if choice2 == "2":
                        no += 1
                        if no >= 100:
                            return
                        continue
                    elif choice2 == "3":
                        no += 1
                        if no >= 50:
                            return
                        passed = 0
                        break

                    self.send("Give me a z: ", end='')
                    try:
                        z = int(self.recv()) % n
                    except ValueError:
                        self.send("Invalid input")
                        return
                        
                    if verifier.verify(s, z, b % 2):
                        self.send(f"Good, you are telling the truth, but I am still not convinced")
                        passed += 1
                    else:
                        self.send("Invalid!")
                        return
            
            self.send("You have failed to prove yourself")
            
        except Exception as e:
            print(f"Error handling client {self.addr}: {e}")
        finally:
            self.conn.close()
    
    def send(self, data, end='\n'):
        if isinstance(data, str):
            data = data.encode()
        if end:
            data += end.encode() if isinstance(end, str) else end
        self.conn.send(data)


def start_server(host='localhost', port=6101):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"Challenge server started on {host}:{port}")
        print("Waiting for connections...")
        
        while True:
            conn, addr = server_socket.accept()
            print(f"Connection from {addr}")
            handler = Chall(conn, addr)
            client_thread = threading.Thread(target=handler.handle)
            client_thread.daemon = True
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 6101
        
    start_server('localhost', port)