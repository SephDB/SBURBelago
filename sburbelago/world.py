from BaseClasses import Location
# Imports of base Archipelago modules must be absolute.
from worlds.AutoWorld import World


class SBURBelagoWorld(World):
    """
    Play your AP as a SBURB session, each player only has items for themselves and a single other person
    in a big circular chain.
    """

    game = "SBURBelago"

    location_name_to_id = {}
    item_name_to_id = {}

    def next_player(self, player: int) -> int:
        next_player = player + 1
        if next_player == self.player:
            next_player += 1
        if next_player > self.multiworld.players:
            next_player = 1 if self.player != 1 else 2
        return next_player

    def generate_basic(self) -> None:
        # Basic copy of locality rules, make each player only be able to have their own or the next person's items
        func_cache = {}
        for location in self.multiworld.get_locations():
            if (location.player, location.item_rule) in func_cache:
                location.item_rule = func_cache[location.player, location.item_rule]
            # empty rule that just returns True, overwrite
            elif location.item_rule is Location.item_rule:
                func_cache[location.player, location.item_rule] = location.item_rule = \
                    lambda i, player=location.player, next_player=self.next_player(location.player), \
                           old_rule=location.item_rule: \
                        i.player in [player, next_player]
            # special rule, needs to also be fulfilled.
            else:
                func_cache[location.player, location.item_rule] = location.item_rule = \
                    lambda i, player=location.player, next_player=self.next_player(location.player), \
                           old_rule=location.item_rule: i.player in [player, next_player] and old_rule(i)
