from calendar import c
from locale import ABDAY_4
from mimetypes import init
import random
import re
import sys
from typing import Dict, List, Optional, Set, Tuple


RESET = "\033[0m"
GREEN = "\033[32m"
GOLD = "\033[93m" 
CYAN = "\033[36m"
RED = "\033[31m"
BLUE = "\033[34m"
BLACK = "\033[30m"
WHITE = "\033[37m"
BOLD = "\033[1m"
STRIKE = "\033[9m"


BOARD_SIZE = 10
ROWS = [chr(ord('A') + i) for i in range(BOARD_SIZE)]
COLS = [str(i + 1) for i in range(BOARD_SIZE)]

SHIPS = [
    ("Carrier", 5),
    ("Battleship", 4),
    ("Cruiser", 3),
    ("Submarine", 3),
    ("Destroyer", 2),
]


Coord = Tuple[int, int]

SHOW_AI_SHIPS = False


class RestartGame(Exception):
    pass


def clear_screen() -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def coord_to_label(coord: Coord) -> str:
    r, c = coord
    return f"{ROWS[r]}{c + 1}"


def parse_coord(token: str) -> Optional[Coord]:
    token = token.strip().upper()
    m = re.fullmatch(r"([A-J])\s*(10|[1-9])", token)
    if not m:
        return None
    row_char, col_str = m.groups()
    r = ord(row_char) - ord('A')
    c = int(col_str) - 1
    if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
        return (r, c)
    return None


def parse_placement_input(s: str) -> Optional[Tuple[Coord, str]]:
    s = s.strip().upper()
    m = re.fullmatch(r"([A-J]\s*(?:10|[1-9]))\s*([HV])", s)
    if not m:
        m2 = re.fullmatch(r"([A-J](?:10|[1-9]))([HV])", s)
        if not m2:
            return None
        pos, orient = m2.groups()
    else:
        pos, orient = m.groups()
    coord = parse_coord(pos)
    if coord is None:
        return None
    return coord, orient


class Ship:
    def __init__(self, name: str, size: int, coords: Set[Coord]):
        self.name = name
        self.size = size
        self.coords = set(coords)
        self.hits: Set[Coord] = set()

    def register_hit(self, coord: Coord) -> None:
        if coord in self.coords:
            self.hits.add(coord)

    @property
    def sunk(self) -> bool:
        return len(self.hits) == self.size


class Board:
    def __init__(self) -> None:
        self.ships: Dict[str, Ship] = {}
        self.occupied: Set[Coord] = set()
        self.shots: Set[Coord] = set()
        self.hits: Set[Coord] = set()
        self.misses: Set[Coord] = set()

    def in_bounds(self, coord: Coord) -> bool:
        r, c = coord
        return 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE

    def can_place(self, start: Coord, size: int, orient: str) -> bool:
        dr, dc = (0, 1) if orient == 'H' else (1, 0)
        r, c = start
        for i in range(size):
            rr, cc = r + dr * i, c + dc * i
            if not self.in_bounds((rr, cc)):
                return False
            if (rr, cc) in self.occupied:
                return False
        return True

    def place_ship(self, name: str, size: int, start: Coord, orient: str) -> bool:
        if not self.can_place(start, size, orient):
            return False
        dr, dc = (0, 1) if orient == 'H' else (1, 0)
        r, c = start
        coords = {(r + dr * i, c + dc * i) for i in range(size)}
        self.occupied.update(coords)
        self.ships[name] = Ship(name, size, coords)
        return True

    def shoot(self, coord: Coord) -> Tuple[str, Optional[str]]:
        if coord in self.shots:
            return "already", None
        self.shots.add(coord)
        if coord in self.occupied:
            self.hits.add(coord)
            for ship in self.ships.values():
                if coord in ship.coords:
                    ship.register_hit(coord)
                    if ship.sunk:
                        return "sunk", ship.name
                    else:
                        return "hit", None
        else:
            self.misses.add(coord)
            return "miss", None

    def all_sunk(self) -> bool:
        return all(s.sunk for s in self.ships.values())


def render_board(board: Board, show_ships: bool, color: str) -> str:
    lines: List[str] = []
    header = "   " + " ".join(f"{col:>2}" for col in COLS)
    lines.append(color + header + RESET)
    # Track sunk ship coordinates for strikethrough styling
    sunk_coords: Set[Coord] = set()
    for ship in board.ships.values():
        if ship.sunk:
            sunk_coords.update(ship.coords)
    for r in range(BOARD_SIZE):
        row_label = ROWS[r]
        row_cells: List[str] = []
        for c in range(BOARD_SIZE):
            p = (r, c)
            if p in board.hits:
                if p in sunk_coords:
                    cell = f" {BOLD}{RED}{STRIKE}X{RESET}{color}"
                else:
                    cell = f" {BOLD}{RED}X{RESET}{color}"
            elif p in board.misses:
                cell = f" {BOLD}{BLACK}0{RESET}{color}"
            elif show_ships and p in board.occupied:
                cell = " S"
            else:
                cell = " ~"
            row_cells.append(cell)
        lines.append(color + f"{row_label}  " + " ".join(row_cells) + RESET)
    return "\n".join(lines)


class AIPlayer:
    def __init__(self) -> None:
        self.available: Set[Coord] = {(r, c) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)}
        self.target_queue: List[Coord] = []
        self.hit_chain: List[Coord] = []

    def reset(self) -> None:
        self.available = {(r, c) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)}
        self.target_queue = []
        self.hit_chain = []

    def place_ships_randomly(self, board: Board) -> None:
        for name, size in SHIPS:
            placed = False
            tries = 0
            while not placed and tries < 1000:
                tries += 1
                orient = random.choice(['H', 'V'])
                r = random.randint(0, BOARD_SIZE - 1)
                c = random.randint(0, BOARD_SIZE - 1)
                placed = board.place_ship(name, size, (r, c), orient)
            if not placed:
                raise RuntimeError("AI failed to place ships after many tries")

    def next_shot(self) -> Coord:
        while self.target_queue and self.target_queue[-1] not in self.available:
            self.target_queue.pop()
        if self.target_queue:
            coord = self.target_queue.pop()
            self.available.discard(coord)
            return coord
        parity_cells = [p for p in self.available if (p[0] + p[1]) % 2 == 0]
        if parity_cells:
            coord = random.choice(parity_cells)
        else:
            coord = random.choice(tuple(self.available))
        self.available.discard(coord)
        return coord

    def on_result(self, coord: Coord, result: str, sunk: Optional[str]) -> None:
        if result == 'hit' or result == 'sunk':
            self.hit_chain.append(coord)
            if result == 'sunk':
                self.target_queue.clear()
                self.hit_chain.clear()
                return
            if len(self.hit_chain) == 1:
                self.enqueue_neighbors(coord)
            else:
                r1, c1 = self.hit_chain[-2]
                r2, c2 = self.hit_chain[-1]
                if r1 == r2:
                    min_c = min(p[1] for p in self.hit_chain)
                    max_c = max(p[1] for p in self.hit_chain)
                    candidates = [(r1, min_c - 1), (r1, max_c + 1)]
                else:
                    min_r = min(p[0] for p in self.hit_chain)
                    max_r = max(p[0] for p in self.hit_chain)
                    candidates = [(min_r - 1, c1), (max_r + 1, c1)]
                for p in candidates:
                    if 0 <= p[0] < BOARD_SIZE and 0 <= p[1] < BOARD_SIZE and p in self.available:
                        self.target_queue.append(p)

    def enqueue_neighbors(self, coord: Coord) -> None:
        r, c = coord
        for p in [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]:
            if 0 <= p[0] < BOARD_SIZE and 0 <= p[1] < BOARD_SIZE and p in self.available:
                self.target_queue.append(p)


def prompt(text: str) -> str:
    try:
        s = input(text)
    except EOFError:
        return ""
    if s.strip().upper() == "XXX":
        raise RestartGame()
    return s


def place_ships_manually(board: Board) -> None:
    clear_screen()
    print(GREEN + "Your Board (place your ships)" + RESET)
    print(render_board(board, show_ships=True, color=GREEN))
    for name, size in SHIPS:
        while True:
            print()
            print(f"Place {name} (size {size}) — format: A1 H or A1 V")
            s = prompt("> ")
            parsed = parse_placement_input(s)
            if not parsed:
                print(RED + "Invalid input. Example: A1 H" + RESET)
                continue
            start, orient = parsed
            if board.place_ship(name, size, start, orient):
                clear_screen()
                print(GREEN + "Your Board (place your ships)" + RESET)
                print(render_board(board, show_ships=True, color=GREEN))
                break
            else:
                print(RED + "Invalid placement (out of bounds or overlap). Try again." + RESET)


def human_fire(ai_board: Board) -> Tuple[Coord, str, Optional[str]]:
    while True:
        s = prompt("Enter shot (e.g., A5): ")
        coord = parse_coord(s)
        if coord is None:
            print(RED + "Invalid coordinate. Use A1..J10." + RESET)
            continue
        result, sunk = ai_board.shoot(coord)
        if result == 'already':
            print(RED + "You already fired there. Try again." + RESET)
            continue
        return coord, result, sunk


def ai_fire(ai: AIPlayer, human_board: Board) -> Tuple[Coord, str, Optional[str]]:
    while True:
        coord = ai.next_shot()
        result, sunk = human_board.shoot(coord)
        if result == 'already':
            continue
        ai.on_result(coord, result, sunk)
        return coord, result, sunk


def print_turn_boards(human_board: Board, ai_board: Board) -> None:
    print(GREEN + "Your Board" + RESET)
    print(render_board(human_board, show_ships=True, color=GREEN))
    print()
    print(GOLD + "General Bones" + RESET)
    print(render_board(ai_board, show_ships=SHOW_AI_SHIPS, color=GOLD))
    print()
    print(f"You have sunk: {', '.join([name for name, s in ai_board.ships.items() if s.sunk]) or 'None'}")
    print(f"AI has sunk: {', '.join([name for name, s in human_board.ships.items() if s.sunk]) or 'None'}")
    print("Wanna start over? Enter XXX")


def game_once() -> None:
    while True:
        human_board = Board()
        ai_board = Board()
        ai = AIPlayer()

        ai.place_ships_randomly(ai_board)
        clear_screen()
        print(CYAN + "Get ready for battle - General Bones awaits..." + RESET)
        print()
        try:
            global SHOW_AI_SHIPS
            ans = prompt("Reveal AI ships for verification? (y/n): ").strip().lower()
            SHOW_AI_SHIPS = (ans == 'y')
            print()
            use_auto = prompt("Auto-place your ships? (y/n): ").strip().lower()
            if use_auto == 'y':
                AIPlayer().place_ships_randomly(human_board)
            else:
                place_ships_manually(human_board)
        except RestartGame:
            clear_screen()
            print("Restarting game...")
            continue
        while True:
            clear_screen()
            print_turn_boards(human_board, ai_board)
            print()
            # Human fires
            try:
                shot, result, sunk = human_fire(ai_board)
            except RestartGame:
                clear_screen()
                print("Restarting game...")
                break
            if result == 'hit':
                print(CYAN + f"You hit at {coord_to_label(shot)}!" + RESET)
            elif result == 'miss':
                print(f"You missed at {coord_to_label(shot)}.")
            elif result == 'sunk':
                print(CYAN + f"You sunk the AI's {sunk}!" + RESET)
            print()
            print(GOLD + "General Bones" + RESET)
            print(render_board(ai_board, show_ships=SHOW_AI_SHIPS, color=GOLD))
            print()
            print(f"You have sunk: {', '.join([name for name, s in ai_board.ships.items() if s.sunk]) or 'None'}")
            print(f"AI has sunk: {', '.join([name for name, s in human_board.ships.items() if s.sunk]) or 'None'}")
            print("Wanna start over? Enter XXX")

            if ai_board.all_sunk():
                print()
                print(CYAN + "You win! All AI ships sunk." + RESET)
                print()
                print("Final boards:")
                print_turn_boards(human_board, ai_board)
                return

            # AI fires
            print()
            print("AI is thinking...")
            ai_shot, ai_result, ai_sunk = ai_fire(ai, human_board)
            if ai_result == 'hit':
                print(RED + f"AI hit at {coord_to_label(ai_shot)}!" + RESET)
            elif ai_result == 'miss':
                print(f"AI missed at {coord_to_label(ai_shot)}.")
            elif ai_result == 'sunk':
                print(RED + f"AI sunk your {ai_sunk}!" + RESET)
            print()
            print(GREEN + "Your Board" + RESET)
            print(render_board(human_board, show_ships=True, color=GREEN))
            print()
            print(f"You have sunk: {', '.join([name for name, s in ai_board.ships.items() if s.sunk]) or 'None'}")
            print(f"AI has sunk: {', '.join([name for name, s in human_board.ships.items() if s.sunk]) or 'None'}")
            print("Wanna start over? Enter XXX")

            if human_board.all_sunk():
                print()
                print(RED + "AI wins! All your ships sunk." + RESET)
                print()
                print("Final boards:")
                print_turn_boards(human_board, ai_board)
                return

            try:
                prompt("Press Enter for next turn...")
            except RestartGame:
                clear_screen()
                print("Restarting game...")
                break


def main() -> None:
    random.seed()
    while True:
        game_once()
        print()
        ans = prompt("Good Game, Sebastian! Play Again? (y/n): ").strip().lower()
        if ans != 'y':
            break


if __name__ == "__main__":
    main()