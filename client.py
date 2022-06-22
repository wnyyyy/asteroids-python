# fonte: https://realpython.com/asteroids-game-python/
# modificado para suportar diversos players e online

import pickle
import socket
from threading import Lock, Thread
import time
import pygame
from pygame.math import Vector2
from models import Spaceship, Asteroid, Bullet, ServerData, ClientData
from server import Server
from util import load_sprite


class Client:
    def __init__(self, size: Vector2, tick_rate = 120, ip_address = "localhost", lag = 0, port = 5000, difficulty = 1):
        self.size = Vector2(size) # tamanho da tela, deve ser mesmo do server
        self.tick_rate = tick_rate # tempo de processamento do jogo, deve ser mesmo do server
        self.lag = lag # lag artificial, no caso desse cliente criar um servidor
        self.port = port # porta que o servidor é criado, caso esse cliente crie um
        self.ip_address = ip_address # ip a criar servidor, caso esse cliente crie um
        self.difficulty = difficulty # dificuldade do jogo, caso relevante
        pygame.init()
        pygame.display.set_caption("Asteroids")
        self.screen = pygame.display.set_mode(size)  # 972 x 756
        self.clock = pygame.time.Clock()
        self.started = False
        self.lock = Lock() # lock para resolver race conditions entre o cliente e a thread de seu listener
        self._mainMenu()

    # loop para execução do jogo
    def _loop(self):
        while True:
            self._input()
            self._game()
            self._draw()


    # limpa dados do jogo, referente a esse usuário
    def _clear(self):
        self.bullets = []
        self.team = []  # naves de outros players
        self.team_bullets = [] # balas de outros players
        self.asteroids = []

    # inicia o jogo
    def _start_game(self):
        self._clear()
        self.connection.setblocking(True)
        # instancia um listener que recebe dados do servidor em loop
        self.listener_thread = Thread(target=self._server_listener)
        self.listener_thread.setName("Listener cliente - server")
        self.listener_thread.start()
        self._loop()

    # cliente cuida apenas da lógica da nave e das balas do jogador.
    # Importante notar que o jogo parte do princípio que o cliente não irá trapacear,
    # existe a possibilidade de "mentir" para o servidor que o jogador acertou uma bala ou que não foi atingido por um asteroide
    def _game(self):
        self.lock.acquire()
        for game_object in self._get_game_objects():
            game_object.move(self.screen.get_size())
        game_over = False

        # Se a nave colide com um asteroide, o jogador morre.
        # A posição do asteroide a ser considerada pelo evento é a posição que o cliente vê.
        # Desse jeito, num cenário de alta latência, o jogador não vai morrer por conta de um asteroide que não estava em sua tela
        for asteroid in self.asteroids:
            if self.spaceship.collides_with(asteroid):
                game_over = True
                break

        # Se a bala colide com um asteroide, o asteroide é destruído (ou dividido)
        # Assim como acima, a posição a ser considerada é a que o cliente vê.
        # Dessa forma, o cliente informa ao servidor quando atingiu um asteroide, e este divide asteroide.
        hit_asteroids = []
        for bullet in self.bullets[:]:
            for asteroid_index in range(len(self.asteroids)):
                if self.asteroids[asteroid_index].collides_with(bullet):
                    hit_asteroids.append(self.asteroids[asteroid_index].id)
                    del self.asteroids[asteroid_index]
                    self.bullets.remove(bullet)
                    break

        # quando a bala sai pra fora do mapa, deve sair da memória
        for bullet in self.bullets[:]:
            if not self.screen.get_rect().collidepoint(bullet.position):
                self.bullets.remove(bullet)

        # envia dados do cliente para o servidor
        client_data = ClientData(self.spaceship, self.bullets, hit_asteroids, game_over)
        self.lock.release()
        self.connection.send(pickle.dumps(client_data))

    # listener que recebe dados do servidor
    def _server_listener(self):

        # executa enquanto o cliente estiver conectado
        while self.connected:
            try:
                recv = self.connection.recv(2048)
                load = pickle.loads(recv)
                spaceships, bullets, sv_asteroids = self._unpack_server_data(load)
                self.lock.acquire()
                test1 = time.time()
                self.team_bullets = bullets
                self.team = spaceships

                ## algoritmo muito lento (30ms com n=20)
                asteroids = []
                for sv_asteroid in sv_asteroids:
                    new = Asteroid(sv_asteroid[1], sv_asteroid[2], sv_asteroid[3])
                    new.velocity = sv_asteroid[0]
                    asteroids.append(new)
                self.asteroids = asteroids

                ## algoritmo rápido
                # sv_asteroids_id = [asteroid[2] for asteroid in sv_asteroids]
                # cl_asteroids_id = [asteroid.id for asteroid in self.asteroids]
                # destroyed_asteroids =  cl_asteroids_id - sv_asteroids_id
                # new_asteroids = sv_asteroids_id - cl_asteroids_id

                #self.asteroids = asteroids


                print(time.time() - test1)
                self.lock.release()
            except:
                pass

    def _connect(self, ip_address, port):
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # realiza handshake com server
        try:
            connection.connect((ip_address, port))
        except Exception as e:
            print("Conexão falhou")
            print(e)
            quit()
        self.connected = True

        # armazena referencias do servidor
        self.connection = connection

        # recebe id e posição do servidor
        client_id, pos, color = pickle.loads(self.connection.recv(2048))
        # instancia uma nave com o id e posiçao recebidos
        self.spaceship = Spaceship(pos, client_id, color)
        connection.setblocking(False)
        print("Cliente "+str(client_id)+" criou uma nave")

    # renderiza a tela para o cliente
    def _draw(self):
        self.screen.fill((0, 0, 0))

        self.lock.acquire()
        for game_object in self._get_game_objects():
            game_object.draw(self.screen)
        self.lock.release()

        pygame.display.flip()
        self.clock.tick(self.tick_rate)

    def _get_game_objects(self):
        game_objects = [*self.asteroids, *self.bullets, *self.team, *self.team_bullets]

        if self.spaceship:
            game_objects.append(self.spaceship)

        return game_objects

    # handler que capta inputs do client durante o jogo
    def _input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                quit()
            elif self.spaceship:
                if (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE):
                    self.lock.acquire()
                    self.spaceship.shoot(self.bullets.append, len(self.bullets))
                    self.lock.release()

        is_key_pressed = pygame.key.get_pressed()

        if self.spaceship:
            if is_key_pressed[pygame.K_RIGHT]:
                self.spaceship.rotate(clockwise=True)
            elif is_key_pressed[pygame.K_LEFT]: 
                self.spaceship.rotate(clockwise=False)
            if is_key_pressed[pygame.K_UP]:
                self.spaceship.accelerate()
            elif is_key_pressed[pygame.K_DOWN]:
                self.spaceship.brake()

    def _mainMenu(self):
        self._clear()

        # renderiza o menu principal
        scr = self.screen
        scr.fill((0, 0, 0))

        title = load_sprite("Asteroids", self.size.x/9, "sourcecodepro")
        scr.blit(title, ((scr.get_width() - title.get_width()) /
                 2, (scr.get_height() - title.get_height())/3.5))

        menu_rect = pygame.Rect(self.size.x/10, (scr.get_height() -
                                title.get_height())/1.7, self.size.x/1.2, title.get_height())

        txt1 = load_sprite("1 -> Criar sessão",
                           self.size.x/27, "sourcecodepro")
        txt2 = load_sprite("2 -> Se juntar a uma sessão",
                           self.size.x/27, "sourcecodepro")

        scr.blit(txt1, menu_rect)
        scr.blit(txt2, (menu_rect.x, menu_rect.y + txt1.get_height()*1.1))

        pygame.display.flip()

        while self.started == False:
            # handler para inputs no menu
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    quit()
                elif event.type == pygame.KEYDOWN and (event.key == pygame.K_1 or event.key == pygame.K_KP_1):
                    self._create_session(menu_rect)
                elif event.type == pygame.KEYDOWN and (event.key == pygame.K_2 or event.key == pygame.K_KP_2):
                    self._join_session_menu(menu_rect)

        self.clock.tick(15)

    def _create_session(self, menu_rect):
        scr = self.screen
        pygame.Surface.fill(scr, (0, 0, 0), menu_rect)

        txt1 = load_sprite("Quantidade de players: ",
                           self.size.x/27, "sourcecodepro")
        txt2 = load_sprite("(Enter para confirmar)",
                           self.size.x/54, "sourcecodepro")

        scr.blit(txt1, menu_rect)
        scr.blit(txt2, (menu_rect.x*2.2, menu_rect.y + txt1.get_height()))

        input_rect = pygame.Rect(
            txt1.get_width() + menu_rect.x, menu_rect.y, self.size.x/21, txt1.get_height())
        input_qtd_players = ''

        pygame.display.flip()

        # seleciona número de jogadores
        notDone = True
        while notDone:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    quit()
                elif event.type == pygame.KEYDOWN:
                    if (event.key == pygame.K_KP_ENTER or event.key == pygame.K_RETURN) and len(input_qtd_players) > 0:
                        notDone = False
                    elif event.key == pygame.K_BACKSPACE:
                        input_qtd_players = input_qtd_players[:-1]
                        pygame.Surface.fill(scr, (0, 0, 0), input_rect)
                        inpt = load_sprite(
                            input_qtd_players, self.size.x/27, "sourcecodepro")
                        scr.blit(inpt, input_rect)
                        pygame.display.flip()
                    else:
                        key = event.unicode
                        if key.isdigit() and len(input_qtd_players) < 2:
                            if len(input_qtd_players) > 0 or event.unicode != '0':
                                input_qtd_players += event.unicode
                                inpt = load_sprite(
                                    input_qtd_players, self.size.x/27, "sourcecodepro")
                                pygame.Surface.fill(scr, (0, 0, 0), input_rect)
                                scr.blit(inpt, input_rect)
                                pygame.display.flip()

        qtd_players = int(input_qtd_players)

        # instancia o servidor
        host = Server(self.size, qtd_players, self.port, self.ip_address, self.tick_rate, self.lag, self.difficulty)

        server_thread = Thread(target=host.run)
        server_thread.setName("Servidor")
        server_thread.start()

        # se junta a sessão
        self._join_session(menu_rect, host.ip_address, host.port)

    def _join_session(self, menu_rect, ip_address, port):
        scr = self.screen

        # conecta ao servidor
        self._connect(ip_address, port)

        # se junta ao lobby
        pygame.Surface.fill(scr, (0, 0, 0), menu_rect)

        txt1 = load_sprite("Aguardando jogadores...",
                           self.size.x/27, "sourcecodepro")
        txt2 = load_sprite("Conectados: ", self.size.x/27, "sourcecodepro")

        scr.blit(txt1, menu_rect)
        scr.blit(txt2, (menu_rect.x*2.2, menu_rect.y + txt1.get_height()*2))

        input_rect = pygame.Rect(menu_rect.x*2.2 + txt2.get_width(), menu_rect.y + txt1.get_height()*2, self.size.x/10, txt2.get_height())

        pygame.display.flip()

        # aguarda até os jogadores se conectarem ao lobby
        notDone = True
        qtd_connected = 0
        max_players = 1
        full = False
        while notDone:
            # recebe quantos estao conectados
            if full == False:
                try: 
                    qtd_connected, max_players = pickle.loads(self.connection.recv(2048))
                except:
                    time.sleep(0.1)
            full = qtd_connected == max_players
            # se a sala estiver cheia, aguardar os players estarem prontos
            if full == False:
                if qtd_connected != 0:
                    inp = str(qtd_connected) + "/" + str(max_players)
                else:
                    inp = ''
                spr_connected = load_sprite(inp, self.size.x/27, "sourcecodepro")
                pygame.Surface.fill(scr, (0, 0, 0), input_rect)
                scr.blit(spr_connected, input_rect)
                pygame.display.flip()
            else:
                pygame.Surface.fill(scr, (0, 0, 0), menu_rect)
                txt1 = load_sprite("Jogadores conectados!",self.size.x/27, "sourcecodepro")
                txt2 = load_sprite("[Espaço] para inciar...",self.size.x/27, "sourcecodepro")
                scr.blit(txt1, menu_rect)
                scr.blit(txt2, (menu_rect.x, menu_rect.y + txt1.get_height()*1.1))
                pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    quit()
                elif (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and full):
                    # envia para o servidor que esse cliente está pronto
                    self.connection.send(pickle.dumps(True))
                    scr.fill((0, 0, 0))
                    pygame.display.flip()
                    notDone = False

        # aguarda confirmação do server que o jogo começou
        while True:
            try:
                self.connection.recv(2048)
                break
            except:
                time.sleep(0.1)

        # inicia o jogo
        self._start_game()

    def _join_session_menu(self, menu_rect):
        scr = self.screen
        pygame.Surface.fill(scr, (0, 0, 0), menu_rect)

        txt1 = load_sprite("Endereço IP:Porta (ex 127.0.0.1:5000) ",
                           self.size.x/27, "sourcecodepro")
        scr.blit(txt1, menu_rect)
    
        input_rect = pygame.Rect(menu_rect.x + scr.get_width()/4.5, menu_rect.y +
                                txt1.get_height()*1.3, menu_rect.width, menu_rect.height)
        input_addr = ''

        pygame.display.flip()

        # seleciona número de jogadores
        notDone = True
        while notDone:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    quit()
                elif event.type == pygame.KEYDOWN:
                    if (event.key == pygame.K_KP_ENTER or event.key == pygame.K_RETURN) and len(input_addr) > 0:
                        notDone = False
                    elif event.key == pygame.K_BACKSPACE:
                        input_addr = input_addr[:-1]
                        pygame.Surface.fill(scr, (0, 0, 0), input_rect)
                        inpt = load_sprite(
                            input_addr, self.size.x/20, "sourcecodepro")
                        scr.blit(inpt, input_rect)
                        pygame.display.flip()
                    else:
                        input_addr += event.unicode
                        inpt = load_sprite(
                            input_addr, self.size.x/20, "sourcecodepro")
                        pygame.Surface.fill(scr, (0, 0, 0), input_rect)
                        scr.blit(inpt, input_rect)
                        pygame.display.flip()
        
        ip_address, port = input_addr.split(":")
        self._join_session(menu_rect, ip_address, int(port))

    # carrega dados vindo do server
    def _unpack_server_data(self, server_data : ServerData):
        spaceships = []
        for dt_spaceship in server_data.spaceships:
            spaceship = Spaceship(dt_spaceship[1], None, dt_spaceship[3])
            spaceship.direction = dt_spaceship[2]
            spaceship.velocity = dt_spaceship[0]
            spaceships.append(spaceship)
        bullets = []
        for dt_bullet in server_data.bullets:
            bullet = Bullet(dt_bullet[1], dt_bullet[0], 0, dt_bullet[3], 0)
            bullets.append(bullet)
            
        return spaceships, bullets, server_data.asteroids
    