import socket
import json
import pygame
import sys
import threading
import math
import time

# Network
PORT = 5555

# Game states
WORLD_SIZE = (1600, 1200)
SCREEN_SIZE = (800, 600)
PLAYER_SPEED = 2
SHOOT_COOLDOWN = 50 #
PROJECTILE_SPEED = 5
grid_spacing = 100 
client = None
player_id = None
my_pos = [0, 0]
currentScreen = 'start'
my_vel = [0, 0]
hits = 0
mouse_held = False
last_shot_time = 0 
players = [None] * 9  # Stores velocity and last position for each player
projectiles = []
colors = [
    (0,200,255), (255,80,80), (0,255,0), (255,255,0),
    (255,0,255), (0,255,255), (128,0,0), (0,128,0),
    (0,0,128), (128,128,0), (128,0,128), (0,128,128)
]

ip = "192.168.107.89" #"127.0.0.1"



# Setup
pygame.init()
screen = pygame.display.set_mode(SCREEN_SIZE)
pygame.display.set_caption(f"Start")
clock = pygame.time.Clock()

def drawText(text, size, color, x, y):
    font = pygame.font.SysFont(None, size)
    text_surface = font.render(text, True, color)
    screen.blit(text_surface, (x, y))

def drawButton(text, rect, font_size, base_color, hover_color, text_color=(0,0,0)):
    mouse_pos = pygame.mouse.get_pos()
    is_hovered = rect.collidepoint(mouse_pos)

    color = hover_color if is_hovered else base_color

    # Draw rectangle
    pygame.draw.rect(screen, color, rect, border_radius=8)  # Rounded corners!

    # Draw text centered
    font = pygame.font.SysFont(None, font_size)
    text_surface = font.render(text, True, text_color)
    text_rect = text_surface.get_rect(center=rect.center)
    screen.blit(text_surface, text_rect)

def apply_bounds(pos):
    pos[0] = max(20, min(WORLD_SIZE[0]-20, pos[0]))
    pos[1] = max(20, min(WORLD_SIZE[1]-20, pos[1]))
    return pos

def drawTextCentered(text, size, color, center_x, center_y):
    font = pygame.font.SysFont(None, size)
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=(center_x, center_y))
    screen.blit(text_surface, text_rect)





#connection to the server
def connectionGame(test_ip):
    global my_vel, client, player_id, my_pos

    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((test_ip, PORT))

        client.send("secret123".encode())


        # Get player ID
        player_id = json.loads(client.recv(1024).decode())["player_id"]
        my_pos = [100 + player_id * 50, 100]
        print("You are Player", player_id)
        
        pygame.display.set_caption(f"Player {player_id}")
        
        # Send initial data
        initial_data_sent = False
        for _ in range(5):
            try:
                client.send(json.dumps({
                    "position": my_pos
                }).encode())
                print("my_pos", my_pos)
                initial_data_sent = True
                break
            except:
                time.sleep(0.1)

        if not initial_data_sent:
            print("Failed to send initial data!")
            return False
        print('client connected successfully')
        return True

    except Exception as e:
        print('failed to connect', e)
        return False


def runGame():
    global running, my_pos, projectiles, my_vel, hits, currentScreen
    # Handle events
    
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
                print("dead")
                currentScreen = 'stop'

def recv_thread():
    global players, projectiles, my_pos, running, currentScreen
    print("[recv_thread] Started")

    while True:
        try:
            data = client.recv(4096)
            if not data:
                break
            msg = json.loads(data)

            if "quit" in msg:
                currentScreen = 'stop'
                client.close()

            for i in range(9):
                if i < len(msg["players"]):
                    players[i] = msg["players"][i]
                else:
                    players[i] = None

                if players[player_id] is not None and "force_sync" in msg:
                    my_pos = players[player_id]["position"]

            if "shoot_events" in msg:
                for evt in msg["shoot_events"]:
                    evt["time"] = pygame.time.get_ticks()
                    projectiles.append(evt)

        except Exception as e:
            print(f'Exception in recv_thread: {e}')
            break


def handle_input():
    return my_vel

def shoot():
    global client, projectiles
    mouse_pos = pygame.mouse.get_pos()
    dx = mouse_pos[0] - SCREEN_SIZE[0]//2
    dy = mouse_pos[1] - SCREEN_SIZE[1]//2
    dist = math.hypot(dx, dy)
    if dist == 0: return
    vel = [dx/dist * PROJECTILE_SPEED, dy/dist * PROJECTILE_SPEED]

    # 🔥 Add instantly to own projectiles
    projectiles.append({
        "owner": player_id,
        "position": my_pos.copy(),
        "velocity": vel,
        "time": pygame.time.get_ticks()
    })

    # Then send to server for others
    try:
        client.send(json.dumps({
            "shoot": {
                "position": my_pos.copy(),
                "velocity": vel
            }
        }).encode())
    except:
        print("failed shooting")


def isButtonClicked(rect, event):
    return event.type == pygame.MOUSEBUTTONDOWN and rect.collidepoint(event.pos)

def drawBackground(offset):    
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



#draw screens
def drawLoadingScreen():
    screen.fill((130, 30, 30))
    pygame.display.flip()

start_button_rect = pygame.Rect(300, 250, 200, 60)
def drawStartScreen():
    global currentScreen
    screen.fill((0, 230, 130))
    drawButton("Start Game", start_button_rect, 36, (0, 200, 130), (0, 255, 180), (255, 255, 255))


    pygame.display.flip()

stop_button_rect = pygame.Rect(SCREEN_SIZE[0] - 120, 20, 80, 20)
def drawGamePlay():
    global projectiles, players, hits
    # Drawing
    screen.fill((30, 30, 30))

    drawButton("End Game", stop_button_rect, 18, (200, 50, 50), (255, 100, 100), (255, 255, 255))

    active_players = sum(1 for p in players if p is not None)
    drawText(f"Amount of Players {active_players}", 20, (255,255,255), 20, 20)
    
    # Calculate drawing offset
    offset = (
        SCREEN_SIZE[0]//2 - my_pos[0],
        SCREEN_SIZE[1]//2 - my_pos[1]
    )
    
    drawBackground(offset)

    # Draw our player (always at center)
    pygame.draw.circle(
        screen, colors[player_id],
        (SCREEN_SIZE[0]//2, SCREEN_SIZE[1]//2),
        20
    )
    
    drawTextCentered("YOU", 20, (255,255,255),
    SCREEN_SIZE[0]//2,
    SCREEN_SIZE[1]//2 )

    health = 3 - hits
    bar_width = 30
    bar_height = 3
    pygame.draw.rect(screen, (255,0,0), (SCREEN_SIZE[0]//2 - 15, SCREEN_SIZE[1]//2 + 25, bar_width, bar_height))
    pygame.draw.rect(screen, (0,255,0), (SCREEN_SIZE[0]//2 - 15, SCREEN_SIZE[1]//2 + 25, bar_width * (health/3), bar_height))
    
    # Draw other players
    for pid, p in enumerate(players):
        if p is None or pid == player_id:
            continue
        
        screen_x = int(p["position"][0] + offset[0])
        screen_y = int(p["position"][1] + offset[1])
        
        pygame.draw.circle(
            screen, colors[pid],
            (screen_x, screen_y),
            20
        )
        
        drawText(f"P{pid}", 20, (255,255,255),
            int(p["position"][0] + offset[0] - 8),
            int(p["position"][1] + offset[1] - 6))
        
        health = 3
        bar_x = int(p["position"][0] + offset[0]) - 15
        bar_y = int(p["position"][1] + offset[1]) + 25

        pygame.draw.rect(screen, (255,0,0), (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, (0,255,0), (bar_x, bar_y, bar_width * (health/3), bar_height))
    
    # Draw projectiles
    for p in projectiles:
        pygame.draw.circle(
            screen, (255,255,0),
            (int(p["position"][0] + offset[0]),
                int(p["position"][1] + offset[1])),
            5
        )

    pygame.display.flip()
    
    # Draw projectiles
    for p in projectiles:
        pygame.draw.circle(
            screen, (255,255,0),
            (int(p["position"][0] + offset[0]),
                int(p["position"][1] + offset[1])),
            5
        )
    

    pygame.display.flip()

next_button_rect = pygame.Rect(SCREEN_SIZE[0] // 2 + 20, SCREEN_SIZE[1] // 2 + 40, 120, 20)
next_button_rect1 = pygame.Rect(SCREEN_SIZE[0] // 2 - 140, SCREEN_SIZE[1] // 2 + 40, 120, 20)
def drawStopScreen(): 
    screen.fill((30, 30, 30))

    # Calculate drawing offset
    offset = (
        SCREEN_SIZE[0]//2 - my_pos[0],
        SCREEN_SIZE[1]//2 - my_pos[1]
    )
    
    drawBackground(offset)

    
    drawText("some information", 20, (255,255,255), SCREEN_SIZE[0] // 2 - 40, SCREEN_SIZE[1] // 2 - 20)
    drawButton("Resume Game", next_button_rect, 26, (0, 200, 200), (0, 255, 255), (255, 255, 255))
    drawButton("Back to Start", next_button_rect1, 26, (200, 200, 0), (255, 255, 100), (255, 255, 255))

    pygame.display.flip()
    
def drawGameOverScreen():
    screen.fill((30, 130, 30))
    pygame.display.flip()




#main loop
running = True
while running:
    clock.tick(60)

    # Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif currentScreen == 'start':
            if event.type == pygame.MOUSEBUTTONDOWN and start_button_rect.collidepoint(event.pos):
                if connectionGame(ip):
                    threading.Thread(target=recv_thread, daemon=True).start()
                    currentScreen = 'game'
                else:
                    print("Failed to connect - wrong Ip")

        elif currentScreen == 'game':
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_held = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                mouse_held = False
            
            if event.type == pygame.MOUSEBUTTONDOWN and stop_button_rect.collidepoint(event.pos):
                client.close()
                currentScreen = 'stop'

        elif currentScreen == 'stop':            
            if event.type == pygame.MOUSEBUTTONDOWN and next_button_rect.collidepoint(event.pos):
                if connectionGame(ip):
                    threading.Thread(target=recv_thread, daemon=True).start()
                    
                    my_pos = [100 + player_id * 50, 100]
                    hits = 0
                    try:
                        client.send(json.dumps({
                            "position_update": my_pos
                        }).encode())
                    except:
                        print("failed to send position update")
                    currentScreen = 'game'
                else:
                    print("Failed to connect - worng Ip")
            if event.type == pygame.MOUSEBUTTONDOWN and next_button_rect1.collidepoint(event.pos):
                currentScreen = 'start'
    
               
    # Screen logic
    if currentScreen == 'start':    
        drawStartScreen()
    elif currentScreen == 'game':
        drawGamePlay()
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]: my_pos[1] -= PLAYER_SPEED
        if keys[pygame.K_s]: my_pos[1] += PLAYER_SPEED
        if keys[pygame.K_a]: my_pos[0] -= PLAYER_SPEED
        if keys[pygame.K_d]: my_pos[0] += PLAYER_SPEED

        my_pos = apply_bounds(my_pos)

        try:
            print(my_pos)
            client.send(json.dumps({"position": my_pos}).encode())
        except Exception as e:
            print("failed to send position", e)

        runGame()
        if mouse_held:
            now = pygame.time.get_ticks()
            if now - last_shot_time > SHOOT_COOLDOWN:  # 0.5 seconds = 500 ms
                shoot()
                last_shot_time = now
    elif currentScreen == 'stop':
        client.close()
        drawStopScreen()
        
    elif currentScreen == 'gameOver':
        drawLoadingScreen()



#quit game
pygame.quit()
if client != False:
    client.close()