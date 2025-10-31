import os
import uuid
from typing import Dict, Any
from flask import Flask, jsonify, request, send_from_directory, session

import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_DIR = os.path.join(BASE_DIR, "battleship app")
if GAME_DIR not in sys.path:
    sys.path.append(GAME_DIR)

# Import game logic
import battleship as game  # type: ignore

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

# In-memory store of game sessions
GAMES: Dict[str, Dict[str, Any]] = {}

def new_game_state() -> Dict[str, Any]:
    human_board = game.Board()
    ai_board = game.Board()
    ai = game.AIPlayer()
    ai.place_ships_randomly(ai_board)
    return {
        "human_board": human_board,
        "ai_board": ai_board,
        "ai": ai,
        "over": False,
        "winner": None,
        "placing_index": None,  # None means not in manual placement
    }


def get_game() -> Dict[str, Any]:
    gid = session.get("game_id")
    if not gid or gid not in GAMES:
        gid = str(uuid.uuid4())
        session["game_id"] = gid
        GAMES[gid] = new_game_state()
    return GAMES[gid]


def serialize_board(board: game.Board, reveal_ships: bool) -> Dict[str, Any]:
    return {
        "size": game.BOARD_SIZE,
        "hits": [list(p) for p in sorted(board.hits)],
        "misses": [list(p) for p in sorted(board.misses)],
        "shots": [list(p) for p in sorted(board.shots)],
        "ships": (
            [
                {
                    "name": s.name,
                    "size": s.size,
                    "coords": [list(p) for p in sorted(s.coords)],
                    "hits": [list(p) for p in sorted(s.hits)],
                    "sunk": s.sunk,
                }
                for s in board.ships.values()
            ]
            if reveal_ships
            else []
        ),
        "all_sunk": board.all_sunk(),
    }


@app.route("/")
def index():
    return send_from_directory(app.template_folder, "index.html")


@app.route("/api/new-game", methods=["POST"]) 
def api_new_game():
    # Reset session game
    gid = str(uuid.uuid4())
    session["game_id"] = gid
    GAMES[gid] = new_game_state()

    data = request.get_json(silent=True) or {}
    auto_place = bool(data.get("auto_place", True))
    if auto_place:
        # Auto-place human ships
        game.AIPlayer().place_ships_randomly(GAMES[gid]["human_board"]) 
        GAMES[gid]["placing_index"] = None
    else:
        # Start manual placement
        GAMES[gid]["placing_index"] = 0

    return jsonify({"ok": True})


@app.route("/api/state", methods=["GET"]) 
def api_state():
    st = get_game()
    hb = st["human_board"]
    ab = st["ai_board"]
    placing_index = st.get("placing_index")
    placing = placing_index is not None and placing_index < len(game.SHIPS)
    next_ship = None
    if placing:
        name, size = game.SHIPS[placing_index]
        next_ship = {"name": name, "size": size, "index": placing_index}
    return jsonify({
        "over": st["over"],
        "winner": st["winner"],
        "human": serialize_board(hb, reveal_ships=True),
        "ai": serialize_board(ab, reveal_ships=False),
        "human_sunk": [name for name, s in ab.ships.items() if s.sunk],
        "ai_sunk": [name for name, s in hb.ships.items() if s.sunk],
        "placing": placing,
        "next_ship": next_ship,
        "placed_count": len(hb.ships),
    })


@app.route("/api/fire", methods=["POST"]) 
def api_fire():
    st = get_game()
    if st["over"]:
        return jsonify({"error": "game over"}), 400

    # Block firing if still placing
    placing_index = st.get("placing_index")
    if placing_index is not None and placing_index < len(game.SHIPS):
        return jsonify({"error": "finish ship placement before firing"}), 400

    data = request.get_json(force=True)
    label = data.get("cell")
    coord = game.parse_coord(label) if isinstance(label, str) else None
    if coord is None:
        return jsonify({"error": "invalid coordinate"}), 400

    # Ensure human has ships; if not, auto-place for now
    hb: game.Board = st["human_board"]
    if not hb.ships:
        game.AIPlayer().place_ships_randomly(hb)

    ab: game.Board = st["ai_board"]
    ai: game.AIPlayer = st["ai"]

    # Human fires
    result, sunk = ab.shoot(coord)
    human_event = {"shot": list(coord), "label": game.coord_to_label(coord), "result": result, "sunk": sunk}

    if ab.all_sunk():
        st["over"] = True
        st["winner"] = "human"
        return jsonify({
            "human": human_event,
            "ai": None,
            "state": {
                "over": st["over"],
                "winner": st["winner"],
                "human": serialize_board(hb, True),
                "ai": serialize_board(ab, False),
            },
        })

    # AI fires
    ai_shot = ai.next_shot()
    ai_result, ai_sunk = hb.shoot(ai_shot)
    ai.on_result(ai_shot, ai_result, ai_sunk)
    ai_event = {"shot": list(ai_shot), "label": game.coord_to_label(ai_shot), "result": ai_result, "sunk": ai_sunk}

    if hb.all_sunk():
        st["over"] = True
        st["winner"] = "ai"

    return jsonify({
        "human": human_event,
        "ai": ai_event,
        "state": {
            "over": st["over"],
            "winner": st["winner"],
            "human": serialize_board(hb, True),
            "ai": serialize_board(ab, False),
        },
    })


@app.route("/api/placement-state", methods=["GET"])
def api_placement_state():
    st = get_game()
    hb: game.Board = st["human_board"]
    placing_index = st.get("placing_index")
    placing = placing_index is not None and placing_index < len(game.SHIPS)
    next_ship = None
    if placing:
        name, size = game.SHIPS[placing_index]
        next_ship = {"name": name, "size": size, "index": placing_index}
    return jsonify({
        "placing": placing,
        "next_ship": next_ship,
        "placed_count": len(hb.ships),
        "human": serialize_board(hb, reveal_ships=True),
    })


@app.route("/api/place", methods=["POST"])
def api_place():
    st = get_game()
    hb: game.Board = st["human_board"]
    placing_index = st.get("placing_index")
    if placing_index is None or placing_index >= len(game.SHIPS):
        return jsonify({"error": "not in placement mode"}), 400

    data = request.get_json(force=True)
    start_label = data.get("start")
    orient = (data.get("orient") or "").upper()
    if orient not in ("H", "V"):
        return jsonify({"error": "orient must be 'H' or 'V'"}), 400
    coord = game.parse_coord(start_label) if isinstance(start_label, str) else None
    if coord is None:
        return jsonify({"error": "invalid start coordinate"}), 400

    name, size = game.SHIPS[placing_index]
    if hb.place_ship(name, size, coord, orient):
        st["placing_index"] += 1
        done = st["placing_index"] >= len(game.SHIPS)
        if done:
            st["placing_index"] = len(game.SHIPS)
        return jsonify({
            "ok": True,
            "done": done,
            "next_ship": (None if done else {"name": game.SHIPS[st["placing_index"]][0], "size": game.SHIPS[st["placing_index"]][1]}),
            "human": serialize_board(hb, reveal_ships=True),
        })
    else:
        return jsonify({"error": "invalid placement (out of bounds or overlap)"}), 400


@app.route("/static/<path:path>")
def serve_static(path: str):
    return send_from_directory(app.static_folder, path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
