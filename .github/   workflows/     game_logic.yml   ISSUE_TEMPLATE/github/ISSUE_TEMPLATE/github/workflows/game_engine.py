import argparse, json, os, sys, time, random
from datetime import datetime, timezone

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
MAP_WIDTH = 15
MAP_HEIGHT = 15
INITIAL_HP = 20
INITIAL_GOLD = 0

# Cooldown thresholds (seconds)
GLOBAL_COOLDOWN = 10
USER_COOLDOWN = 60

# ----------------------------------------------------------------------
# Helper: load / save state
# ----------------------------------------------------------------------
def load_state(path="game_state.json"):
    if not os.path.exists(path):
        return create_initial_state()
    with open(path, "r") as f:
        return json.load(f)

def save_state(state, path="game_state.json"):
    with open(path, "w") as f:
        json.dump(state, f, indent=2)

# ----------------------------------------------------------------------
# Initial state (pre-seeded dungeon Level 1)
# ----------------------------------------------------------------------
def create_initial_state():
    # Pre-built 15x15 map
    dungeon_map = [
        ["#","#","#","#","#","#","#","#","#","#","#","#","#","#","#"],
        ["#",".",".",".","#",".",".",".","#",".",".",".",".",".","#"],
        ["#",".","$",".",".",".","X",".",".",".",".","#",".",".","#"],
        ["#",".",".",".","#",".",".",".","#",".",".","#",".",".","#"],
        ["#","#","#",".","#","#","#","#","#",".",".","#",".","#","#"],
        ["#",".",".",".",".",".",".",".",".",".",".","#",".",".","#"],
        ["#",".","#",".","#","#","#",".","#","#","#","#",".",".","#"],
        ["#",".","#",".",".",".",".",".",".",".",".",".",".",".","#"],
        ["#",".","#","#","#","#",".","#","#","#","#","#",".",".","#"],
        ["#",".",".",".",".","#",".",".",".",".",".",".",".",".","#"],
        ["#",".",".",".",".","#",".","#","#","#",".","#","#",".","#"],
        ["#",".","$",".",".","#",".",".",".",".",".",".",".",".","#"],
        ["#",".",".",".",".","#","#","#","#","#","#","#",".",">","#"],
        ["#",".",".",".",".",".",".",".",".",".",".",".",".",".","#"],
        ["#","#","#","#","#","#","#","#","#","#","#","#","#","#","#"]
    ]
    entities = [
        {"type": "monster", "x": 5, "y": 2, "hp": 8, "max_hp": 8, "attack": 4},
        {"type": "treasure", "x": 2, "y": 11, "gold": 15, "item": None},
        {"type": "treasure", "x": 2, "y": 2, "gold": 5, "item": "Potion"},
    ]
    return {
        "hero": {"x": 1, "y": 1, "hp": INITIAL_HP, "max_hp": INITIAL_HP, "gold": INITIAL_GOLD, "inventory": []},
        "dungeon": {"level": 1, "map": dungeon_map, "entities": entities},
        "config": {"global_cooldown": GLOBAL_COOLDOWN, "user_cooldown": USER_COOLDOWN},
        "last_action_time": "1970-01-01T00:00:00Z",
        "last_action_by_user": {},
        "log": [],
        "game_active": True
    }

# ----------------------------------------------------------------------
# Cooldown checks
# ----------------------------------------------------------------------
def check_cooldown(state, user):
    now = datetime.now(timezone.utc)
    last_global = datetime.fromisoformat(state["last_action_time"])
    if (now - last_global).total_seconds() < state["config"]["global_cooldown"]:
        return False, f"⏳ Global cooldown active. Try again in {state['config']['global_cooldown'] - (now-last_global).seconds}s."
    user_last_str = state["last_action_by_user"].get(user)
    if user_last_str:
        user_last = datetime.fromisoformat(user_last_str)
        if (now - user_last).total_seconds() < state["config"]["user_cooldown"]:
            return False, f"⏳ Your personal cooldown active. Wait {state['config']['user_cooldown'] - (now-user_last).seconds}s."
    return True, None

def update_cooldown(state, user):
    now = datetime.now(timezone.utc).isoformat()
    state["last_action_time"] = now
    state["last_action_by_user"][user] = now

# ----------------------------------------------------------------------
# Procedural dungeon generation (for level changes)
# ----------------------------------------------------------------------
def generate_dungeon(level):
    # Simple room-based generator
    w, h = MAP_WIDTH, MAP_HEIGHT
    grid = [["#" for _ in range(w)] for _ in range(h)]
    # Place 3-5 rooms
    rooms = []
    for _ in range(random.randint(4, 6)):
        rw = random.randint(3, 5)
        rh = random.randint(3, 5)
        rx = random.randint(1, w - rw - 1)
        ry = random.randint(1, h - rh - 1)
        # Check overlap
        if any(rx <= r[0]+r[2] and rx+rw >= r[0] and ry <= r[1]+r[3] and ry+rh >= r[1] for r in rooms):
            continue
        rooms.append((rx, ry, rw, rh))
        for y in range(ry, ry+rh):
            for x in range(rx, rx+rw):
                grid[y][x] = "."
    # Connect rooms with L-shaped corridors
    for i in range(len(rooms)-1):
        x1 = rooms[i][0] + rooms[i][2]//2
        y1 = rooms[i][1] + rooms[i][3]//2
        x2 = rooms[i+1][0] + rooms[i+1][2]//2
        y2 = rooms[i+1][1] + rooms[i+1][3]//2
        if random.random() < 0.5:
            # horizontal then vertical
            for x in range(min(x1,x2), max(x1,x2)+1):
                grid[y1][x] = "."
            for y in range(min(y1,y2), max(y1,y2)+1):
                grid[y][x2] = "."
        else:
            for y in range(min(y1,y2), max(y1,y2)+1):
                grid[y][x1] = "."
            for x in range(min(x1,x2), max(x1,x2)+1):
                grid[y2][x] = "."
    # Place stairs down in the last room
    lr = rooms[-1]
    sx, sy = lr[0] + lr[2]//2, lr[1] + lr[3]//2
    grid[sy][sx] = ">"
    # Generate entities
    entities = []
    # Monsters: one per room except first and last
    for r in rooms[1:-1]:
        mx = random.randint(r[0]+1, r[0]+r[2]-2)
        my = random.randint(r[1]+1, r[1]+r[3]-2)
        hp = 6 + level*2
        entities.append({"type": "monster", "x": mx, "y": my, "hp": hp, "max_hp": hp, "attack": 3+level})
    # Treasures: 2 random
    for _ in range(2):
        r = random.choice(rooms)
        tx = random.randint(r[0]+1, r[0]+r[2]-2)
        ty = random.randint(r[1]+1, r[1]+r[3]-2)
        # avoid stair/other entities
        if grid[ty][tx] == ".":
            gold = random.randint(5, 15)
            item = "Potion" if random.random() < 0.3 else None
            entities.append({"type": "treasure", "x": tx, "y": ty, "gold": gold, "item": item})
    # Place hero at first room center
    hero_x = rooms[0][0] + rooms[0][2]//2
    hero_y = rooms[0][1] + rooms[0][3]//2
    return {
        "level": level,
        "map": grid,
        "entities": entities,
        "hero_spawn": {"x": hero_x, "y": hero_y}
    }

# ----------------------------------------------------------------------
# Game commands
# ----------------------------------------------------------------------
def process_command(state, command, user):
    cmd = command.strip().lower()
    h = state["hero"]
    d = state["dungeon"]
    log_entry = None

    # --- Restart ---
    if cmd == "restart":
        state.clear()
        state.update(create_initial_state())
        return "🔄 Game restarted! A new hero enters the dungeon."

    if not state["game_active"]:
        return "💀 The hero is dead. Use `Restart` to begin a new adventure."

    # --- Movement ---
    dirs = {"north": (0,-1), "south": (0,1), "west": (-1,0), "east": (1,0)}
    if cmd.startswith("move "):
        dkey = cmd[5:]
        if dkey not in dirs:
            return f"❌ Unknown direction `{dkey}`. Use: Move North, Move South, Move East, Move West."
        dx, dy = dirs[dkey]
        nx, ny = h["x"] + dx, h["y"] + dy
        if not (0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT):
            return "❌ You cannot leave the dungeon."
        tile = d["map"][ny][nx]
        if tile == "#":
            return "❌ You bump into a wall."
        # Check for monster
        for e in d["entities"]:
            if e["type"] == "monster" and e["x"] == nx and e["y"] == ny:
                return "❌ A monster blocks the way! Attack it first."
        # Move hero
        h["x"], h["y"] = nx, ny
        # Check stairs
        if tile == ">":
            new_dungeon = generate_dungeon(d["level"] + 1)
            d.update(new_dungeon)
            h["x"], h["y"] = new_dungeon["hero_spawn"]["x"], new_dungeon["hero_spawn"]["y"]
            log_entry = f"{user} descends to level {d['level']}."
        else:
            log_entry = f"{user} moves {dkey}."
        # Auto-pickup if treasure on new cell (optional but user-friendly)
        treasure = next((e for e in d["entities"] if e["type"]=="treasure" and e["x"]==h["x"] and e["y"]==h["y"]), None)
        if treasure:
            h["gold"] += treasure["gold"]
            if treasure.get("item"):
                h["inventory"].append(treasure["item"])
            d["entities"].remove(treasure)
            log_entry += f" Found {treasure['gold']} gold" + (f" and a {treasure['item']}" if treasure.get("item") else "") + "!"
        state["log"].append(log_entry)
        return f"✅ {log_entry}"

    # --- Attack ---
    if cmd.startswith("attack "):
        dkey = cmd[7:]
        if dkey not in dirs:
            return f"❌ Unknown attack direction `{dkey}`. Use: Attack North, Attack South, Attack East, Attack West."
        dx, dy = dirs[dkey]
        tx, ty = h["x"] + dx, h["y"] + dy
        target = next((e for e in d["entities"] if e["type"]=="monster" and e["x"]==tx and e["y"]==ty), None)
        if not target:
            return "❌ No monster in that direction."
        # Hero attack
        dmg = random.randint(2, 7)
        target["hp"] -= dmg
        msg = f"⚔️ You hit the monster for {dmg} damage."
        if target["hp"] <= 0:
            gold_drop = random.randint(5, 15)
            h["gold"] += gold_drop
            d["entities"].remove(target)
            msg += f" It dies! You gain {gold_drop} gold."
        else:
            # Monster counterattack
            m_dmg = random.randint(1, target["attack"])
            h["hp"] -= m_dmg
            msg += f" The monster strikes back for {m_dmg} damage."
            if h["hp"] <= 0:
                h["hp"] = 0
                state["game_active"] = False
                msg += " 💀 You have fallen. Game Over."
        log_entry = f"{user} attacks {dkey}. {msg}"
        state["log"].append(log_entry)
        return f"✅ {msg}"

    # --- Pick Up ---
    if cmd in ("pick up", "pickup"):
        treasure = next((e for e in d["entities"] if e["type"]=="treasure" and e["x"]==h["x"] and e["y"]==h["y"]), None)
        if not treasure:
            return "❌ Nothing to pick up here."
        h["gold"] += treasure["gold"]
        if treasure.get("item"):
            h["inventory"].append(treasure["item"])
        d["entities"].remove(treasure)
        log_entry = f"{user} picks up {treasure['gold']} gold" + (f" and a {treasure['item']}" if treasure.get("item") else "")
        state["log"].append(log_entry)
        return f"✅ {log_entry}"

    # --- Use Item ---
    if cmd.startswith("use "):
        item = cmd[4:]
        if item not in h["inventory"]:
            return f"❌ You don't have `{item}`."
        if item.lower() == "potion":
            heal = 8
            h["hp"] = min(h["max_hp"], h["hp"] + heal)
            h["inventory"].remove(item)
            log_entry = f"{user} uses a Potion and heals {heal} HP."
            state["log"].append(log_entry)
            return f"✅ {log_entry}"
        else:
            return f"❌ Unknown item `{item}`."

    # --- Help / Invalid ---
    if cmd in ("help", "actions", "?"):
        return ("📜 Commands: Move North/South/East/West, Attack North/..., Pick Up, Use Potion, Restart")
    return f"❌ Unknown command `{command}`. Type `Help` for a list."

# ----------------------------------------------------------------------
# README rendering
# ----------------------------------------------------------------------
def render_readme(state):
    h = state["hero"]
    d = state["dungeon"]
    lines = []
    lines.append("# 🏰 Community Dungeon Crawler")
    lines.append(f"**Hero HP:** {h['hp']}/{h['max_hp']}  |  **Gold:** {h['gold']}  |  **Level:** {d['level']}")
    if h["inventory"]:
        lines.append(f"**Inventory:** {', '.join(h['inventory'])}")
    else:
        lines.append("**Inventory:** empty")
    if not state["game_active"]:
        lines.append("\n### 💀 GAME OVER 💀")
        lines.append("The hero has fallen. Use `Restart` to begin anew.")

    # ASCII map
    lines.append("\n```")
    # Create a display grid copy
    disp = [row[:] for row in d["map"]]
    # Place entities
    for e in d["entities"]:
        if disp[e["y"]][e["x"]] == ".":
            if e["type"] == "monster":
                disp[e["y"]][e["x"]] = "X"
            elif e["type"] == "treasure":
                disp[e["y"]][e["x"]] = "$"
    # Place hero (overrides everything)
    disp[h["y"]][h["x"]] = "H"
    for row in disp:
        lines.append("".join(row))
    lines.append("```")

    # Action buttons
    lines.append("\n### 🎮 Actions")
    base_url = f"https://github.com/{os.environ.get('GITHUB_REPOSITORY','owner/repo')}/issues/new?template=action.yml&labels=game-action&title="
    dirs = ["North", "South", "East", "West"]
    move_buttons = " | ".join([f"[Move {d}]({base_url}Move+{d})" for d in dirs])
    lines.append(f"**Move:** {move_buttons}")
    attack_buttons = " | ".join([f"[Attack {d}]({base_url}Attack+{d})" for d in dirs])
    lines.append(f"**Attack:** {attack_buttons}")
    lines.append(f"[Pick Up]({base_url}Pick+Up) | [Use Potion]({base_url}Use+Potion) | [Restart]({base_url}Restart)")

    # Recent log
    if state["log"]:
        lines.append("\n### 📜 Recent Events")
        for entry in state["log"][-5:]:
            lines.append(f"- {entry}")

    return "\n".join(lines) + "\n"

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--issue-number", required=True)
    parser.add_argument("--repo", required=True)  # not used directly, but available
    args = parser.parse_args()

    # Load state (creates if missing)
    state = load_state()

    # Cooldown check
    ok, msg = check_cooldown(state, args.user)
    if not ok:
        print(msg)
        return

    # Process command
    result_msg = process_command(state, args.command, args.user)

    # Update cooldown only if state changed (we use a simple check: if game_active didn't change to false due to error)
    # We'll always update cooldown if we reach this point (valid or not), but for invalid commands we may still want cooldown to avoid spam.
    # So we update cooldown.
    update_cooldown(state, args.user)

    # Write state and README
    save_state(state)
    with open("README.md", "w") as f:
        f.write(render_readme(state))

    print(result_msg)

if __name__ == "__main__":
    main()
