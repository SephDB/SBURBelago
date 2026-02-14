import itertools
import logging
from collections import defaultdict
from dataclasses import dataclass

from BaseClasses import Location
from NetUtils import MultiData
from Options import OptionError, OptionSet, Choice, PerGameCommonOptions, Toggle, DefaultOnToggle, T, TextChoice
# Imports of base Archipelago modules must be absolute.
from worlds.AutoWorld import World


class SkaiaSlots(OptionSet):
    """
    Select which slots are part of Skaia instead of the Medium's topology.
    These will be able to send/receive items from all other worlds, thus being mostly unaffected by this meta world's effects.

    Good for meta-games like APBingo or a group puzzle slot

    Valid keys are the names of other slots in the multiworld
    """
    display_name = "Skaia Slots"

class MediumTopology(TextChoice):
    """
    Select the type of topology the Medium has.

    Ring: Each game only has items for itself and the next in the ring.
    Dual: Items can flow in both directions across the ring.
    SBURB: each game exclusively has item for the next, not its own.
        WARNING: this last mode is extremely likely to fail generation.
        Enable at least one decently-sized Skaia world and turn on progression only mode for any chance of generating.
    Custom: comma-separated list of offsets to connected worlds. These work modulo the amount of worlds in the Medium.
        Here's how the other options translate into this one:
        - Ring: "0,1"
        - Dual: "-1,0,1"
        - SBURB: "1"
    """
    display_name = "Medium's Topology"

    option_ring = 0
    option_dual = 1
    option_SBURB = 2

    default = 0

    @classmethod
    def get_option_name(cls, value: T) -> str:
        if isinstance(value,str):
            return value
        if value == MediumTopology.option_SBURB:
            return "SBURB"
        return super().get_option_name(value)

class ProgressionOnly(Toggle):
    """
    Only affect placement of progression items, allow filler to be placed freely
    """
    display_name = "Progression Only"

class RandomizeMedium(DefaultOnToggle):
    """
    Randomize the order of the player worlds in the Medium
    """
    display_name = "Randomize Medium order"

@dataclass
class SBURBOptions(PerGameCommonOptions):
    skaia: SkaiaSlots
    medium_topo: MediumTopology
    medium_rando: RandomizeMedium
    progression_only: ProgressionOnly

class SBURBelagoWorld(World):
    """
    Play your AP as a SBURB session, each player only has items for themselves and a single other person
    in a big circular chain.
    """

    game = "SBURBelago"

    location_name_to_id = {}
    item_name_to_id = {}

    options_dataclass = SBURBOptions
    options: SBURBOptions

    connected_worlds: dict[int,frozenset[int]]

    def generate_early(self) -> None:
        if self.player != self.multiworld.players:
            raise OptionError("SBURBelago is required to be the last slot in the multiworld!")

        skaia = {p for p in self.multiworld.player_ids if self.multiworld.player_name[p] in self.options.skaia.value}
        players = [p for p in self.multiworld.player_ids[:-1] if p not in skaia]
        if self.options.medium_rando:
            self.random.shuffle(players)

        if len(players) == 0:
            logging.warn("SBURBelago requires players in the Medium to do anything.")
            if len(skaia) == 0:
                raise OptionError("SBURBelago is a meta-world and requires other worlds to generate.")
            logging.warn("All worlds are placed in Skaia, there's no rules for SBURBelago to set!")

        topology_option:str = defaultdict(lambda:self.options.medium_topo.value,{
            MediumTopology.option_ring: "0,1",
            MediumTopology.option_dual: "-1,0,1",
            MediumTopology.option_SBURB: "1"
        })[self.options.medium_topo.value]

        try:
            topology = [int(part) for part in topology_option.split(',')]
        except ValueError:
            raise OptionError("SBURBelago: Invalid Medium topology specification. Please double check your syntax.")

        connected_worlds = defaultdict(set)
        for index,player in enumerate(players):
            connected_worlds[player].update(skaia)
            for offset in topology:
                connected_worlds[player].add(players[(index+offset) % len(players)])

        self.connected_worlds = {p: frozenset(allowed) for p,allowed in connected_worlds.items()}

    def generate_basic(self) -> None:
        # Basic copy of locality rules, make each player only be able to have their own or the next person's items
        func_cache = {}
        prog_only = bool(self.options.progression_only.value)
        for location in self.multiworld.get_locations():
            if location.player not in self.connected_worlds:
                continue
            if (location.player, location.item_rule) in func_cache:
                location.item_rule = func_cache[location.player, location.item_rule]
                continue

            # empty rule that just returns True, overwrite
            if location.item_rule is Location.item_rule:
                func_cache[location.player, location.item_rule] = location.item_rule = \
                    lambda i, prog=prog_only, allowed_players=self.connected_worlds[location.player]: \
                        (prog and not i.advancement) or i.player in allowed_players

            # special rule, needs to also be fulfilled.
            else:
                func_cache[location.player, location.item_rule] = location.item_rule = \
                    lambda i, prog=prog_only, allowed_players=self.connected_worlds[location.player], \
                           old_rule=location.item_rule: \
                        ((prog and not i.advancement) or i.player in allowed_players) and old_rule(i)

    def modify_multidata(self, multidata: "MultiData") -> None:
        del multidata["slot_data"][self.player]
        del multidata["slot_info"][self.player]
        del multidata["connect_names"][self.player_name]
        del multidata["locations"][self.player]
        del multidata["precollected_items"][self.player]
        del multidata["precollected_hints"][self.player]
        del multidata["datapackage"][self.game]
