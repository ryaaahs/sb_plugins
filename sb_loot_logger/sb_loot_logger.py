import logging
import os
import util
import time
import json
import ctypes
import time

from _remote import ffi, lib
from manager import PluginBase

BASEDIR = os.path.split(os.path.dirname(__file__))[0]

SB_LOOT_LOGGER_FOLDER = BASEDIR + '\\sblootlogger'

SUBWORLD_LOOT_LOGPATH = SB_LOOT_LOGGER_FOLDER + '\\subworld_loot.log'
FLOOR_LOOT_LOGPATH = SB_LOOT_LOGGER_FOLDER + '\\floor_loot.log'

DEBUG_LOGPATH = SB_LOOT_LOGGER_FOLDER + '\\debug.txt'

ITEMS_JSON = SB_LOOT_LOGGER_FOLDER + '\\items.json'

DEBUG_MODE = True

#TODO Missing IMPLANT
MISC = 0
SLOT_MAIN = 256
SLOT_SECOND = 512
SLOT_SPECIAL = 768
SLOT_MOBILITY = 1280
SLOT_BODY = 1024

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
        if not os.path.exists(SUBWORLD_LOOT_LOGPATH):
            with open(SUBWORLD_LOOT_LOGPATH, "w"):
                pass
            if DEBUG_MODE:
                logging.info("~~~~~~~~~~~~~~")
                logging.info("Subworld loot file has been created")
        elif DEBUG_MODE:
                logging.info("~~~~~~~~~~~~~~")
                logging.info("Subworld loot file has not been created")
        
        if not os.path.exists(FLOOR_LOOT_LOGPATH):
            with open(FLOOR_LOOT_LOGPATH, "w"):
                pass
            if DEBUG_MODE:
                logging.info("Floor loot file has been created")
        elif DEBUG_MODE:
                logging.info("Floor loot file has not been created")

        if not os.path.exists(DEBUG_LOGPATH) and DEBUG_MODE:
            with open(DEBUG_LOGPATH, "w"):
                pass
            if DEBUG_MODE:
                logging.info("Debug file has been created")
                logging.info("~~~~~~~~~~~~~~")
        elif DEBUG_MODE:
                logging.info("Debug file has not been created")
                logging.info("~~~~~~~~~~~~~~")

    

    def afterUpdate(self, inputs=None):
        client_world = self.refs.ClientWorld
        world_view = self.refs.WorldView
        if client_world == ffi.NULL or world_view == ffi.NULL: return
        
        cwprops = client_world.asWorld.props
        zone = util.getstr(client_world.asWorld.props.zone) or util.getstr(client_world.asWorld.props.music)
        floor = cwprops.floor;
        
        # Log floor loot
        logFloorLoot(self, floor, zone)

        # If we're not in the ignored zones 
        if zone not in IGNORED_ZONE:
            # Check to see if were in a new sub world within the game
            if not self.new_subworld:
                log_data = {
                    "date": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), 
                    "location": zone
                }
                with open(FLOOR_LOOT_LOGPATH, 'a') as file:
                    file.write('Entering subworld...')
                    file.write('\n')
                    json.dump(log_data, file)
                    file.write('\n')

                    if DEBUG_MODE:
                        logging.info("Finished writing to Loot file")
                self.new_subworld = True
                self.is_home = False
                self.current_floor = floor 
                self.current_zone = zone

            # Iterate through all the game objects and search for Loot or Chest objs
            for obj in util.worldobjects(client_world.mySubWorld.asNativeSubWorld):
                if util.getClassName(obj) == "Loot" or util.getClassName(obj) == "Chest":
                    logLoot(self, obj, util.getClassName(obj))
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

                with open(FLOOR_LOOT_LOGPATH, 'a') as file:
                    file.write('Exiting subworld...')
                    file.write('\n')

                    if DEBUG_MODE:
                        logging.info("Finished writing to Loot file")
                
                log_data = {
                    "date": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), 
                    "location": self.current_zone,
                    "subworld_loot": self.current_subworld_looted_items,
                }

                # Write the entire subworld loot to file
                with open(SUBWORLD_LOOT_LOGPATH, 'a') as file:
                    json.dump(log_data, file)
                    file.write('\n')

                if DEBUG_MODE:
                    logging.info("Finished writing to Loot file")

                self.current_subworld_looted_items = []

                self.subworld_item_ids = []
                self.player_dropped_items_ids = []

                self.is_home = True
                self.new_subworld = False
                self.is_recalled = False


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
        if (class_name == "Loot"):
            lootDebugDisplay(obj)
            loot = ffi.cast('struct Loot *', obj)

        # We need to confirm if the other types of Loot are dropped from a chest
        if class_name == "Chest":
            chest = ffi.cast('struct Chest *', obj)
            
            # Wait till all items come out of the chest before running the logic
            if obj.objId not in self.current_floor_chests_ids and chest.pos == util.veclen(chest.angles):
                for item in  reFieldToList(chest.items, 'struct ItemProperties *'):
                    for loot_obj in util.worldobjects(client_world.mySubWorld.asNativeSubWorld):
                        # Catch any ids that made it in already (Mostly misc)
                        if util.getClassName(loot_obj) == "Loot" and loot_obj.objId not in self.current_floor_looted_items_ids:
                            chest_loot = ffi.cast('struct Loot *', loot_obj)
                            # Compare memory addresses to see if they are the same
                            if str(item.classptr) == str(chest_loot.itemProps.classptr):
                                # We found a match
                                boosts_list = [] 

                                for boost in reFieldToList(chest_loot.itemProps.statboosts, 'struct StatBoost *'):
                                    boost_json = {
                                        "stat": boost.stat,
                                        "val": boost.val,
                                    }

                                    boosts_list.append(boost_json)

                                looted_item = {
                                    "id": loot_obj.objId,
                                    "name": util.getstr(chest_loot.itemDesc.name),
                                    "type_id": chest_loot.itemProps.type,
                                    "slot": chest_loot.itemDesc.slot,
                                    "boosts": boosts_list,
                                }

                                self.current_floor_looted_items.append(looted_item)
                                self.current_floor_looted_items_ids.append(loot_obj.objId)
                self.current_floor_chests_ids.append(obj.objId)       
        elif slotType(loot.itemDesc.slot) == "Miscellaneous":

            looted_item = {
                "id": obj.objId,
                "name": util.getstr(loot.itemDesc.name),
                "type_id": loot.itemProps.type,
                "slot": loot.itemDesc.slot,
                "boosts": [],
            }

            self.current_floor_looted_items.append(looted_item)
            self.current_floor_looted_items_ids.append(obj.objId)
        else:
            # If the item is not part of a chest, it was dropped by a player and we add to the ignore list
            if obj.objId in self.player_dropped_items_ids:
                return
            else:
                self.player_dropped_items_ids.append(obj.objId)

def logFloorLoot(self, floor, zone):
    """
    Logs all the loot collected from logLoot and stores it within the floor_log file 
    This cleans any variables needed for the next floor of loot
    """

    # First case catches changing floors
    # Second case catches exiting on boss room
    # Third case catches leaves early (Floor 0 exit or homing back)
    if (zone not in IGNORED_ZONE and self.current_floor != floor) or (zone in IGNORED_ZONE and not self.is_home) or self.is_recalled:
        logging.info("Floor Change!")

        log_data = {
            "date": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), 
            "location": self.current_zone,
            "floor": self.current_floor,
            "floor_loot": self.current_floor_looted_items
        }

        with open(FLOOR_LOOT_LOGPATH, 'a') as file:
                json.dump(log_data, file)
                file.write('\n')

                if DEBUG_MODE:
                    logging.info("Finished writing to Loot file")

        self.current_floor = floor
        self.current_zone = zone

        self.current_subworld_looted_items.append(log_data)

        self.current_floor_looted_items_ids = []
        self.current_floor_looted_items = []
        self.current_floor_chests_ids = []

def lootDebugDisplay(obj):
    """
    Helper function used to display struct information of important C++ objects used within this plugin
    """

    logging.info("New Loot Found!")
            
    loot = ffi.cast('struct Loot *', obj)
    item_prop = loot.itemProps
    item_desc = loot.itemDesc
    item_type = slotType(item_desc.slot)

    if DEBUG_MODE:
        logging.info("----")
        logging.info("ItemProperties")
        logging.info(" - Type: " + str(item_prop.type))
        logging.info(" - Slotpos: " + str(item_prop.slotpos))
        logging.info(" - _cached_size: " + str(item_prop._cached_size))
        logging.info(" - _has_bits:" + str(item_prop._has_bits))
        logging.info("ItemDescription")
        logging.info(" - name:" + util.getstr(item_desc.name))
        logging.info(" - type:" + str(item_desc.type))
        logging.info(" - build:" + str(item_desc.build))
        logging.info(" - tier:" + str(item_desc.tier))
        logging.info(" - price:" + str(item_desc.price))
        logging.info(" - currency:" + str(item_desc.currency))
        logging.info(" - itemclass:" + str(item_desc.itemclass))
        logging.info(" - itemsubclass:" + str(item_desc.itemsubclass))
        logging.info(" - slot:" + str(item_desc.slot))

        if item_prop.statboosts != ffi.NULL and item_desc.slot != MISC: 
            for boost in reFieldToList(item_prop.statboosts, 'struct StatBoost *'):
                if DEBUG_MODE:
                    logging.info("StatBoost")
                    logging.info(boost)
                    logging.info(" - stat: " + str(boost.stat))
                    logging.info(" - val: " + str(boost.val))
                    logging.info(" - level: " + str(boost.level))
                    try:
                        logging.info(" - increment:" + str(boost.increment))
                    except Exception:
                        logging.info(" - increment:" + str(0))
                    logging.info(" - subtypestr:" + util.getstr(boost.subtypestr))
                    logging.info(" - subtype:" + str(boost.subtype))
                    logging.info(" - _has_bits:" + str(boost._has_bits))
                    logging.info("----")
        else:
            logging.info("StatBoost")
            logging.info("----")

def writeToDebugFile(test_string): 
        with open(DEBUG_LOGPATH, 'a') as file:
            file.write(test_string)
            if DEBUG_MODE:
                logging.info("Finished writing to Debug file")

def slotType(slot_value):
    """
    Helper function used to convert slot ints into readable strings
    """

    # If slot is zero, we know that the drop is a miscellaneous item
    if slot_value == MISC: 
        return "Miscellaneous"
    elif slot_value == SLOT_MAIN:
        return "Main"
    elif slot_value == SLOT_SECOND:
        return "Second"
    elif slot_value == SLOT_SPECIAL:
        return "Special"
    elif slot_value == SLOT_MOBILITY:
        return "Mobility"
    elif slot_value == SLOT_BODY:
        return "Body"
    
    return ""

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