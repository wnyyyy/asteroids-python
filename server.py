# classe de host para um jogo
# instanciada quando um cliente cria uma sessão
# aqui ocorre o processamento dos asteroides, seu percurso de vida e onde nascem novos

import pickle
from threading import Lock, Thread
import time
from webbrowser import get
from pygame import Vector2
import pygame
from util import create_socket, get_random_position
from models import ServerClient, Asteroid, Spaceship, Bullet, ServerData, ClientData

class Server:
    COLORS = [(224,224,224), (0, 252, 67), (245, 0, 0), (99, 112, 255) ,(255, 238, 0), (56, 252, 239), (209, 84, 0), (222, 27, 206)]
    def __init__(self, size: Vector2, qtd_players, port, ip_address = "localhost", tick_rate = 120, lag = 0, difficulty = 1):
        self.tick_rate = tick_rate # tempo de processamento do jogo, deve ser mesmo do cliente
        self.size = Vector2(size) # tamanho da tela do jogo
        self.lag = lag # lag artifical para testes
        self.qtd_players = qtd_players
        self.ip_address = ip_address
        self.port = port
        self.clock = pygame.time.Clock()
        self.clients = []
        self.difficulty = difficulty # não utilizado, tempo para nascer asteroides
        self.spawn_timers = [9999,5,3,1,0.2] # não utilizado, tempo para nascer asteroides
        self.dist_buffer = size.x/7
        self.max_asteroids = 15 # não utilizado, max de asteroides no mapa
        self.lock = Lock() # lock para resolver race conditions
        self.spawn_timer = time.time() # não utilizado, tempo para nascer asteroides
        self._clear() 
        ## a consertar: servidor quebra caso tenha muitos asteroides no mapa
        # self.asteroids= [Asteroid((0,0),1), Asteroid((100,100),2), Asteroid((100,100),3), Asteroid((100,10),4),
        # Asteroid((0,0),5), Asteroid((100,100),12), Asteroid((100,100),4353), Asteroid((100,10),123444),
        # Asteroid((0,0),1123), Asteroid((100,100),232), Asteroid((100,100),32345), Asteroid((100,10),5644),
        # Asteroid((0,0),12), Asteroid((100,100),122), Asteroid((100,100),33445), Asteroid((100,10),4565784),
        # Asteroid((0,0),321), Asteroid((100,100),1412), Asteroid((100,100),2233), Asteroid((100,10),567574)]
        self.asteroids=[Asteroid((0,0),1), Asteroid((100,100),2)]

    # inicia o jogo
    def run(self):
        self._create_connection() # cria a conexão do server e aguarda os clientes conectarem
        self._create_lobby() # cria o lobby da partida e aguarda os jogadores estarem prontos
        self._create_listeners() # cria um listener para cada cliente conectado, cada listener é uma thread
        #self._create_broadcaster() # não testado totalmente, descomentar essa linha faz o broadcast do jogo ser feito numa thread dedicada. lag artificial só funciona desse modo
        time.sleep(0.2)
        #self._spawn_asteroids() # não testado, thread que cria asteroides
        self._loop()

    def _loop(self):
        while True:
            self._game()

    # limpa dados do jogo, referente a partida
    def _clear(self):
        self.bullets = []
        self.asteroids = []
        self.spaceships = [] # no caso do server, guarda as informaçoes referentes a todas as naves

    # server cuida da lógica dos asteroides e o andamento da partida
    def _game(self):
        self.clock.tick(self.tick_rate)
        self.lock.acquire()
        for game_object in self._get_game_objects():
            game_object.move(self.size)
        self.lock.release()
        self._broadcast_game() # anuncia o jogo para os clientes. comentar essa linha caso descomente a 45

    def _get_game_objects(self):
        bullets = [bullet for cl_bullets in self.bullets for bullet in cl_bullets]
        game_objects = [*self.asteroids, *bullets, *self.spaceships]
        return game_objects

    def _spawn_asteroids(self):
        spawner_thread = Thread(target=self._spawner)
        spawner_thread.setName("Server: Spawner")
        spawner_thread.start()        

    def _spawner(self):
        while True:
            time.sleep(self.spawn_timers[self.difficulty])
            for spaceship in self.spaceships:
                not_done = True
                while not_done:
                    pos = get_random_position(self.size)
                    for spaceship in self.spaceships:
                        if abs(pos.x - spaceship.position.x) + abs(pos.y - spaceship.position.y) < self.dist_buffer:
                            break
                        else:
                            not_done = False
                            self.lock.acquire()
                            self.asteroids.append(Asteroid(pos))
                            self.lock.release()             
                

    # cria thread que envia dados para cliente
    def _create_broadcaster(self):
        broadcaster_thread = Thread(target=self._broadcaster)
        broadcaster_thread.setName("Server: Broadcaster")
        broadcaster_thread.start()

    # envia dados do jogo para os clientes
    def _broadcaster(self):
        while True:
            time.sleep(self.lag)
            self.clock.tick(self.tick_rate)
            for client in self.clients:
                spaceships = []
                self.lock.acquire()
                for spaceship in self.spaceships:
                    if spaceship.id != client.id:
                        spaceships.append(spaceship)
                
                bullets = self.bullets[:client.id-1] + self.bullets[client.id:]
                # instancia um objeto ServerData, que será usado para transportar dados pelo socket
                asteroids = self.asteroids
                self.lock.release()

                server_data = ServerData(spaceships, [x for xs in bullets for x in xs], asteroids)
                
                try:
                    client.connection.send(pickle.dumps(server_data))
                except:
                    pass

    def _broadcast_game(self):
        time.sleep(self.lag)
        for client in self.clients:
            spaceships = []
            self.lock.acquire()
            for spaceship in self.spaceships:
                if spaceship.id != client.id:
                    spaceships.append(spaceship)
            
            bullets = self.bullets[:client.id-1] + self.bullets[client.id:]
            # instancia um objeto ServerData, que será usado para transportar dados pelo socket
            asteroids = self.asteroids
            self.lock.release()

            server_data = ServerData(spaceships, [x for xs in bullets for x in xs], asteroids)
            
            try:
                client.connection.send(pickle.dumps(server_data))
            except:
                pass

    # cria a conexão do server e aguarda os clientes conectarem
    def _create_connection(self):
        # cria os sockets necessários
        server = create_socket(self.ip_address, self.port, self.qtd_players)

        while len(self.clients) != self.qtd_players:
            # aguarda a conexão de um player e aceita
            game_data_connection, addr = server.accept()
            # id atribuído para o cliente conectado
            client_id = len(self.clients) + 1
            client = ServerClient(client_id, game_data_connection)
            # guarda referência dessa conexão
            self.clients.append(client)
            print("Server: cliente id "+str(client_id)+ ", endereço " + str(addr[0])+":"+ str(addr[1]) + " conectado")

            # cria um spaceship vinculado a esse cliente via seu ID
            pos = Vector2(self.size.x / 2 + self.size.x/15*client_id, self.size.y / 2)
            if (client_id - 1 <= len(self.COLORS)):
                color = self.COLORS[client_id-1]
            else: color = (100,100,100)
            spaceship = Spaceship(pos, client_id, color)
            self.spaceships.append(spaceship)
            self.bullets.append([])

            # informa o id, posiçao inicial e cor para o cliente conectado construir seu spaceship
            client.connection.send(pickle.dumps([client_id, pos, color]))
            time.sleep(1)
            for cl in self.clients:
                cl.connection.send(pickle.dumps([len(self.clients),self.qtd_players]))

    # recebe informaçoes de cada cliente
    def _client_listener(self, client):
        while True:
            try:
                load = client.connection.recv(2048)
                self.lock.acquire()
                cl_spaceship, cl_bullets, hit_asteroids, game_over = self._unpack_client_data(pickle.loads(load), client.id)
                # deleta todas as balas atiradas por esse spaceship e preenche novamente com os dados recebidos agora, para deletar balas nao usadas mais
                bullets = []
                for cl_bullet in cl_bullets:
                    bullets.append(Bullet(cl_bullet[1], cl_bullet[0], client.id, cl_bullet[3], cl_bullet[2]))
                self.bullets[client.id-1] = bullets
                # atualiza dados do spaceship no server
                for spaceship in self.spaceships:
                    if spaceship.id == client.id:
                        spaceship.velocity = cl_spaceship[0]
                        spaceship.position = cl_spaceship[1]
                        spaceship.direction = cl_spaceship[2]
                # divide asteroides abatidos
                for asteroid in hit_asteroids:
                    #print("hit", asteroid.id)
                    ret = asteroid.split()
                    if (ret != False):
                        asteroid1, asteroid2 = ret
                        #print("new1: ", asteroid1.id)
                        #print("new2: ", asteroid2.id)
                        self.asteroids.append(asteroid1)
                        self.asteroids.append(asteroid2)
                    self.asteroids.remove(asteroid)
                self.lock.release()
            except:
                pass

    # cria um listener para cada cliente conectado, cada listener é uma thread
    def _create_listeners(self):
        for client in self.clients:
            client_thread = Thread(target=self._client_listener, args=(client,))
            client_thread.setName("Listener server - cliente "+str(client.id))
            client_thread.start()

    def _create_lobby(self):
        # a sala está cheia, aguarda input de pronto dos clientes
        for client in self.clients:
            pickle.loads(client.connection.recv(2048))
        # envia confirmação para clientes
        for client in self.clients:
            client.connection.send(pickle.dumps(True))

    # carrega dados vindo do cliente
    def _unpack_client_data(self, client_data : ClientData, id):
        hit_asteroids = []
        for hit_asteroid_id in client_data.hit_asteroids:
            for asteroid in self.asteroids:
                if asteroid.id == hit_asteroid_id:
                    #print("hit", str(asteroid.id))
                    hit_asteroids.append(asteroid)
                    break
        #if len(hit_asteroids) > 0: print(str(hit_asteroids))
        return client_data.spaceship, client_data.bullets, hit_asteroids, client_data.game_over