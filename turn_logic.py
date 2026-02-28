from __future__ import annotations

import random
from typing import Any, Callable

from board_utils import BUILD_COSTS, RESOURCE_KEYS
import vp_scoring

DetectBoardCallback = Callable[[dict[str, Any], str, str | None], None]


def roll_two_six_sided_dice(rng: random.Random) -> tuple[int, int, int]:
    die_1 = rng.randint(1, 6)
    die_2 = rng.randint(1, 6)
    return die_1, die_2, die_1 + die_2


def _settlements_by_id(game_state: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        s["id"]: s
        for s in game_state.get("settlements", [])
        if isinstance(s, dict) and isinstance(s.get("id"), int)
    }


def _players_by_color(game_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["color"]: p for p in game_state.get("players", []) if "color" in p}


def _ensure_bank(game_state: dict[str, Any]) -> dict[str, Any]:
    bank = game_state.setdefault("bank", {})
    bank.setdefault("resources", {k: 19 for k in RESOURCE_KEYS})
    bank.setdefault("development_deck", [])
    bank.setdefault("discarded_development_cards", [])
    return bank


def allocate_resources_for_roll(
    game_state: dict[str, Any], roll_total: int
) -> dict[str, dict[str, int]]:
    if roll_total == 7:
        return {}

    settlements = _settlements_by_id(game_state)
    players_by_color = _players_by_color(game_state)
    bank = _ensure_bank(game_state)
    payouts: dict[str, dict[str, int]] = {}

    for tile in game_state.get("tiles", []):
        if tile.get("robber"):
            continue
        if tile.get("roll_number") != roll_total:
            continue

        resource = tile.get("resource_type")
        if resource not in RESOURCE_KEYS:
            continue

        for settlement_id in tile.get("settlement_ids", []):
            settlement = settlements.get(settlement_id)
            if not settlement:
                continue

            owner = settlement.get("color")
            structure = settlement.get("type")
            if owner not in players_by_color:
                continue
            if structure not in {"settlement", "city"}:
                continue

            amount = 2 if structure == "city" else 1
            available = int(bank["resources"].get(resource, 0))
            grant = min(amount, max(0, available))
            if grant <= 0:
                continue

            players_by_color[owner]["resources"][resource] += grant
            bank["resources"][resource] -= grant
            payouts.setdefault(owner, {})
            payouts[owner][resource] = int(payouts[owner].get(resource, 0)) + grant

    return payouts


def can_afford(player: dict[str, Any], cost: dict[str, int]) -> bool:
    resources = player.get("resources", {})
    return all(int(resources.get(r, 0)) >= n for r, n in cost.items())


def spend_resources(
    game_state: dict[str, Any], player: dict[str, Any], cost: dict[str, int]
) -> None:
    bank = _ensure_bank(game_state)
    for resource, amount in cost.items():
        player["resources"][resource] -= amount
        bank["resources"][resource] = int(bank["resources"].get(resource, 0)) + amount


def queue_structure_purchase(
    game_state: dict[str, Any], player: dict[str, Any], action_type: str
) -> bool:
    if action_type not in {"road", "settlement", "city"}:
        return False

    cost = BUILD_COSTS[action_type]
    if not can_afford(player, cost):
        return False

    spend_resources(game_state, player, cost)
    player.setdefault("pending_actions", []).append({"type": action_type})
    return True


def buy_development_card(game_state: dict[str, Any], player: dict[str, Any]) -> bool:
    bank = _ensure_bank(game_state)
    deck = bank.get("development_deck", [])
    cost = BUILD_COSTS["development_card"]

    if not can_afford(player, cost):
        return False
    if not deck:
        return False

    spend_resources(game_state, player, cost)
    card = deck.pop(0)
    player["development_cards"][card] = int(player["development_cards"].get(card, 0)) + 1
    return True


def trade_with_bank(
    game_state: dict[str, Any], player: dict[str, Any], give: str, get: str, rate: int = 4
) -> bool:
    if give not in RESOURCE_KEYS or get not in RESOURCE_KEYS or give == get:
        return False
    if rate <= 0:
        return False

    resources = player.get("resources", {})
    if int(resources.get(give, 0)) < rate:
        return False

    bank = _ensure_bank(game_state)
    if int(bank["resources"].get(get, 0)) <= 0:
        return False

    resources[give] -= rate
    resources[get] = int(resources.get(get, 0)) + 1
    bank["resources"][give] = int(bank["resources"].get(give, 0)) + rate
    bank["resources"][get] = int(bank["resources"].get(get, 0)) - 1
    return True


def _total_resource_cards(player: dict[str, Any]) -> int:
    resources = player.get("resources", {})
    return sum(int(resources.get(resource, 0) or 0) for resource in RESOURCE_KEYS)


def _discard_random_resources_to_bank(
    game_state: dict[str, Any], player: dict[str, Any], discard_count: int, rng: random.Random
) -> dict[str, int]:
    if discard_count <= 0:
        return {}

    resources = player.get("resources", {})
    bank = _ensure_bank(game_state)
    discarded: dict[str, int] = {}

    while discard_count > 0:
        available_types = []
        available_total = 0
        for resource in RESOURCE_KEYS:
            count = int(resources.get(resource, 0) or 0)
            if count <= 0:
                continue
            available_types.append((resource, count))
            available_total += count

        if available_total <= 0:
            break

        # Weighted random pick by card count (each card equally likely).
        pick = rng.randint(1, available_total)
        running = 0
        chosen_resource = available_types[0][0]
        for resource, count in available_types:
            running += count
            if pick <= running:
                chosen_resource = resource
                break

        resources[chosen_resource] = int(resources.get(chosen_resource, 0) or 0) - 1
        bank["resources"][chosen_resource] = int(bank["resources"].get(chosen_resource, 0) or 0) + 1
        discarded[chosen_resource] = int(discarded.get(chosen_resource, 0)) + 1
        discard_count -= 1

    return discarded


def _handle_roll_of_seven(
    game_state: dict[str, Any], active_player_color: str, hardware, rng: random.Random
) -> None:
    # Per project requirement: players with >=7 cards discard floor(total/2).
    discards_by_player: dict[str, dict[str, int]] = {}

    for player in game_state.get("players", []):
        if not isinstance(player, dict):
            continue

        color = str(player.get("color", "unknown"))
        total_cards = _total_resource_cards(player)
        if total_cards < 7:
            continue

        discard_count = total_cards // 2
        discarded = _discard_random_resources_to_bank(
            game_state=game_state, player=player, discard_count=discard_count, rng=rng
        )
        discards_by_player[color] = discarded

    game = game_state.setdefault("game", {})
    game["last_robber_discards"] = discards_by_player

    if discards_by_player:
        affected = ", ".join(sorted(discards_by_player.keys()))
        hardware.display_lcd_message(f"{active_player_color} rolled 7: discard {affected}")
    else:
        hardware.display_lcd_message(f"{active_player_color} rolled 7: no discards")


def run_player_turn(
    game_state: dict[str, Any],
    player_index: int,
    hardware,
    detect_board_callback: DetectBoardCallback,
    rng: random.Random,
) -> None:
    player = game_state["players"][player_index]
    color = player["color"]

    hardware.clear_all_player_lights()
    hardware.set_player_light(color, True)
    hardware.display_lcd_message(f"{color} turn")

    die_1, die_2, total = roll_two_six_sided_dice(rng)
    hardware.display_dice(die_1, die_2)

    game = game_state.setdefault("game", {})
    game["last_roll"] = {"die_1": die_1, "die_2": die_2, "total": total}

    if total == 7:
        game["last_roll_payouts"] = {}
        _handle_roll_of_seven(game_state, color, hardware, rng)
    else:
        game["last_roll_payouts"] = allocate_resources_for_roll(game_state, total)

    while True:
        action = hardware.get_turn_action(player, game_state)
        action_type = action.get("type", "end_turn")

        if action_type == "buy_road":
            ok = queue_structure_purchase(game_state, player, "road")
            hardware.display_lcd_message("Road queued" if ok else "Cannot buy road")

        elif action_type == "buy_settlement":
            ok = queue_structure_purchase(game_state, player, "settlement")
            hardware.display_lcd_message(
                "Settlement queued" if ok else "Cannot buy settlement"
            )

        elif action_type == "buy_city":
            ok = queue_structure_purchase(game_state, player, "city")
            hardware.display_lcd_message("City queued" if ok else "Cannot buy city")

        elif action_type == "buy_development_card":
            ok = buy_development_card(game_state, player)
            hardware.display_lcd_message("Dev card bought" if ok else "Cannot buy dev card")

        elif action_type == "trade_bank":
            ok = trade_with_bank(
                game_state,
                player,
                give=action.get("give", "wood"),
                get=action.get("get", "brick"),
                rate=int(action.get("rate", 4)),
            )
            hardware.display_lcd_message("Trade complete" if ok else "Trade failed")

        elif action_type == "end_turn":
            break

        else:
            hardware.display_lcd_message(f"Unknown action: {action_type}")

    detect_board_callback(game_state, context="end_turn_detection", player_color=color)
    vp_scoring.recompute_all_victory_points(game_state)

    hardware.set_player_light(color, False)
