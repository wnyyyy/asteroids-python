## NOME: Vinícius Costalunga Lima

## instalar requirements.txt antes de executar

from client import Client

width = 972 # tamanho da janela, o jogo deve escalar a partir disso, mas não testei
ip_address = "localhost"
port = 5000
lag = 0 # em segundos, recomendado para testar de 0.1~1
tick_rate = 120 # fps que o jogo será rodado
difficulty = 1 # não utilizado no momento

Client = Client((width, width/1.2), tick_rate, ip_address, lag, port, difficulty)