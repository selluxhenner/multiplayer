import socket
import pickle
import pygame
import sys
import threading
import math
import time
import random

# Network
PORT = 5555

# Game states
WORLD_SIZE = (1600, 1200)
SCREEN_SIZE = (800, 600)
PLAYER_SPEED = 2
SHOOT_COOLDOWN = 20
PROJECTILE_SPEED = 5
grid_spacing = 100 
client = False
player_id = None
my_pos = [0, 0]
currentScreen = 'start'
my_vel = [0, 0]
hits = 0
mouse_held = False
last_shot_time = 0 
players = [None] * 9  # Stores velocity and last position for each player
projectiles = []
obstacles = []  # Will be populated from server
colors = [
    (0,200,255), (255,80,80), (0,255,0), (255,255,0),
    (255,0,255), (0,255,255), (128,0,0), (0,128,0),
    (0,0,128), (128,128,0), (128,0,128), (0,128,128)
]



def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google's public DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "Unable to get IP"

# Music player settings
music_files = ['SevenNationArmy.mp3', 'song2.mp3', 'song3.mp3']  # Add your music files here
current_song_index = 0
is_playing = True

# Music player buttons
music_buttons = {
    'prev': pygame.Rect(SCREEN_SIZE[0] - 150, SCREEN_SIZE[1] - 50, 40, 40),
    'play': pygame.Rect(SCREEN_SIZE[0] - 100, SCREEN_SIZE[1] - 50, 40, 40),
    'next': pygame.Rect(SCREEN_SIZE[0] - 50, SCREEN_SIZE[1] - 50, 40, 40)
}

# Initialize Pygame and Mixer
pygame.init()
pygame.mixer.init()
# Load and play music
pygame.mixer.music.load('SevenNationArmy.mp3')
pygame.mixer.music.play(loops=-1)

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
    # Apply bounds for world size
    pos[0] = max(20, min(WORLD_SIZE[0]-20, pos[0]))
    pos[1] = max(20, min(WORLD_SIZE[1]-20, pos[1]))
    
    # Check for player collisions with obstacles
    player_rect = pygame.Rect(pos[0] - 20, pos[1] - 20, 40, 40)  # Player radius is 20
    
    # Store the original position
    original_pos = pos.copy()
    
    # Check X movement first
    pos[0] = original_pos[0] + my_vel[0]
    player_rect.x = pos[0] - 20
    for obstacle in obstacles:
        obstacle_rect = pygame.Rect(obstacle["x"], obstacle["y"], obstacle["width"], obstacle["height"])
        if player_rect.colliderect(obstacle_rect):
            if my_vel[0] > 0:  # Moving right
                pos[0] = obstacle_rect.left - 20
            elif my_vel[0] < 0:  # Moving left
                pos[0] = obstacle_rect.right + 20
            break
    
    # Then check Y movement
    pos[1] = original_pos[1] + my_vel[1]
    player_rect.y = pos[1] - 20
    for obstacle in obstacles:
        obstacle_rect = pygame.Rect(obstacle["x"], obstacle["y"], obstacle["width"], obstacle["height"])
        if player_rect.colliderect(obstacle_rect):
            if my_vel[1] > 0:  # Moving down
                pos[1] = obstacle_rect.top - 20
            elif my_vel[1] < 0:  # Moving up
                pos[1] = obstacle_rect.bottom + 20
            break
    
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

        # Get player ID
        player_id = pickle.loads(client.recv(1024))["player_id"]
        my_pos = [100 + player_id * 50, 100]
        print("You are Player", player_id)
        
        pygame.display.set_caption(f"Player {player_id}")
        
        # Send initial data
        initial_data_sent = False
        for _ in range(5):
            try:
                client.send(pickle.dumps({
                    "position": my_pos
                }))
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

    except:
        print('failed to connect - Invalid IP')
        return False


def runGame():
    global running, my_pos, projectiles, my_vel, hits, currentScreen
    # Handle events
    
    # Update my position based on current velocity
    my_pos[0] += my_vel[0]
    my_pos[1] += my_vel[1]
    my_pos = apply_bounds(my_pos)
    
    # Send position update to server
    try:
        client.send(pickle.dumps({
            "position": my_pos.copy()
        }))
    except:
        print("Failed to send position update")
    
    # Update projectiles
    now = pygame.time.get_ticks()
    projectiles = [p for p in projectiles if now - p["time"] < 2000]
    
    # Check projectile collisions with obstacles and update positions
    for p in projectiles[:]:
        # Update position
        p["position"][0] += p["velocity"][0]
        p["position"][1] += p["velocity"][1]
        
        # Check obstacle collisions
        projectile_rect = pygame.Rect(p["position"][0] - 5, p["position"][1] - 5, 10, 10)
        for obstacle in obstacles:
            obstacle_rect = pygame.Rect(obstacle["x"], obstacle["y"], obstacle["width"], obstacle["height"])
            if projectile_rect.colliderect(obstacle_rect):
                projectiles.remove(p)
                break
        
        # Check if projectile is out of bounds
        if (p["position"][0] < 0 or p["position"][0] > WORLD_SIZE[0] or 
            p["position"][1] < 0 or p["position"][1] > WORLD_SIZE[1]):
            projectiles.remove(p)
    
    # Hit detection with players
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
                currentScreen = 'gameOver'


def recv_thread():
    global players, projectiles, my_pos, running, currentScreen, obstacles
    print("[recv_thread] Started")

    while True:
        try:
            data = client.recv(4096)
            if not data:
                break
            msg = pickle.loads(data)

            if "quit" in msg:
                currentScreen = 'stop'
                client.close()

            # Update all players' positions
            if "players" in msg:
                # Initialize players array if needed
                if len(players) != len(msg["players"]):
                    players = [None] * len(msg["players"])
                
                # Update each player's data
                for i, player_data in enumerate(msg["players"]):
                    if player_data is not None:
                        if players[i] is None:
                            players[i] = {"position": [0, 0]}
                        # Update all players' positions except our own
                        if i != player_id:
                            players[i]["position"] = player_data["position"].copy()
                    else:
                        players[i] = None
                
                # Debug print to see what we received
                print(f"Player {player_id} received positions:", msg["players"])

            if "shoot_events" in msg:
                for evt in msg["shoot_events"]:
                    evt["time"] = pygame.time.get_ticks()
                    projectiles.append(evt.copy())
                    
            if "obstacles" in msg:
                obstacles = msg["obstacles"]

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

    # Add instantly to own projectiles
    projectiles.append({
        "owner": player_id,
        "position": my_pos.copy(),
        "velocity": vel.copy(),
        "time": pygame.time.get_ticks()
    })

    # Then send to server for others
    try:
        client.send(pickle.dumps({
            "shoot": {
                "position": my_pos.copy(),
                "velocity": vel.copy()
            }
        }))
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

    # Draw Obstacles from server data
    for obstacle in obstacles:
        # Screen coordinates for drawing
        screen_x = obstacle["x"] + offset[0]
        screen_y = obstacle["y"] + offset[1]

        if 0 <= screen_x < SCREEN_SIZE[0] and 0 <= screen_y < SCREEN_SIZE[1]:
            # Create obstacle rect for collision detection
            obstacle_rect = pygame.Rect(obstacle["x"], obstacle["y"], obstacle["width"], obstacle["height"])
            # Draw in screen coordinates
            pygame.draw.rect(screen, (255, 0, 0), (screen_x, screen_y, obstacle["width"], obstacle["height"]))


# Button definitions
start_button_rect = pygame.Rect(300, 250, 200, 60)
stop_button_rect = pygame.Rect(SCREEN_SIZE[0] - 120, 20, 80, 20)
next_button_rect = pygame.Rect(SCREEN_SIZE[0] // 2 + 20, SCREEN_SIZE[1] // 2 + 40, 120, 20)
next_button_rect1 = pygame.Rect(SCREEN_SIZE[0] // 2 - 140, SCREEN_SIZE[1] // 2 + 40, 120, 20)

def drawStartScreen():
    global currentScreen
    screen.fill((0, 230, 130))
    drawButton("Start Game", start_button_rect, 36, (0, 200, 130), (0, 255, 180), (255, 255, 255))
    pygame.display.flip()

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
        
        # Convert world coordinates to screen coordinates
        screen_x = int(p["position"][0] + offset[0])
        screen_y = int(p["position"][1] + offset[1])
        
        # Only draw if player is visible on screen
        if 0 <= screen_x < SCREEN_SIZE[0] and 0 <= screen_y < SCREEN_SIZE[1]:
            pygame.draw.circle(
                screen, colors[pid],
                (screen_x, screen_y),
                20
            )
            
            drawText(f"P{pid}", 20, (255,255,255),
                screen_x - 8,
                screen_y - 6)
            
            health = 3
            bar_x = screen_x - 15
            bar_y = screen_y + 25

            pygame.draw.rect(screen, (255,0,0), (bar_x, bar_y, bar_width, bar_height))
            pygame.draw.rect(screen, (0,255,0), (bar_x, bar_y, bar_width * (health/3), bar_height))
    
    # Draw projectiles
    for p in projectiles:
        screen_x = int(p["position"][0] + offset[0])
        screen_y = int(p["position"][1] + offset[1])
        if 0 <= screen_x < SCREEN_SIZE[0] and 0 <= screen_y < SCREEN_SIZE[1]:
            pygame.draw.circle(
                screen, (255,255,0),
                (screen_x, screen_y),
                5
            )

    # Draw music controls
    draw_music_controls()

    pygame.display.flip()

def drawStopScreen(): 
    screen.fill((30, 30, 30))

    # Calculate drawing offset
    offset = (
        SCREEN_SIZE[0]//2 - my_pos[0],
        SCREEN_SIZE[1]//2 - my_pos[1]
    )
    
    drawBackground(offset)
    
    drawText("Game Paused", 20, (255,255,255), SCREEN_SIZE[0] // 2 - 40, SCREEN_SIZE[1] // 2 - 20)
    drawButton("Resume Game", next_button_rect, 26, (0, 200, 200), (0, 255, 255), (255, 255, 255))
    drawButton("Back to Start", next_button_rect1, 26, (200, 200, 0), (255, 255, 100), (255, 255, 255))

    pygame.display.flip()

def drawGameOverScreen():
    screen.fill((30, 130, 30))
    drawTextCentered("Game Over", 48, (255,255,255), SCREEN_SIZE[0]//2, SCREEN_SIZE[1]//2 - 50)
    drawButton("Play Again", next_button_rect, 26, (0, 200, 200), (0, 255, 255), (255, 255, 255))
    drawButton("Back to Start", next_button_rect1, 26, (200, 200, 0), (255, 255, 100), (255, 255, 255))
    pygame.display.flip()

def load_next_song():
    global current_song_index, is_playing
    current_song_index = (current_song_index + 1) % len(music_files)
    pygame.mixer.music.load(music_files[current_song_index])
    if is_playing:
        pygame.mixer.music.play(loops=-1)

def load_prev_song():
    global current_song_index, is_playing
    current_song_index = (current_song_index - 1) % len(music_files)
    pygame.mixer.music.load(music_files[current_song_index])
    if is_playing:
        pygame.mixer.music.play(loops=-1)

def toggle_play_pause():
    global is_playing
    if is_playing:
        pygame.mixer.music.pause()
    else:
        pygame.mixer.music.unpause()
    is_playing = not is_playing

def draw_music_controls():
    # Draw background for music controls
    pygame.draw.rect(screen, (40, 40, 40), (SCREEN_SIZE[0] - 160, SCREEN_SIZE[1] - 60, 160, 60))
    
    # Draw previous button
    drawButton("⏮", music_buttons['prev'], 24, (60, 60, 60), (100, 100, 100), (255, 255, 255))
    
    # Draw play/pause button
    drawButton("⏯" if is_playing else "▶", music_buttons['play'], 24, (60, 60, 60), (100, 100, 100), (255, 255, 255))
    
    # Draw next button
    drawButton("⏭", music_buttons['next'], 24, (60, 60, 60), (100, 100, 100), (255, 255, 255))

# Main loop
running = True
while running:
    clock.tick(60)

    # Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif currentScreen == 'start':
            if event.type == pygame.MOUSEBUTTONDOWN and start_button_rect.collidepoint(event.pos):
                ip = "192.168.107.155"  # Change to your server's IP
                if connectionGame(ip):
                    threading.Thread(target=recv_thread, daemon=True).start()
                    currentScreen = 'game'
                else:
                    print("Failed to connect")

        elif currentScreen == 'game':
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mouse_held = True
                
                # Check music control buttons
                if music_buttons['prev'].collidepoint(event.pos):
                    load_prev_song()
                elif music_buttons['play'].collidepoint(event.pos):
                    toggle_play_pause()
                elif music_buttons['next'].collidepoint(event.pos):
                    load_next_song()
                elif stop_button_rect.collidepoint(event.pos):
                    client.close()
                    currentScreen = 'stop'
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                mouse_held = False

            # Handle movement
            keys = pygame.key.get_pressed()
            if keys[pygame.K_w]: my_vel[1] = -PLAYER_SPEED
            elif keys[pygame.K_s]: my_vel[1] = PLAYER_SPEED
            else: my_vel[1] = 0
            
            if keys[pygame.K_a]: my_vel[0] = -PLAYER_SPEED
            elif keys[pygame.K_d]: my_vel[0] = PLAYER_SPEED
            else: my_vel[0] = 0

        elif currentScreen == 'stop':            
            if event.type == pygame.MOUSEBUTTONDOWN and next_button_rect.collidepoint(event.pos):
                if connectionGame(ip):
                    threading.Thread(target=recv_thread, daemon=True).start()
                    my_pos = [100 + player_id * 50, 100]
                    hits = 0
                    try:
                        client.send(pickle.dumps({
                            "position_update": my_pos
                        }))
                    except:
                        print("failed to send position update")
                    currentScreen = 'game'
                else:
                    print("Failed to connect")
            if event.type == pygame.MOUSEBUTTONDOWN and next_button_rect1.collidepoint(event.pos):
                currentScreen = 'start'

        elif currentScreen == 'gameOver':
            if event.type == pygame.MOUSEBUTTONDOWN and next_button_rect.collidepoint(event.pos):
                if connectionGame(ip):
                    threading.Thread(target=recv_thread, daemon=True).start()
                    my_pos = [100 + player_id * 50, 100]
                    hits = 0
                    currentScreen = 'game'
                else:
                    print("Failed to connect")
            if event.type == pygame.MOUSEBUTTONDOWN and next_button_rect1.collidepoint(event.pos):
                currentScreen = 'start'

    # Screen logic
    if currentScreen == 'start':    
        drawStartScreen()
    elif currentScreen == 'game':
        drawGamePlay()
        runGame()
        if mouse_held:
            now = pygame.time.get_ticks()
            if now - last_shot_time > SHOOT_COOLDOWN:
                shoot()
                last_shot_time = now
    elif currentScreen == 'stop':
        drawStopScreen()
    elif currentScreen == 'gameOver':
        drawGameOverScreen()

#quit game
pygame.quit()
if client != False:
    client.close()
