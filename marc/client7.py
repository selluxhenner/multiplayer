"""
Marc Déteindre 
Kevin Schmidt
CLient file
15 May 2025
Game 2
"""

import socket
import pickle
import pygame
import sys
import threading
import math
import time
import random
import queue # Added for send_queue  172.20.10.2

# Network
PORT = 5555

# Game states
WORLD_SIZE = (1600, 1200)
SCREEN_SIZE = (800, 600)
PLAYER_SPEED = 3
SLOW_SPEED = 0.75  # Reduced to 1/4 of normal speed 172.20.10.4
SPEED_BOOST_FACTOR = 1.5 # Factor to increase speed in speed zones
SHOOT_COOLDOWN = 100
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
slow_zones = []  # Will be populated from server
speed_zones = [] # Will be populated from server

# Thread-safe queue for outgoing messages
send_queue = queue.Queue()
sender_thread_active = threading.Event() # To control the sender thread

input_box = pygame.Rect(300, 180, 200, 40)
input_server_chosen = ''
input_active = False
response_text = ''

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google's public DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "Unable to get IP"


colors = [
    (0,200,255), (255,80,80), (0,255,0), (255,255,0),
    (255,0,255), (0,255,255), (128,0,0), (0,128,0),
    (0,0,128), (128,128,0), (128,0,128), (0,128,128)
]

# Music player settings
music_files = ['DiesIrae.mp3', 'song2.mp3', 'song3.mp3']  # Add your music files here
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
pygame.mixer.music.load('DiesIrae.mp3')
pygame.mixer.music.play(loops=-1)
pygame.mixer.music.set_volume(0.5)

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
    # Store the original position
    original_pos = pos.copy()
    
    # First check X movement
    test_x_pos = [pos[0], original_pos[1]]
    test_x_rect = pygame.Rect(test_x_pos[0] - 20, test_x_pos[1] - 20, 40, 40)
    
    # Then check Y movement
    test_y_pos = [original_pos[0], pos[1]]
    test_y_rect = pygame.Rect(test_y_pos[0] - 20, test_y_pos[1] - 20, 40, 40)
    
    # Check for collisions with obstacles
    for obstacle in obstacles:
        obstacle_rect = pygame.Rect(obstacle["x"], obstacle["y"], obstacle["width"], obstacle["height"])
        
        did_correct_x = False
        did_correct_y = False

        # Check X collision
        if test_x_rect.colliderect(obstacle_rect):
            # If moving right and would collide with left side of obstacle
            if my_vel[0] > 0:
                target_x = obstacle_rect.left - 20
                if pos[0] > target_x: # Ensure correction is necessary
                    pos[0] = target_x
                    did_correct_x = True
            # If moving left and would collide with right side of obstacle
            elif my_vel[0] < 0:
                target_x = obstacle_rect.right + 20
                if pos[0] < target_x: # Ensure correction is necessary
                    pos[0] = target_x
                    did_correct_x = True
        
        # Check Y collision
        if test_y_rect.colliderect(obstacle_rect):
            # If moving down and would collide with top of obstacle
            if my_vel[1] > 0:
                target_y = obstacle_rect.top - 20
                if pos[1] > target_y: # Ensure correction is necessary
                    pos[1] = target_y
                    did_correct_y = True
            # If moving up and would collide with bottom of obstacle
            elif my_vel[1] < 0:
                target_y = obstacle_rect.bottom + 20
                if pos[1] < target_y: # Ensure correction is necessary
                    pos[1] = target_y
                    did_correct_y = True

        # If moving diagonally and collided with a side, stop the other axis of movement
        is_moving_diagonally = (my_vel[0] != 0 and my_vel[1] != 0)
        if is_moving_diagonally:
            if did_correct_x and not did_correct_y:
                # Hit a vertical side, stop Y movement
                pos[1] = my_pos[1] 
            elif did_correct_y and not did_correct_x:
                # Hit a horizontal side, stop X movement
                pos[0] = my_pos[0]
            elif did_correct_x and did_correct_y:
                # Hit a corner, stop all movement for this frame (revert to start-of-frame position)
                pos[0] = my_pos[0]
                pos[1] = my_pos[1]
    
    # Apply world bounds
    pos[0] = max(20, min(WORLD_SIZE[0]-20, pos[0]))
    pos[1] = max(20, min(WORLD_SIZE[1]-20, pos[1]))
    
    return pos

def drawTextCentered(text, size, color, center_x, center_y):
    font = pygame.font.SysFont(None, size)
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=(center_x, center_y))
    screen.blit(text_surface, text_rect)

def sender_thread_func():
    global client, sender_thread_active, send_queue
    print("[Sender Thread] Started")
    while sender_thread_active.is_set():
        try:
            if client and hasattr(client, 'fileno') and client.fileno() != -1:
                data_to_send = send_queue.get(block=True, timeout=0.001)
                try:
                    client.send(pickle.dumps(data_to_send))
                    send_queue.task_done()
                except (socket.error, EOFError, BrokenPipeError) as e:
                    print(f"[Sender Thread] Network send error: {e}. Clearing sender_thread_active.")
                    sender_thread_active.clear()
                    if client:
                        try: client.close()
                        except: pass
                        client = None
                    break
            else:
                if not sender_thread_active.is_set(): break
                time.sleep(0.1)
                if not client or (hasattr(client, 'fileno') and client.fileno() == -1):
                    if sender_thread_active.is_set():
                        print("[Sender Thread] Client became invalid in loop. Clearing sender_thread_active.")
                    sender_thread_active.clear()
                    break
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[Sender Thread] Unexpected error: {e}. Clearing sender_thread_active.")
            sender_thread_active.clear()
            break
    
    print("[Sender Thread] Loop finished. sender_thread_active.is_set():", sender_thread_active.is_set())

def connectionGame():
    global my_vel, client, player_id, my_pos, hits, obstacles, slow_zones, speed_zones, sender_thread_active, response_text, server_chosen
    
    internet_ip = get_local_ip()
    cut_ip = internet_ip.split('.')
    new_ip = f"{cut_ip[0]}.{cut_ip[1]}.{cut_ip[2]}.{server_chosen}"
    print("new_ip", new_ip)
    hits = 0

    try:
        # If there's an existing client, ensure it's closed and sender thread stopped
        if client and client != False:
            try:
                client.close()
            except: pass
        sender_thread_active.clear() # Stop previous sender thread if any

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((new_ip, PORT))

        # Get initial data including player ID and obstacles
        initial_data = pickle.loads(client.recv(4096))
        player_id = initial_data["player_id"]
        obstacles = initial_data["obstacles"]
        slow_zones = initial_data["slow_zones"]
        speed_zones = initial_data.get("speed_zones", []) # Get speed_zones, default to empty list if not present
        my_pos = [100 + player_id * 50, 100]
        print("You are Player", player_id)
        
        pygame.display.set_caption(f"Player {player_id}")
        
        # Send initial data (this can remain a direct send as it's part of connection setup)
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
            if client: client.close()
            client = None
            return False
        print('client connected successfully')
        
        # Start receiver and sender threads
        threading.Thread(target=recv_thread, daemon=True).start()
        sender_thread_active.set() # Signal sender thread to start/run
        threading.Thread(target=sender_thread_func, daemon=True).start()
        
        return True

    except Exception as e: # Broader exception catch for connection issues
        print(f'[connectionGame] Exception: {e}. Closing client and clearing sender_thread_active.')
        if client:
            try:
                client.close()
            except: pass
        client = None
        sender_thread_active.clear()
        return False


def runGame():
    global running, my_pos, projectiles, my_vel, hits, currentScreen
    
    player_rect = pygame.Rect(my_pos[0] - 20, my_pos[1] - 20, 40, 40)
    
    # Check if player is in slow zone
    in_slow_zone = False
    for zone in slow_zones:
        zone_rect = pygame.Rect(zone["x"], zone["y"], zone["width"], zone["height"])
        if player_rect.colliderect(zone_rect):
            in_slow_zone = True
            break
            
    # Check if player is in speed zone (only if not in slow zone)
    in_speed_zone = False
    if not in_slow_zone:
        for zone in speed_zones:
            zone_rect = pygame.Rect(zone["x"], zone["y"], zone["width"], zone["height"])
            if player_rect.colliderect(zone_rect):
                in_speed_zone = True
                break
    
    # Calculate current speed
    current_speed_multiplier = 1.0
    if in_slow_zone:
        current_speed_multiplier = SLOW_SPEED / PLAYER_SPEED
    elif in_speed_zone:
        current_speed_multiplier = SPEED_BOOST_FACTOR
    
    # Calculate new position based on effective speed
    effective_player_speed = PLAYER_SPEED * current_speed_multiplier
    new_pos = [
        my_pos[0] + my_vel[0] * (effective_player_speed / PLAYER_SPEED if PLAYER_SPEED != 0 else 0),
        my_pos[1] + my_vel[1] * (effective_player_speed / PLAYER_SPEED if PLAYER_SPEED != 0 else 0)
    ]
    
    # Apply bounds and collision detection
    my_pos = apply_bounds(new_pos)
    
    # Send position update to server via queue
    try:
        if sender_thread_active.is_set(): # Only queue if sender is supposed to be active
            send_queue.put({"position": my_pos.copy()})
        else:
            print("Sender thread not active, not sending position.")
    except Exception as e: # Catch potential queue errors, though rare for put
        print(f"Failed to queue position update: {e}")
    
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
                if sender_thread_active.is_set():
                    send_queue.put({"dead": True})
                    
                currentScreen = 'gameOver'


def recv_thread():
    global players, projectiles, my_pos, running, currentScreen, client, sender_thread_active
    print("[recv_thread] Started")

    if client and hasattr(client, 'fileno') and client.fileno() != -1:
        try:
            client.settimeout(0.1)  # Set a 100ms timeout for recv
        except (OSError, AttributeError) as e:
            print(f"[recv_thread] Could not set timeout: {e}. Clearing sender_thread_active.")
            sender_thread_active.clear()
            if client and client != False: 
                try: client.close()
                except: pass
            client = None
            print("[recv_thread] Stopped due to timeout setting failure.")
            return
    else:
        print(f"[recv_thread] Client invalid at start ({client=}). Clearing sender_thread_active.")
        sender_thread_active.clear() # Ensure sender thread is also signaled if client is bad from start
        print("[recv_thread] Stopped due to client invalid at start.")
        return

    while sender_thread_active.is_set():
        if not client or (hasattr(client, 'fileno') and client.fileno() == -1):
            print("[recv_thread] Client became invalid in loop. Clearing sender_thread_active.")
            sender_thread_active.clear()
            break
        try:
            data = client.recv(4096)
            if not data:
                print("[recv_thread] Connection closed by server (recv returned no data). Clearing sender_thread_active.")
                currentScreen = 'stop' 
                sender_thread_active.clear()
                if client: 
                    try: client.close()
                    except: pass
                client = None
                break
            
            msg = pickle.loads(data)

            if "quit" in msg:
                print("[recv_thread] Received quit signal from server. Clearing sender_thread_active.")
                currentScreen = 'stop'
                sender_thread_active.clear()
                if client: 
                    try: client.close()
                    except: pass
                client = None
                break

            if "players" in msg:
                # Initialize players array if needed or if size mismatches
                if len(players) != len(msg["players"]):
                    # This resizes based on server data. Consider implications if server sends unexpected player counts.
                    # For now, assuming it's manageable and less than or equal to available colors.
                    players = [None] * len(msg["players"])
                
                for i, player_data in enumerate(msg["players"]):
                    if i >= len(players): # Safety break if msg["players"] is unexpectedly large post-check
                        print(f"[recv_thread] Warning: Player index {i} out of bounds for current players list size {len(players)}.")
                        break
                    
                    if player_data is not None:
                        if players[i] is None:
                            players[i] = {"position": [0, 0]} # Initialize if new
                        
                        if i != player_id: # Ensure not updating self
                             players[i]["position"] = player_data["position"].copy()
                    else: # If player_data is None
                        players[i] = None

            if "shoot_events" in msg:
                for evt in msg["shoot_events"]:
                    evt["time"] = pygame.time.get_ticks() # Add timestamp on reception
                    projectiles.append(evt.copy())

        except socket.timeout:
            continue 
        except (EOFError, pickle.UnpicklingError, ConnectionResetError, BrokenPipeError) as e:
            print(f'[recv_thread] Network or data error in loop: {e}. Clearing sender_thread_active.')
            sender_thread_active.clear()
            if client: 
                try: client.close()
                except: pass
            client = None
            break
        except Exception as e:
            print(f'[recv_thread] Unexpected exception in loop: {e}. Clearing sender_thread_active.')
            sender_thread_active.clear()
            if client: 
                try: client.close()
                except: pass
            client = None
            break
    
    print("[recv_thread] Loop finished. sender_thread_active.is_set():", sender_thread_active.is_set())

def handle_input():
    return my_vel

def shoot():
    global client, projectiles, send_queue, sender_thread_active
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

    # Then send to server for others via queue
    try:
        if sender_thread_active.is_set():
            send_queue.put({
                "shoot": {
                    "position": my_pos.copy(),
                    "velocity": vel.copy()
                }
            })
        else:
            print("Sender thread not active, not sending shoot.")
    except Exception as e:
        print(f"failed queueing shoot: {e}")

def isButtonClicked(rect, event):
    return event.type == pygame.MOUSEBUTTONDOWN and rect.collidepoint(event.pos)

def drawBackground(offset):    
    # Draw grid
    for x in range(0, WORLD_SIZE[0], grid_spacing):
        for y in range(0, WORLD_SIZE[1], grid_spacing):
            screen_x = x + offset[0]
            screen_y = y + offset[1]
            MARGIN = 100
        if -MARGIN <= screen_x < SCREEN_SIZE[0] + MARGIN and -MARGIN <= screen_y < SCREEN_SIZE[1] + MARGIN:
                pygame.draw.circle(screen, (60, 60, 60), (int(screen_x), int(screen_y)), 2)
    
    # Draw world boundary
    pygame.draw.rect(
        screen, (50,50,50),
        (offset[0], offset[1], WORLD_SIZE[0], WORLD_SIZE[1]),
        2
    )

    # Draw Speed Zones from server data (draw these first)
    for zone in speed_zones:
        # Screen coordinates for drawing
        screen_x = zone["x"] + offset[0]
        screen_y = zone["y"] + offset[1]

        MARGIN = 100
        if -MARGIN <= screen_x < SCREEN_SIZE[0] + MARGIN and -MARGIN <= screen_y < SCREEN_SIZE[1] + MARGIN:
            # Draw in screen coordinates
            pygame.draw.rect(screen, (0, 255, 0), (screen_x, screen_y, zone["width"], zone["height"]))

    # Draw Slow Zones from server data (draw these second)
    for zone in slow_zones:
        # Screen coordinates for drawing
        screen_x = zone["x"] + offset[0]
        screen_y = zone["y"] + offset[1]

        MARGIN = 100
        if -MARGIN <= screen_x < SCREEN_SIZE[0] + MARGIN and -MARGIN <= screen_y < SCREEN_SIZE[1] + MARGIN:
            # Draw in screen coordinates
            pygame.draw.rect(screen, (0, 0, 255), (screen_x, screen_y, zone["width"], zone["height"]))
            
    # Draw Obstacles from server data (draw these last, so they are on top)
    for obstacle in obstacles:
        # Screen coordinates for drawing
        screen_x = obstacle["x"] + offset[0]
        screen_y = obstacle["y"] + offset[1]

        MARGIN = 100
        if -MARGIN <= screen_x < SCREEN_SIZE[0] + MARGIN and -MARGIN <= screen_y < SCREEN_SIZE[1] + MARGIN:
            # Create obstacle rect for collision detection (already done in apply_bounds, not strictly needed here for drawing)
            # obstacle_rect = pygame.Rect(obstacle["x"], obstacle["y"], obstacle["width"], obstacle["height"])
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
    
    # Draw input box
    color = (0, 0, 0) if input_active else (100, 100, 100)
    pygame.draw.rect(screen, color, input_box, 2)
    font = pygame.font.SysFont(None, 36)
    text_surf = font.render(input_server_chosen, True, (0, 0, 0))
    screen.blit(text_surf, (input_box.x + 5, input_box.y + 5))

    drawText("Enter Server Number (e.g. 89)", 24, (0, 0, 0), input_box.x, input_box.y - 30)
    drawText(response_text, 24, (240, 0, 0), input_box.x, input_box.y + 60)

    drawButton("Start Game", start_button_rect, 36, (0, 200, 130), (0, 255, 180), (255, 255, 255))
    pygame.display.flip()

def drawGamePlay():
    global projectiles, players, hits
    # Drawing
    screen.fill((30, 30, 30))
    
    # Calculate drawing offset
    offset = (
        SCREEN_SIZE[0]//2 - my_pos[0],
        SCREEN_SIZE[1]//2 - my_pos[1]
    )
    
    drawBackground(offset)
    pygame.mixer.music.set_volume(1)

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
        MARGIN = 100
        if -MARGIN <= screen_x < SCREEN_SIZE[0] + MARGIN and -MARGIN <= screen_y < SCREEN_SIZE[1] + MARGIN:
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
        MARGIN = 100
        if -MARGIN <= screen_x < SCREEN_SIZE[0] + MARGIN and -MARGIN <= screen_y < SCREEN_SIZE[1] + MARGIN:
            pygame.draw.circle(
                screen, (255,255,0),
                (screen_x, screen_y),
                5
            )

    # Draw music controls
    draw_music_controls()
    active_players = sum(1 for p in players if p is not None)
    drawText(f"Amount of Players {active_players}", 20, (255,255,255), 20, 20)
    drawButton("End Game", stop_button_rect, 18, (200, 50, 50), (255, 100, 100), (255, 255, 255))


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
    screen.fill((15, 42, 64))
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
            if event.type == pygame.MOUSEBUTTONDOWN:
                if input_box.collidepoint(event.pos):
                    input_active = True
                else:
                    input_active = False

                if start_button_rect.collidepoint(event.pos):
                    if input_server_chosen.isdigit():
                        server_chosen = int(input_server_chosen)
                        if connectionGame():
                            threading.Thread(target=recv_thread, daemon=True).start()
                            currentScreen = 'game'
                        else:
                            print("Failed to connect")
                    else:
                        response_text = "Please enter a valid number."

            elif event.type == pygame.KEYDOWN and input_active:
                if event.key == pygame.K_BACKSPACE:
                    input_server_chosen = input_server_chosen[:-1]
                elif event.key == pygame.K_RETURN:
                    input_active = False
                elif event.unicode.isdigit():
                    input_server_chosen += event.unicode


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
                    print("[Main Loop] Stop button clicked. Clearing sender_thread_active.")
                    sender_thread_active.clear()
                    if client:
                        try:
                            client.close()
                        except socket.error as e:
                            print(f"Socket error on close: {e}")
                        client = None # Mark client as closed
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
                # Attempt to reconnect
                if connectionGame(): # This will restart threads if successful
                    # Reset game state for resume
                    my_pos = [100 + player_id * 50, 100] # player_id might be stale if connection failed before
                    hits = 0
                    # No direct send here, let the sender thread handle it from runGame
                    currentScreen = 'game'
                else:
                    print("Failed to reconnect for resume.")
                    # Stay on 'stop' screen or go to 'start'
            if event.type == pygame.MOUSEBUTTONDOWN and next_button_rect1.collidepoint(event.pos):
                print("[Main Loop] Stop screen: Back to Start clicked. Clearing sender_thread_active.")
                sender_thread_active.clear()
                if client:
                    try:
                        client.close()
                    except: pass
                    client = None
                currentScreen = 'start'

        elif currentScreen == 'gameOver':
            if event.type == pygame.MOUSEBUTTONDOWN and next_button_rect.collidepoint(event.pos):
                # Attempt to reconnect
                if connectionGame(): # This will restart threads
                    my_pos = [100 + player_id * 50, 100]
                    hits = 0
                    currentScreen = 'game'
                else:
                    print("Failed to reconnect for play again.")

                if connectionGame(): # This will restart threads
                    my_pos = [100 + player_id * 50, 100]
                    hits = 0
                    currentScreen = 'game'
                else:
                    print("Failed to reconnect for play again.")
            if event.type == pygame.MOUSEBUTTONDOWN and next_button_rect1.collidepoint(event.pos):
                print("[Main Loop] GameOver screen: Back to Start clicked. Clearing sender_thread_active.")
                sender_thread_active.clear()
                if client:
                    try:
                        client.close()
                    except: pass
                    client = None
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
print("[Main] Pygame quit. Clearing sender_thread_active.")
sender_thread_active.clear()
if client and client != False : # Check client is a socket object before closing
    try:
        client.close()
    except: pass # Ignore errors on final close
client = None # Ensure client is None at the very end

# It's good practice to wait for daemon threads if you want to ensure cleanup,
# but for a game client, letting them exit with the main program is often fine.
# If send_queue.join() was used, this would be more critical.
