import pygame
import socket
import pickle
import threading
import time
import ctypes

# Constants
PORT = 5555
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google's public DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "Unable to get IP"

local_ip = get_local_ip()
print("local_ip", local_ip)

WORLD_SIZE = (1600, 1200)
MAX_PLAYERS = 9

colors = [
    (0, 200, 255), (255, 80, 80), (0, 255, 0), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (128, 0, 0), (0, 128, 0),
    (0, 0, 128)
]

players = [None] * MAX_PLAYERS
obstacles = []
slow_zones = []
speed_zones = []
projectiles = []

# Pygame setup
pygame.init()
user32 = ctypes.windll.user32
screen_width = user32.GetSystemMetrics(0)
screen_height = user32.GetSystemMetrics(1)-60

screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
SCREEN_SIZE = screen.get_size()
pygame.display.set_caption("Server Overview")
clock = pygame.time.Clock()

def update_scaling():
    global scale_x, scale_y
    scale_x = SCREEN_SIZE[0] / WORLD_SIZE[0]
    scale_y = SCREEN_SIZE[1] / WORLD_SIZE[1]

update_scaling()

def draw_world():
    screen.fill((30, 30, 30))

    # Grid
    for x in range(0, WORLD_SIZE[0], 100):
        pygame.draw.line(screen, (50, 50, 50), (x * scale_x, 0), (x * scale_x, SCREEN_SIZE[1]))
    for y in range(0, WORLD_SIZE[1], 100):
        pygame.draw.line(screen, (50, 50, 50), (0, y * scale_y), (SCREEN_SIZE[0], y * scale_y))

    # Zones
    for z in speed_zones:
        pygame.draw.rect(screen, (0, 255, 0), pygame.Rect(
            z["x"] * scale_x, z["y"] * scale_y, z["width"] * scale_x, z["height"] * scale_y))
    for z in slow_zones:
        pygame.draw.rect(screen, (0, 0, 255), pygame.Rect(
            z["x"] * scale_x, z["y"] * scale_y, z["width"] * scale_x, z["height"] * scale_y))
    for o in obstacles:
        pygame.draw.rect(screen, (255, 0, 0), pygame.Rect(
            o["x"] * scale_x, o["y"] * scale_y, o["width"] * scale_x, o["height"] * scale_y))

    # Players
    for i, p in enumerate(players):
        if p is not None:
            x, y = p["position"]
            pygame.draw.circle(screen, colors[i], (int(x * scale_x), int(y * scale_y)), 10)
            draw_text(f"P{i}", x * scale_x + 12, y * scale_y - 10, (255, 255, 255))

    # Projectiles
    now = time.time()
    for shot in projectiles:
        age = now - shot["spawn_time"]
        if age > 2.0:
            continue
        x = shot["position"][0] + shot["velocity"][0] * age * 60
        y = shot["position"][1] + shot["velocity"][1] * age * 60
        pygame.draw.circle(screen, (255, 255, 0), (int(x * scale_x), int(y * scale_y)), 4)

def draw_text(text, x, y, color):
    font = pygame.font.SysFont(None, 18)
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))

def network_thread():
    global players, obstacles, slow_zones, speed_zones, projectiles

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((local_ip, PORT))

    # Receive initial data
    initial = pickle.loads(s.recv(4096))
    obstacles[:] = initial["obstacles"]
    slow_zones[:] = initial["slow_zones"]
    speed_zones[:] = initial["speed_zones"]

    s.send(pickle.dumps({"position": [0, 0]}))  # Dummy data

    while True:
        try:
            data = s.recv(4096)
            if not data:
                break
            msg = pickle.loads(data)

            if "players" in msg:
                players[:] = msg["players"]

            if "shoot_events" in msg:
                now = time.time()
                for evt in msg["shoot_events"]:
                    evt["spawn_time"] = now
                    projectiles.append(evt)
                projectiles[:] = [p for p in projectiles if now - p["spawn_time"] < 2.0]

        except Exception as e:
            print("Network error:", e)
            break

# Start network thread
threading.Thread(target=network_thread, daemon=True).start()

# Main loop
running = True
while running:
    clock.tick(60)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_F11:
                fullscreen = not fullscreen
                if fullscreen:
                    screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
                else:
                    screen = pygame.display.set_mode((800, 600))
                SCREEN_SIZE = screen.get_size()
                update_scaling()

    draw_world()
    pygame.display.flip()

pygame.quit()
