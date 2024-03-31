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
LOOT_LOGPATH = BASEDIR + '\\loot_log.txt'
DEBUG_FILE_LOGPATH = BASEDIR + '\\debug_file.txt'
ITEMS_JSON = BASEDIR + '\\items.json'
DEBUG_MODE = True
MISC = 0
SLOT_MAIN = 256
SLOT_SECOND = 512
SLOT_SPECIAL = 768
SLOT_MOBILITY = 1280
SLOT_BODY = 1024


# List of midboss floors
# TODO Look into a dynamic way of figuring out mid bosses.
MID_BOSS = {
    'forest': 4,
    'forestHard': 4,
    'ice': 3,
    'iceHard': 3
}

# Zones that we're ignoring
IGNORED_ZONE = (
    'home',
    'lobby'
) 

class Plugin(PluginBase):
    def onInit(self, inputs=None):
        self.do_chest_log = True
        self.new_subworld = False
        self.is_home = True
        self.current_floor_looted_items = []
        self.current_floor_chests = []
        self.current_subworld_looted_items = []
        self.current_floor = 0
        self.current_zone = ""
        
        # Check to see if files exists before using them later
        if not os.path.exists(LOOT_LOGPATH):
            with open(LOOT_LOGPATH, "w"):
                pass
            if DEBUG_MODE:
                logging.info("Loot file has been created")
        if DEBUG_MODE:
                logging.info("Loot file has not been created")

        if not os.path.exists(DEBUG_FILE_LOGPATH) and DEBUG_MODE:
            with open(DEBUG_FILE_LOGPATH, "w"):
                pass
            if DEBUG_MODE:
                logging.info("Debug file has been created")
        if DEBUG_MODE:
                logging.info("Debug file has not been created")

    

    def afterUpdate(self, inputs=None):
        cw = self.refs.ClientWorld
        wv = self.refs.WorldView
        if cw == ffi.NULL or wv == ffi.NULL: return
        
        cwprops = cw.asWorld.props
        zone = util.getstr(cw.asWorld.props.zone) or util.getstr(cw.asWorld.props.music)
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
                with open(LOOT_LOGPATH, 'a') as file:
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

            for obj in util.worldobjects(cw.mySubWorld.asNativeSubWorld):
                if util.getClassName(obj) == "Loot" or util.getClassName(obj) == "Chest":
                    logLoot(self, obj, util.getClassName(obj))
        else: 
            if not self.is_home: 
                with open(LOOT_LOGPATH, 'a') as file:
                    file.write('Exiting subworld...')
                    file.write('\n')

                    if DEBUG_MODE:
                        logging.info("Finished writing to Loot file")

                self.current_subworld_looted_items = []
                self.is_home = True
                self.new_subworld = False

def reFieldToList(rf, itemtype=None):
    '''struct RepeatedField_int -> list
    struct RepeatedPtrField works too if there is a single struct to cast on all elements'''

    if rf.elements == ffi.NULL:
        return []
    lst = ffi.unpack(rf.elements, rf.current_size)
    if itemtype != None:
        for e in range(len(lst)):
            lst[e] = ffi.cast(itemtype, lst[e])
    return lst

def logMidBossZoneString(current_zone, current_floor): 
    zone_string = current_zone
    
    if (current_zone in MID_BOSS and MID_BOSS[current_zone] == current_floor):
        zone_string += "_mid_boss"
    else: 
        # If we don't have it, return the original string
        return current_zone

    return zone_string;

def logLoot(self, obj, class_name):
    cw = self.refs.ClientWorld

    if (class_name == "Loot"):
        loot = ffi.cast('struct Loot *', obj)
        item_prop = loot.itemProps
        item_desc = loot.itemDesc
        item_type = slotType(item_desc.slot)

    item_info = {}
    
    if obj.objId in self.current_floor_looted_items:
        return
    else:
        logging.info("New Loot Found!")

        if class_name == "Loot" and item_type == "Miscellaneous":
            logging.info(util.getstr(loot.itemDesc.name) + ": " + str(obj.objId))
            self.current_floor_looted_items.append(obj.objId)
        else:
            # We need to confirm if the other types of Loot are dropped from a chest
            if class_name == "Chest":
                chest = ffi.cast('struct Chest *', obj)
                
                # Wait till all items come out of the chest before running the logic
                if obj.objId not in self.current_floor_chests and chest.pos == util.veclen(chest.angles):
                    for item in  reFieldToList(chest.items, 'struct ItemProperties *'):
                        for loot_obj in util.worldobjects(cw.mySubWorld.asNativeSubWorld):
                            # Catch any ids that made it in already (Mostly misc)
                            if util.getClassName(loot_obj) == "Loot" and loot_obj.objId not in self.current_floor_looted_items:
                                chest_loot = ffi.cast('struct Loot *', loot_obj)
                                # Compare memory addresses to see if they are the same
                                if str(item.classptr) == str(chest_loot.itemProps.classptr):
                                    # We found a match
                                    self.current_floor_looted_items.append(loot_obj.objId)
                    self.current_floor_chests.append(obj.objId);

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
        with open(DEBUG_FILE_LOGPATH, 'a') as file:
            file.write(test_string)
            if DEBUG_MODE:
                logging.info("Finished writing to Debug file")

def slotType(slot_value):
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


def logFloorLoot(self, floor, zone):
    if (zone not in IGNORED_ZONE and self.current_floor != floor) or (zone in IGNORED_ZONE and not self.is_home) :
        logging.info("Floor Change!")

        log_data = {
            "date": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), 
            "location": logMidBossZoneString(self.current_zone, self.current_floor),
            "floor": self.current_floor,
            "floor_loot": self.current_floor_looted_items
        }

        with open(LOOT_LOGPATH, 'a') as file:
                file.write('Floor: ' + str(self.current_floor))
                file.write('\n')
                json.dump(log_data, file)
                file.write('\n')

                if DEBUG_MODE:
                    logging.info("Finished writing to Loot file")

        self.current_floor = floor
        self.current_zone = zone
        self.current_subworld_looted_items.append(self.current_floor_looted_items)
        self.current_floor_looted_items = []
        self.current_floor_chests = []