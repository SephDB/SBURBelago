import itertools
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, TextIO

from BaseClasses import Location, MultiWorld
from NetUtils import MultiData, SlotType
from Options import OptionError, OptionSet, Choice, PerGameCommonOptions, Toggle, DefaultOnToggle, T, TextChoice, \
    OptionList, Visibility, OptionGroup
# Imports of base Archipelago modules must be absolute.
from worlds.AutoWorld import World, WebWorld


#OptionList to allow for non-string entries
class SkaiaSlots(OptionList):
    """
    Select which slots are part of Skaia instead of the Medium's topology.
    These will be able to send/receive items to/from all Medium worlds.

    Good for meta-games like APBingo or a group puzzle slot

    Valid keys are the names of other slots in the multiworld or the slot number directly
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

class RandomizeMedium(Toggle):
    """
    Randomize the order of the player worlds in the Medium
    """
    display_name = "Randomize Medium order"

class RemoveSelf(Toggle):
    """
    Remove this world from the multiworld at the end of generation.
    Requires this to be the last slot in the multiworld and no item links to be active.
    """
    display_name = "Remove Self"

class MediumSlots(OptionList):
    """
    Specify which slots qualify for inclusion in the Medium. Slots specified as Skaia slots are removed from this.
    Special values:
        **ALL** - all slots except for SBURBelago ones
        **BETWEEN** - all slots between this and the previous SBURBelago slot in slot order
        **UNTIL** - all slots before this slot
    """
    visibility = Visibility.all ^ Visibility.template
    display_name = "Medium Slots"
    default = ["ALL"]

@dataclass
class SBURBOptions(PerGameCommonOptions):
    skaia: SkaiaSlots
    medium_topo: MediumTopology
    medium_rando: RandomizeMedium
    progression_only: ProgressionOnly
    remove_self: RemoveSelf
    medium_slots: MediumSlots

class SkaiaWeb(WebWorld):
    tutorials = []
    option_groups = [
        OptionGroup("Advanced Options",[RemoveSelf,MediumSlots],start_collapsed=True)
    ]

class SBURBelagoWorld(World):
    """
    Play your AP as a SBURB session, each player only has items for themselves and a single other person
    in a big circular chain.
    """

    game = "SBURBelago"

    location_name_to_id = {"Nowhere":10}
    item_name_to_id = {"Nothing":10}

    options_dataclass = SBURBOptions
    options: SBURBOptions

    web = SkaiaWeb() #Only here for options creator option groups

    connected_worlds: dict[int,frozenset[int]]

    def generate_early(self) -> None:
        self.multiworld.player_types[self.player] = SlotType.spectator #Auto-goal on

        if self.options.remove_self:
            if self.player != self.multiworld.players:
                raise OptionError("SBURBelago is required to be the last slot in the multiworld to delete itself!")
            if self.multiworld.groups:
                raise OptionError("SBURBelago can't delete itself if there's player groups(like item link)")

        slot_lookup = {**{name:player for player,name in self.multiworld.player_name.items()}, **{i:i for i in self.multiworld.player_ids}}

        if not set(self.options.skaia.value).issubset(slot_lookup.keys()):
            raise OptionError(f"Non-existent slots defined as Skaia worlds! {set(self.options.skaia.value).difference(slot_lookup.keys())}")

        skaia = {slot_lookup[p] for p in self.options.skaia.value}

        medium = []
        sburbs = [player for player in self.multiworld.player_ids if self.multiworld.game[player] == self.game]
        previous_sburb = max([p for p in sburbs if p < self.player],default=-1)

        for slot in self.options.medium_slots.value:
            if slot in slot_lookup:
                medium.append(slot_lookup[slot])
            elif slot == "ALL":
                medium += self.multiworld.player_ids[:]
            elif slot == "UNTIL":
                medium += self.multiworld.player_ids[:self.player]
            elif slot == "BETWEEN":
                medium += self.multiworld.player_ids[previous_sburb+1:self.player]
            else:
                raise OptionError(f"Unknown slot in medium_slots: {slot}")

        players = [p for p in medium if
                   p not in skaia and self.multiworld.game[p] != self.game]

        if len(players) == 0:
            logging.warn("SBURBelago requires players in the Medium to do anything.")
            if len(skaia) == 0:
                raise OptionError("SBURBelago is a meta-world and requires other worlds to generate.")
            logging.warn("All worlds are placed in Skaia, there's no rules for SBURBelago to set!")

        if self.options.medium_rando:
            self.random.shuffle(players)

        topology_option:str = defaultdict(lambda:self.options.medium_topo.value,{
            MediumTopology.option_ring: "0,1",
            MediumTopology.option_dual: "-1,0,1",
            MediumTopology.option_SBURB: "1"
        })[self.options.medium_topo.value]

        try:
            topology = [int(part) for part in topology_option.split(',')] if len(topology_option) > 0 else []
        except ValueError:
            raise OptionError("SBURBelago: Invalid Medium topology specification. Please double check your syntax.")

        connected_worlds = defaultdict(set)
        for index,player in enumerate(players):
            connected_worlds[player].update(skaia)
            for offset in topology:
                connected_worlds[player].add(players[(index+offset) % len(players)])
        all_defined_worlds = set(players).union(skaia)
        for skaia_slot in skaia:
            connected_worlds[skaia_slot].update(all_defined_worlds)

        self.connected_worlds = {p: frozenset(allowed) for p,allowed in connected_worlds.items()}

    @classmethod
    def stage_generate_basic(cls, multiworld: MultiWorld):
        sburbs:Iterable[SBURBelagoWorld] = multiworld.get_game_worlds(cls.game)
        all_game_ids = {p for p in multiworld.player_ids if multiworld.game[p] != cls.game}

        connected_worlds:dict[int,set[int]] = defaultdict(set)
        progression_setting = {}
        for game in sburbs:
            progression = game.options.progression_only.value
            for slot,connected in game.connected_worlds.items():
                connected_worlds[slot].update(connected)
                if progression_setting.setdefault(slot,progression) != progression:
                    raise OptionError(f"Mismatched SBURBelago progression setting on slot {slot}: {multiworld.player_name[slot]}")

        missing_players = {p for p in multiworld.player_ids if len(multiworld.regions.location_cache[p]) > 0} - set(connected_worlds.keys())
        if missing_players:
            raise OptionError(f"Slots not included in SBURBelago: {[multiworld.player_name[p] for p in missing_players]}")

        connected_worlds = {slot:connected for slot,connected in connected_worlds.items() if connected != all_game_ids}

        # Fix item links
        for group_slot,group in multiworld.groups.items():
            group_players = group["players"]
            for slot,connected in connected_worlds.items():
                if not connected.isdisjoint(group_players):
                    connected.add(group_slot)

        final_connections = cls.final_connections = {slot:frozenset(connected) for slot,connected in connected_worlds.items()}

        func_cache = {}
        for location in multiworld.get_locations():
            if location.player not in final_connections:
                continue
            if (location.player, location.item_rule) in func_cache:
                location.item_rule = func_cache[location.player, location.item_rule]
                continue

            prog_only = progression_setting[location.player]
            # empty rule that just returns True, overwrite
            if location.item_rule is Location.item_rule:
                func_cache[location.player, location.item_rule] = location.item_rule = \
                    lambda i, prog=prog_only, allowed_players=final_connections[location.player]: \
                        (prog and not i.advancement) or i.player in allowed_players

            # special rule, needs to also be fulfilled.
            else:
                func_cache[location.player, location.item_rule] = location.item_rule = \
                    lambda i, prog=prog_only, allowed_players=final_connections[location.player], \
                           old_rule=location.item_rule: \
                        ((prog and not i.advancement) or i.player in allowed_players) and old_rule(i)

    @classmethod
    def stage_write_spoiler(cls, multi:MultiWorld, file:TextIO):
        file.write("\n\nSBURBelago layout:\nCopy this into https://dreampuf.github.io/GraphvizOnline/?engine=circo \n\n")
        file.write("digraph SBURBelago {\n")

        file.writelines(f"\tp{slot} [label={name}];\n" for slot,name in multi.player_name.items()
                        if slot not in multi.groups and multi.game[slot] != cls.game)
        file.write('\n')

        for slot1,connections in cls.final_connections.items():
            file.writelines(f"\tp{slot1} -> p{slot2};\n" for slot2 in connections if slot2 not in multi.groups)

        file.write("}\n\n")

        cls.final_connections = {}

    def modify_multidata(self, multidata: "MultiData") -> None:
        if not self.options.remove_self:
            return
        del multidata["slot_data"][self.player]
        del multidata["slot_info"][self.player]
        del multidata["connect_names"][self.player_name]
        del multidata["locations"][self.player]
        del multidata["precollected_items"][self.player]
        del multidata["precollected_hints"][self.player]
        del multidata["datapackage"][self.game]
