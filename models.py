# fonte: https://realpython.com/asteroids-game-python/#step-4-controlling-game-objects
# modificado para suportar diversos players e online

import uuid
from pygame.math import Vector2
from pygame.transform import rotozoom, rotate
import util

UP = Vector2(0, -1)
DOWN = Vector2(0, 1)
LEFT = Vector2(-1, 0)
RIGHT = Vector2(1, 0)

### modelos referentes a passagem de dados via socket ###
class ServerClient:
    def __init__(self, id, connection):
        self.id = id
        self.connection = connection

# tipo de dado transportado do server para o cliente
class ServerData:
    def __init__(self, spaceships, bullets, asteroids):
        self.spaceships = []
        for spaceship in spaceships:
            self.spaceships.append([spaceship.velocity, spaceship.position, spaceship.direction, spaceship.color])
        self.bullets = []
        for bullet in bullets:
            self.bullets.append([bullet.velocity, bullet.position, bullet.id, bullet.color])
        self.asteroids = []
        for asteroid in asteroids:
            self.asteroids.append([asteroid.velocity, asteroid.position, asteroid.id, asteroid.size])

# tipo de dado transportado do cliente para o server
class ClientData:
    def __init__(self, spaceship, bullets, hit_asteroids, game_over):
        self.spaceship = [spaceship.velocity, spaceship.position, spaceship.direction]
        self.bullets = []
        for bullet in bullets:
            self.bullets.append([bullet.velocity, bullet.position, bullet.id, bullet.color])
        self.hit_asteroids = hit_asteroids
        self.game_over = game_over

### modelos referentes ao jogo ###
class GameObject:
    SPACESHIP_SIZE = 36

    def __init__(self, position, sprite, velocity):
        self.position = Vector2(position)
        self.sprite = sprite
        self.radius = sprite.get_width() / 2
        self.velocity = Vector2(velocity)

    def draw(self, surface):
        #pygame.draw.rect(self.sprite, pygame.Color(255,255,255), [0, 0, self.sprite.get_width(), self.sprite.get_height()], 1)
        blit_position = self.position - Vector2(self.radius)
        surface.blit(self.sprite, blit_position)

    def move(self, size):
        self.position = util.wrap_position(self.position + self.velocity, size)

    def collides_with(self, other_obj):
        distance = self.position.distance_to(other_obj.position)
        return distance < self.radius + other_obj.radius

class Spaceship(GameObject):
    MANEUVERABILITY = 3.2
    ACCELERATION = 0.15
    MAX_SPEED = 3
    COLLISION_RADIUS = 0.3
    BULLET_SPEED = 4
    MAX_BULLETS = 3

    def __init__(self, position, spaceship_id, color):
        self.id = spaceship_id
        self.direction = Vector2(UP)
        self.color = color
        super().__init__(position, util.load_sprite(">", self.SPACESHIP_SIZE, "lucidasans", self.SPACESHIP_SIZE/6, self.SPACESHIP_SIZE/5, color), Vector2(0))
        self.sprite = rotate(self.sprite, 90)
        self.radius = self.radius * self.COLLISION_RADIUS
        self.last_bullet = 0

    def rotate(self, clockwise=True):
        sign = 1 if clockwise else -1
        angle = self.MANEUVERABILITY * sign
        self.direction.rotate_ip(angle)

    def draw(self, surface):
        #pygame.draw.rect(self.sprite, pygame.Color(255,255,255), [0, 0, self.sprite.get_width(), self.sprite.get_height()], 1)
        angle = self.direction.angle_to(UP)
        rotated_surface = rotozoom(self.sprite, angle, 1.0)
        rotated_surface_size = Vector2(rotated_surface.get_size())
        blit_position = self.position - rotated_surface_size * 0.5
        surface.blit(rotated_surface, blit_position)
        
    def accelerate(self):
        vel = self.velocity
        vel += self.direction * self.ACCELERATION
        # calcula velocidade maxima
        sum = abs(vel.x) + abs(vel.y)
        if sum > self.MAX_SPEED:
            dif = sum/self.MAX_SPEED
            vel.x = vel.x / dif
            vel.y = vel.y / dif

        self.velocity = vel
        #print("dirx: %.2f   diry: %.2f     velx: %.2f   vely: %.2f   velt: %.2f" % (self.direction.x, self.direction.y, self.velocity.x, self.velocity.y, abs(self.velocity.x) + abs(self.velocity.y)))
    
    def brake(self):
        self.velocity -= self.velocity * (self.ACCELERATION / 3)

    def shoot(self, create_bullet_callback, num):
        if num < self.MAX_BULLETS:
            # offset pra bala sair do centro da nave
            bullet_x = self.position.x + self.SPACESHIP_SIZE/12
            bullet_y = self.position.y - self.SPACESHIP_SIZE/2.4
            bullet_velocity = self.direction * self.BULLET_SPEED + self.velocity
            bullet = Bullet((bullet_x,bullet_y), bullet_velocity, self.id, self.color)
            create_bullet_callback(bullet)

class Asteroid(GameObject):
    MAX_SPEED = 3
    MIN_SPEED = 1

    def __init__(self, position, id = uuid.uuid1().int, size = 3):
        self.size = size
        self.id = id

        size_to_scale = {
            3: 1,
            2: 0.5,
            1: 0.25
        }

        scale = size_to_scale[size]
        sprite = rotozoom(util.load_sprite("o", self.SPACESHIP_SIZE*15, "consolas", self.SPACESHIP_SIZE*10/15, self.SPACESHIP_SIZE*10/2.1), 0, scale)

        super().__init__(position, sprite, util.get_random_velocity(self.MIN_SPEED, self.MAX_SPEED)/3)

    def split(self):
        if self.size > 1:
            asteroid1 = Asteroid(self.position, uuid.uuid1().int, self.size - 1)
            asteroid2 = Asteroid(self.position, uuid.uuid1().int, self.size - 1)
            return asteroid1, asteroid2
                

class Bullet(GameObject):
    def __init__(self, position, velocity, spaceship_id, color, bullet_id = uuid.uuid1().int):
        self.spaceship_id = spaceship_id
        self.id = bullet_id
        self.color = color
        super().__init__(position, util.load_sprite(".", self.SPACESHIP_SIZE, "consolas", color=color), velocity)

    def move(self, size):
        self.position = self.position + self.velocity