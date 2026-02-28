from __future__ import annotations

from typing import Any

from board_utils import road_signature


def _player_color_to_index(game_state: dict[str, Any]) -> dict[str, int]:
    return {
        player["color"]: idx
        for idx, player in enumerate(game_state.get("players", []))
        if isinstance(player, dict) and "color" in player
    }


def _settlements_by_id(game_state: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        settlement["id"]: settlement
        for settlement in game_state.get("settlements", [])
        if isinstance(settlement, dict) and isinstance(settlement.get("id"), int)
    }


def _player_road_edges(game_state: dict[str, Any], player_color: str) -> list[tuple[int, int]]:
    edges: list[tuple[int, int]] = []
    for road in game_state.get("roads", []):
        if road.get("color") == player_color:
            edges.append(road_signature(road["a"], road["b"]))
    return edges


def _blocked_vertices(game_state: dict[str, Any], player_color: str) -> set[int]:
    blocked: set[int] = set()
    for settlement in game_state.get("settlements", []):
        owner = settlement.get("color")
        stype = settlement.get("type")
        if owner is not None and owner != player_color and stype in {"settlement", "city"}:
            blocked.add(settlement["id"])
    return blocked


def longest_road_length(game_state: dict[str, Any], player_color: str) -> int:
    edges = _player_road_edges(game_state, player_color)
    if not edges:
        return 0

    adjacency: dict[int, list[tuple[int, int]]] = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append((a, b))
        adjacency.setdefault(b, []).append((a, b))

    blocked = _blocked_vertices(game_state, player_color)
    best = 0

    def dfs(vertex: int, used: set[tuple[int, int]], length: int) -> None:
        nonlocal best
        best = max(best, length)

        if length > 0 and vertex in blocked:
            return

        for edge in adjacency.get(vertex, []):
            if edge in used:
                continue
            a, b = edge
            nxt = b if vertex == a else a
            used.add(edge)
            dfs(nxt, used, length + 1)
            used.remove(edge)

    for a, b in edges:
        used_a = {(a, b)}
        dfs(a, used_a, 1)
        used_b = {(a, b)}
        dfs(b, used_b, 1)

    return best


def _base_structure_points(game_state: dict[str, Any], player_color: str) -> int:
    points = 0
    for settlement in game_state.get("settlements", []):
        if settlement.get("color") != player_color:
            continue
        if settlement.get("type") == "settlement":
            points += 1
        elif settlement.get("type") == "city":
            points += 2
    return points


def update_longest_road_holder(game_state: dict[str, Any]) -> None:
    players = game_state.get("players", [])
    lengths = []
    for player in players:
        length = longest_road_length(game_state, player["color"])
        player["longest_road_length"] = length
        lengths.append(length)

    if not lengths:
        return

    max_len = max(lengths)
    prev_holder = next(
        (p["color"] for p in players if p.get("has_longest_road")),
        None,
    )

    for player in players:
        player["has_longest_road"] = False

    if max_len < 5:
        return

    leaders = [players[i]["color"] for i, l in enumerate(lengths) if l == max_len]

    if len(leaders) == 1:
        winner = leaders[0]
    elif prev_holder in leaders:
        winner = prev_holder
    else:
        winner = None

    if winner is not None:
        for player in players:
            if player["color"] == winner:
                player["has_longest_road"] = True
                break


def update_largest_army_holder(game_state: dict[str, Any]) -> None:
    players = game_state.get("players", [])
    knight_counts = [int(player.get("played_knights", 0)) for player in players]
    if not knight_counts:
        return

    max_knights = max(knight_counts)
    prev_holder = next(
        (p["color"] for p in players if p.get("has_largest_army")),
        None,
    )

    for player in players:
        player["has_largest_army"] = False

    if max_knights < 3:
        return

    leaders = [players[i]["color"] for i, k in enumerate(knight_counts) if k == max_knights]

    if len(leaders) == 1:
        winner = leaders[0]
    elif prev_holder in leaders:
        winner = prev_holder
    else:
        winner = None

    if winner is not None:
        for player in players:
            if player["color"] == winner:
                player["has_largest_army"] = True
                break


def compute_player_victory_points(game_state: dict[str, Any], player_color: str) -> int:
    color_to_index = _player_color_to_index(game_state)
    idx = color_to_index[player_color]
    player = game_state["players"][idx]

    points = _base_structure_points(game_state, player_color)

    dev_cards = player.get("development_cards", {})
    points += int(dev_cards.get("victory_point", 0))

    if player.get("has_longest_road"):
        points += 2
    if player.get("has_largest_army"):
        points += 2

    return points


def recompute_all_victory_points(game_state: dict[str, Any]) -> None:
    update_longest_road_holder(game_state)
    update_largest_army_holder(game_state)

    for player in game_state.get("players", []):
        color = player["color"]
        player["victory_points"] = compute_player_victory_points(game_state, color)


def get_winner(game_state: dict[str, Any], threshold: int = 10) -> dict[str, Any] | None:
    players = game_state.get("players", [])
    if not players:
        return None

    best = max(players, key=lambda p: int(p.get("victory_points", 0)))
    if int(best.get("victory_points", 0)) >= threshold:
        return best
    return None


def validate_unique_settlement_ids(game_state: dict[str, Any]) -> bool:
    ids = [s["id"] for s in game_state.get("settlements", []) if "id" in s]
    return len(ids) == len(set(ids))
