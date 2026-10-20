import socket
import pickle
import pygame
import sys
import threading
import math
import time

# Network
SERVER_IP = "192.168.107.155"  # CHANGE TO SERVER'S IP
PORT = 5555

# Game
WORLD_SIZE = (1600, 1200)
SCREEN_SIZE = (800, 600)
PLAYER_SPEED = 200
PROJECTILE_SPEED = 5
grid_spacing = 100 

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((SERVER_IP, PORT))

# Get player ID
player_id = pickle.loads(client.recv(1024))["player_id"]
print("You are Player", player_id)

# Setup
pygame.init()
screen = pygame.display.set_mode(SCREEN_SIZE)
pygame.display.set_caption(f"Player {player_id}")
clock = pygame.time.Clock()

# Game state
my_pos = [100 + player_id * 50, 100]
my_vel = [0, 0]
hits = 0
players = [None] * 12  # Stores velocity and last position for each player
projectiles = []
colors = [
    (0,200,255), (255,80,80), (0,255,0), (255,255,0),
    (255,0,255), (0,255,255), (128,0,0), (0,128,0),
    (0,0,128), (128,128,0), (128,0,128), (0,128,128)
]

# Send initial data
client.send(pickle.dumps({
    "position": my_pos,
    "velocity": my_vel
}))

def recv_thread():
    global players, projectiles, my_pos, running
    while True:
        try:
            data = client.recv(4096)
            if not data:
                break
            msg = pickle.loads(data)
            
            if "request_position" in msg:
                # Server requested our position, send it
                client.send(pickle.dumps({
                    "position_update": my_pos,
                    "velocity": my_vel
                }))
            
            if "players" in msg:
                players = msg["players"]
                if players[player_id] is not None:
                    if "force_sync" in msg:
                        # Force sync our position to match server
                        my_pos = players[player_id]["position"]
                    else:
                        my_pos = players[player_id]["position"]
            
            if "shoot_events" in msg:
                for evt in msg["shoot_events"]:
                    evt["time"] = pygame.time.get_ticks()
                    projectiles.append(evt)
        except Exception as e:
            break

threading.Thread(target=recv_thread, daemon=True).start()

def handle_input():
    return my_vel

def shoot():
    mouse_pos = pygame.mouse.get_pos()
    dx = mouse_pos[0] - SCREEN_SIZE[0]//2
    dy = mouse_pos[1] - SCREEN_SIZE[1]//2
    dist = math.hypot(dx, dy)
    if dist == 0: return
    vel = [dx/dist * PROJECTILE_SPEED, dy/dist * PROJECTILE_SPEED]
    client.send(pickle.dumps({
        "shoot": {
            "position": my_pos.copy(),
            "velocity": vel
        }
    }))

def apply_bounds(pos):
    pos[0] = max(20, min(WORLD_SIZE[0]-20, pos[0]))
    pos[1] = max(20, min(WORLD_SIZE[1]-20, pos[1]))
    return pos

# Main game loop
running = True
while running:
    clock.tick(60)
    
    # Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            shoot()
        elif event.type == pygame.KEYDOWN:
            try:
                keys = pygame.key.get_pressed()
                vel = [0, 0]
                if keys[pygame.K_w]: vel[1] = -PLAYER_SPEED
                if keys[pygame.K_s]: vel[1] = PLAYER_SPEED
                if keys[pygame.K_a]: vel[0] = -PLAYER_SPEED
                if keys[pygame.K_d]: vel[0] = PLAYER_SPEED
                client.send(pickle.dumps({"velocity": vel}))
            except:
                pass
        elif event.type == pygame.KEYUP:
            try:
                key = event.key
                vel = [0, 0]
                if key in [pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d]:
                    keys = pygame.key.get_pressed()
                    if keys[pygame.K_w]: vel[1] = -PLAYER_SPEED
                    if keys[pygame.K_s]: vel[1] = PLAYER_SPEED
                    if keys[pygame.K_a]: vel[0] = -PLAYER_SPEED
                    if keys[pygame.K_d]: vel[0] = PLAYER_SPEED
                    client.send(pickle.dumps({"velocity": vel}))
            except:
                pass
    
    try:
        # Drawing
        screen.fill((30, 30, 30))
        
        # Calculate drawing offset
        offset = (
            SCREEN_SIZE[0]//2 - my_pos[0],
            SCREEN_SIZE[1]//2 - my_pos[1]
        )
        
         # Draw grid
        for x in range(0, WORLD_SIZE[0], grid_spacing):
            for y in range(0, WORLD_SIZE[1], grid_spacing):
                screen_x = x + offset[0]
                screen_y = y + offset[1]
                if 0 <= screen_x < SCREEN_SIZE[0] and 0 <= screen_y < SCREEN_SIZE[1]:
                    pygame.draw.circle(screen, (60, 60, 60), (int(screen_x), int(screen_y)), 2)
        
        # Draw world boundary
        pygame.draw.rect(
            screen, (50,50,50),
            (offset[0], offset[1], WORLD_SIZE[0], WORLD_SIZE[1]),
            2
        )
        
        # Draw our player (always at center)
        pygame.draw.circle(
            screen, colors[player_id],
            (SCREEN_SIZE[0]//2, SCREEN_SIZE[1]//2),
            20
        )
        
        # Draw other players
        for pid, p in enumerate(players):
            if p is None or pid == player_id:
                continue
            
            pygame.draw.circle(
                screen, colors[pid],
                (int(p["position"][0] + offset[0]), 
                 int(p["position"][1] + offset[1])),
                20
            )
        
        # Draw projectiles
        for p in projectiles:
            pygame.draw.circle(
                screen, (255,255,0),
                (int(p["position"][0] + offset[0]),
                 int(p["position"][1] + offset[1])),
                5
            )
        


        pygame.display.flip()
    except pygame.error:
        pass  # Ignore drawing errors during window movement
    
    # Update my position based on current velocity
    my_pos[0] += my_vel[0]
    my_pos[1] += my_vel[1]
    my_pos = apply_bounds(my_pos)
    
    # Update projectiles
    now = pygame.time.get_ticks()
    projectiles = [p for p in projectiles if now - p["time"] < 2000]
    for p in projectiles:
        p["position"][0] += p["velocity"][0]
        p["position"][1] += p["velocity"][1]
    
    # Hit detection
    for p in projectiles[:]:
        if p.get("owner") == player_id:
            continue
        dx = p["position"][0] - my_pos[0]
        dy = p["position"][1] - my_pos[1]
        if dx*dx + dy*dy < 400:  # 20px radius
            hits += 1
            projectiles.remove(p)
            if hits >= 3:
                my_pos = [100 + player_id * 50, 100]
                hits = 0
                try:
                    client.send(pickle.dumps({
                        "position_update": my_pos
                    }))
                except:
                    pass

pygame.quit()
client.close()