# Battleship CLI (Human vs AI)

A simple terminal-based Battleship game in Python. Human vs AI with a Hunt/Target AI.

## Requirements
- Python 3.10+
- macOS Terminal or any ANSI-capable terminal (for colors)

## Rules
- Board: 10x10 (rows A–J, columns 1–10)
- Ships (standard):
  - Carrier (5)
  - Battleship (4)
  - Cruiser (3)
  - Submarine (3)
  - Destroyer (2)
- Ships cannot overlap. Ships may touch edges/corners.
- Ships are placed horizontally or vertically.
- Human may place ships manually or auto-place. AI auto-places.
- Shots are entered like `A5`. You will be re-prompted on invalid or duplicate shots.
- Feedback reveals hit/miss and when a ship is sunk.
- Both boards are displayed: your board (green) and AI board (gold, General Bones).
- Start over option with "XXX" at any time
- Replay prompt at the end.

## Run
```bash
python3 battleship.py
```

## Notes
- Colors use ANSI escape codes. If your terminal doesn’t display color, the game still works in plain text.
