import random
import socket
import pygame
from pygame.math import Vector2


def load_sprite(char, size, font, trim_x = 0, trim_y = 0, color = (224,224,224)):
    font = pygame.font.SysFont(font, int(size), bold=True)
    sprite = font.render(char, True, color)

    # corta sprite para colisão funcionar corretamente
    offset_x = sprite.get_width() - trim_x
    offset_y = sprite.get_height() - trim_y
    surface = pygame.Surface((offset_x, offset_y), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    surface.blit(sprite, (0, 0), (trim_x/2, trim_y/2, offset_x, offset_y) )

    return surface

def wrap_position(position, size):
    x, y = position
    w, h = size
    return Vector2(x % w, y % h)

def get_random_position(size):
    return Vector2(
        random.randrange(size.x),
        random.randrange(size.y),
    )

def get_random_velocity(min_speed, max_speed):
    speed = random.randint(min_speed, max_speed)
    angle = random.randrange(0, 360)
    return Vector2(speed, 0).rotate(angle)

def create_socket(ip_address, port, max = 1000):
    game_data_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    game_data_connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    game_data_connection.bind((ip_address, port))
    game_data_connection.listen(max)
    return game_data_connection