import socket
import threading
import pickle
import tkinter as tk
from tkinter import messagebox, Listbox
import time

MAX_PLAYERS = 12
HOST = "127.0.0.1"  # Listen on all interfaces
PORT = 5555

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()

lock = threading.Lock()
clients = [None] * MAX_PLAYERS
addresses = [None] * MAX_PLAYERS
players = [None] * MAX_PLAYERS
shoot_events = []
running = True

colors = [
    "#00C8FF", "#FF5050", "#00FF00", "#FFFF00",
    "#FF00FF", "#00FFFF", "#800000", "#008000",
    "#000080", "#808000", "#800080", "#008080"
]

def client_thread(conn, player_id):
    global players, shoot_events, running
    try:
        conn.send(pickle.dumps({"player_id": player_id}))
    except Exception as e:
        return

    try:
        data = conn.recv(1024)
        init_msg = pickle.loads(data)
        with lock:
            players[player_id] = {
                "velocity": init_msg.get("velocity", [0, 0]),
                "last_position": init_msg.get("position", [100 + player_id * 50, 100]),
                "last_update": time.time()
            }
    except Exception as e:
        return

    while running:
        try:
            data = conn.recv(1024)
            if not data:
                break
            msg = pickle.loads(data)
            with lock:
                # Only process velocity changes
                if "velocity" in msg:
                    players[player_id]["velocity"] = msg["velocity"]
                    players[player_id]["last_update"] = time.time()
                
                # Shooting events
                if "shoot" in msg:
                    shoot_events.append({
                        "owner": player_id,
                        "position": msg["shoot"]["position"],
                        "velocity": msg["shoot"]["velocity"]
                    })
                
                # Position updates (only for respawns)
                if "position_update" in msg:
                    players[player_id]["last_position"] = msg["position_update"]
                    players[player_id]["last_update"] = time.time()
                
        except Exception as e:
            break
    
    with lock:
        clients[player_id] = None
        players[player_id] = None
    conn.close()

def broadcast_state():
    global shoot_events
    clock = time.time
    tick = 1/60
    last_time = clock()
    
    while running:
        current_time = clock()
        if current_time - last_time >= tick:
            with lock:
                # Calculate current positions based on last known velocity
                current_states = []
                for i in range(MAX_PLAYERS):
                    if players[i] is not None:
                        time_diff = current_time - players[i]["last_update"]
                        players[i]["last_position"] = [
                            players[i]["last_position"][0] + players[i]["velocity"][0] * time_diff,
                            players[i]["last_position"][1] + players[i]["velocity"][1] * time_diff
                        ]
                        players[i]["last_update"] = current_time
                        current_states.append({
                            "velocity": players[i]["velocity"],
                            "position": players[i]["last_position"]
                        })
                    else:
                        current_states.append(None)

                state = {
                    "players": current_states,
                    "shoot_events": shoot_events
                }
                shoot_events = []
                
                for i in range(MAX_PLAYERS):
                    if clients[i] is not None:
                        try:
                            clients[i].send(pickle.dumps(state))
                        except:
                            pass
            last_time = current_time

def accept_clients():
    while running:
        try:
            conn, addr = server.accept()
            with lock:
                for i in range(MAX_PLAYERS):
                    if clients[i] is None:
                        clients[i] = conn
                        addresses[i] = addr
                        threading.Thread(
                            target=client_thread,
                            args=(conn, i),
                            daemon=True
                        ).start()
                        break
                else:
                    conn.close()
        except:
            break

def force_resync():
    with lock:
        # First, request position updates from all clients
        sync_request = pickle.dumps({"request_position": True})
        for i in range(MAX_PLAYERS):
            if clients[i] is not None:
                try:
                    clients[i].send(sync_request)
                except:
                    pass
        
        # Wait a brief moment for responses
        time.sleep(0.1)
        
        # Then broadcast current state to everyone
        current_states = []
        for i in range(MAX_PLAYERS):
            if players[i] is not None:
                current_states.append({
                    "velocity": players[i]["velocity"],
                    "position": players[i]["last_position"]
                })
            else:
                current_states.append(None)

        state = {
            "players": current_states,
            "force_sync": True
        }
        sync_state = pickle.dumps(state)
        
        for i in range(MAX_PLAYERS):
            if clients[i] is not None:
                try:
                    clients[i].send(sync_state)
                except:
                    pass

def update_listbox():
    current_selection = listbox.curselection()
    listbox.delete(0, tk.END)
    with lock:
        for i in range(MAX_PLAYERS):
            status = "Connected" if clients[i] is not None else "Disconnected"
            listbox.insert(tk.END, f"Player {i}: {status}")
            if clients[i] is not None:
                listbox.itemconfig(i, {'bg': colors[i]})
    if current_selection:
        listbox.selection_set(current_selection)

def periodic_ui_update():
    if running:
        update_listbox()
        root.after(100, periodic_ui_update)  # Update every 100ms

def shutdown_server():
    global running
    if messagebox.askyesno("Quit", "Are you sure you want to stop the server?"):
        running = False
        # Send quit message to all clients
        quit_msg = pickle.dumps({"quit": True})
        with lock:
            for c in clients:
                if c is not None:
                    try:
                        c.send(quit_msg)
                        c.shutdown(socket.SHUT_RDWR)
                        c.close()
                    except:
                        pass
        root.destroy()
        server.close()

def kick_player():
    selected = listbox.curselection()
    if not selected:
        messagebox.showerror("Error", "No player selected!")
        return
    player_id = selected[0]
    
    with lock:
        if clients[player_id] is not None:
            # Store the client socket before nulling it
            client_to_kick = clients[player_id]
            
            # First remove from active lists to prevent any new messages
            clients[player_id] = None
            players[player_id] = None
            
            # Then try to send quit message and close connection
            try:
                client_to_kick.send(pickle.dumps({"quit": True, "kicked": True}))
            except:
                pass
            
            # Force close the connection
            try:
                client_to_kick.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                client_to_kick.close()
            except:
                pass
            
            # Immediately broadcast the player removal
            current_states = []
            for i in range(MAX_PLAYERS):
                if players[i] is not None:
                    current_states.append({
                        "velocity": players[i]["velocity"],
                        "position": players[i]["last_position"]
                    })
                else:
                    current_states.append(None)
            
            state = {
                "players": current_states,
                "shoot_events": []
            }
            
            # Send update to all remaining clients
            for i in range(MAX_PLAYERS):
                if clients[i] is not None:
                    try:
                        clients[i].send(pickle.dumps(state))
                    except:
                        pass
            
            update_listbox()

# Tkinter UI setup
root = tk.Tk()
root.title("Server")

listbox = Listbox(root, width=40, height=15)
listbox.pack(pady=10)

btn_frame = tk.Frame(root)
btn_frame.pack()
tk.Button(btn_frame, text="Kick", command=kick_player).grid(row=0, column=0)
tk.Button(btn_frame, text="Resync", command=force_resync).grid(row=0, column=1)
tk.Button(btn_frame, text="Quit", command=shutdown_server).grid(row=0, column=2)

# Start periodic UI updates
periodic_ui_update()

# Start server threads
threading.Thread(target=accept_clients, daemon=True).start()
threading.Thread(target=broadcast_state, daemon=True).start()

root.mainloop()