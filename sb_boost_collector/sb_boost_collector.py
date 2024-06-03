import logging
import os
import util
import time
import json
import ctypes
import time
import math
import subprocess

from enum import Enum
from _remote import ffi, lib
from manager import PluginBase

# Place items in here that you don't want logged/displayed
FILTERED_ITEMS = '''
1 EC
'''.split("\n")
FILTERED_ITEMS = list(filter(None, FILTERED_ITEMS))

BASEDIR = os.path.split(os.path.dirname(__file__))[0]

CLEAN_BOOSTS_PY = BASEDIR + '\\clean_boost_information.py'
BOOST_MAP = BASEDIR + '\\boost_map.json'
SB_LOOT_LOGGER_FOLDER = BASEDIR + '\\sb_loot_logger'

SUBWORLD_LOOT_LOGPATH = SB_LOOT_LOGGER_FOLDER + '\\subworld_loot.log'
BOOST_COLLECTOR_LOG = SB_LOOT_LOGGER_FOLDER + '\\boost_collector.log'


DEBUG_MODE = True

class ITEM_TYPES(Enum):
    MISC = 0
    SLOT_MAIN = 256
    SLOT_SECOND = 512
    SLOT_SPECIAL = 768
    SLOT_BODY = 1024
    SLOT_MOBILITY = 1280

# Zones that we're ignoring
IGNORED_ZONE = (
    'home',
    'lobby'
) 

class Plugin(PluginBase):
    def onInit(self, inputs=None):
        self.new_subworld = False
        self.is_home = True
        self.is_recalled = False

        self.current_floor = 0
        self.current_zone = ""

        self.current_floor_looted_items = []
        self.current_subworld_looted_items = []

        self.current_floor_chests_ids = []
        self.current_floor_looted_items_ids = []
        self.player_dropped_items_ids = []

        if not os.path.exists(SB_LOOT_LOGGER_FOLDER):
            os.makedirs(SB_LOOT_LOGGER_FOLDER)
        
        # Check to see if files exists before using them later
        if not os.path.exists(BOOST_COLLECTOR_LOG):
            with open(BOOST_COLLECTOR_LOG, "w"):
                pass
            if DEBUG_MODE:
                logging.info("~~~~~~~~~~~~~~")
                logging.info("Boost Collector file has been created")
        elif DEBUG_MODE:
                logging.info("~~~~~~~~~~~~~~")
                logging.info("Boost Collector file has not been created")
        
    def afterUpdate(self, inputs=None):
        self.draw = False
        
        client_world = self.refs.ClientWorld
        world_view = self.refs.WorldView

        if client_world == ffi.NULL or world_view == ffi.NULL or client_world.player == ffi.NULL: 
            return
        
        cwprops = client_world.asWorld.props
        zone = util.getstr(client_world.asWorld.props.zone) or util.getstr(client_world.asWorld.props.music)
        floor = cwprops.floor;
        
        # Log floor loot
        logFloorLoot(self, floor, zone)

        # If we're not in the ignored zones 
        if zone not in IGNORED_ZONE:
            # Check to see if were in a new sub world within the game
            if not self.new_subworld:

                self.new_subworld = True
                self.is_home = False
                self.current_floor = floor 
                self.current_zone = zone

            # Iterate through all the game objects and search for Loot or Chest objs
            for game_object in util.worldobjects(client_world.mySubWorld.asNativeSubWorld):
                if util.getClassName(game_object) == "Loot" or util.getClassName(game_object) == "Chest":
                    logLoot(self, game_object, util.getClassName(game_object))
        else: 
            # We exited from a subworld and need to cleanup
            if not self.is_home: 
                # Check to see if we left early
                floor_logged = False
                for subworld_floor in self.current_subworld_looted_items:
                    if len(self.current_subworld_looted_items) != 0 and subworld_floor["floor"] == self.current_floor:
                        floor_logged = True
                
                if not floor_logged:
                    self.is_recalled = True
                    logFloorLoot(self, floor, zone)
                
                subprocess.run(['python', CLEAN_BOOSTS_PY])

                self.current_subworld_looted_items = []

                self.subworld_item_ids = []
                self.player_dropped_items_ids = []

                self.is_home = True
                self.new_subworld = False
                self.is_recalled = False
        
        self.draw = True

def logLoot(self, obj, class_name):
    """
    Logs Loot items within the subworld either coming from enemies or chests.
    This function ignores any items dropped from the player
    """
    client_world = self.refs.ClientWorld
    item_info = {}
    
    if obj.objId in self.current_floor_looted_items_ids or obj.objId in self.player_dropped_items_ids:
        return
    else:

        # We need to confirm if the other types of Loot are dropped from a chest
        if class_name == "Chest":
            chest = ffi.cast('struct Chest *', obj)
            
            # Wait till all items come out of the chest before running the logic
            if obj.objId not in self.current_floor_chests_ids and chest.pos == util.veclen(chest.angles):
                for item in reFieldToList(chest.items, 'struct ItemProperties *'):
                    for loot_obj in util.worldobjects(client_world.mySubWorld.asNativeSubWorld):
                        # Catch any ids that made it in already (Mostly misc)
                        if util.getClassName(loot_obj) == "Loot" and loot_obj.objId not in self.current_floor_looted_items_ids:
                            chest_loot = ffi.cast('struct Loot *', loot_obj)

                            # Compare memory addresses to see if they are the same
                            if str(item.classptr) == str(chest_loot.itemProps.classptr):
                                # We found a match
                                boosts_list = [] 
                                with open(BOOST_MAP, "r") as file:
                                    boost_map = json.load(file)

                                for boost in reFieldToList(chest_loot.itemProps.statboosts, 'struct StatBoost *'):
                                    boost_json = {
                                        "enum": ffi.string(ffi.cast("enum Stat", boost.stat)),
                                        "stat": boost.stat,
                                        "val": boost.val
                                    }

                                    boosts_list.append(boost_json)

                                looted_item = {
                                    "name": util.getstr(chest_loot.itemDesc.name),
                                    "boosts": boosts_list
                                }

                                formatted_time = time.strftime('%H:%M:%S', time.gmtime())

                                if not util.getstr(chest_loot.itemDesc.name) in FILTERED_ITEMS:
                                    
                                    # Check for MISC filter
                                    if slotType(chest_loot.itemDesc.slot) == "Miscellaneous":
                                        self.current_floor_looted_items_ids.append(loot_obj.objId)
                                    # Check for any other filter
                                    elif slotType(chest_loot.itemDesc.slot) != "Miscellaneous":

                                        self.current_floor_looted_items.append(looted_item)
                                        self.current_floor_looted_items_ids.append(loot_obj.objId)

                self.current_floor_chests_ids.append(obj.objId)       

def logFloorLoot(self, floor, zone):
    """
    Logs all the loot collected from logLoot and stores it within the floor_log file 
    This cleans any variables needed for the next floor of loot
    """

    # First case catches changing floors
    # Second case catches exiting on boss room
    # Third case catches leaves early (Floor 0 exit or homing back)
    if (zone not in IGNORED_ZONE and self.current_floor != floor) or (zone in IGNORED_ZONE and not self.is_home) or self.is_recalled:
        if DEBUG_MODE:
            logging.info("Floor Change!")

        with open(BOOST_COLLECTOR_LOG, 'a') as file:
            for item in self.current_floor_looted_items:
                if (item["boosts"] != []):
                    json.dump(item, file)
                    file.write('\n')

        log_data = { 
            "location": self.current_zone,
            "floor": self.current_floor,
        }

        self.current_subworld_looted_items.append(log_data)

        self.current_floor = floor
        self.current_zone = zone

        self.current_floor_looted_items_ids = []
        self.current_floor_looted_items = []
        self.current_floor_chests_ids = []

def reFieldToList(rf, itemtype=None):
    '''
    struct RepeatedField_int -> list
    struct RepeatedPtrField works too if there is a single struct to cast on all elements
    '''

    if rf.elements == ffi.NULL:
        return []
    lst = ffi.unpack(rf.elements, rf.current_size)
    if itemtype != None:
        for e in range(len(lst)):
            lst[e] = ffi.cast(itemtype, lst[e])
    return lst

def slotType(slot_value):
    """
    Helper function used to convert slot ints into readable strings
    """

    # If slot is zero, we know that the drop is a miscellaneous item
    if slot_value == ITEM_TYPES.MISC.value: 
        return "Miscellaneous"
    elif slot_value == ITEM_TYPES.SLOT_MAIN.value:
        return "Main"
    elif slot_value == ITEM_TYPES.SLOT_SECOND.value:
        return "Second"
    elif slot_value == ITEM_TYPES.SLOT_SPECIAL.value:
        return "Special"
    elif slot_value == ITEM_TYPES.SLOT_MOBILITY.value:
        return "Mobility"
    elif slot_value == ITEM_TYPES.SLOT_BODY.value:
        return "Body"
    
    return ""
