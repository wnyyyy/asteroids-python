from client import Client

width = 972
ip_address = "localhost"
port = 5000
lag = 0
tick_rate = 120
difficulty = 1

Client = Client((width, width/1.2), tick_rate, ip_address, lag, port, difficulty)