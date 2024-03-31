import logging
import os
import util
import time
import json
import ctypes

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
        self.current_looted_items = []
        
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
                

            for obj in util.worldobjects(cw.mySubWorld.asNativeSubWorld):
                if util.getClassName(obj) == "Loot":
                    logLoot(self, obj)
        else: 
            if not self.is_home: 
                with open(LOOT_LOGPATH, 'a') as file:
                    file.write('Exiting subworld...')
                    file.write('\n')

                    if DEBUG_MODE:
                        logging.info("Finished writing to Loot file")

                self.current_looted_items = []
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

def logBossZoneString(currentZone): 
        logString = currentZone
        if not logString.endswith("boss"): 
            logString += "_mid_boss"

        return logString;

def logLoot(self, obj):
    loot = ffi.cast('struct Loot *', obj)

    if str(loot) in self.current_looted_items:
        return
    else:
        logging.info("Loot Found!")
        self.current_looted_items.append(str(loot));

    item_info = {}
    item_type = ""
    item_prop = ffi.cast('struct ItemProperties *', loot)
    item_desc = loot.itemDesc
    
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

    # If slot is zero, we know that the drop is a miscellaneous item
    if item_desc.slot == MISC: 
        item_type = "Miscellaneous"
    elif item_desc.slot == SLOT_MAIN:
        item_type = "Main"
    elif item_desc.slot == SLOT_SECOND:
        item_type = "Second"
    elif item_desc.slot == SLOT_SPECIAL:
        item_type = "Special"
    elif item_desc.slot == SLOT_MOBILITY:
        item_type = "Mobility"
    elif item_desc.slot == SLOT_BODY:
        item_type = "Body"

    boosts = []
    stat_boosts = reFieldToList(item_prop.statboosts, 'struct StatBoost *')

    for boost in stat_boosts:
        if DEBUG_MODE:
            logging.info("StatBoost")
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

def writeToDebugFile(test_string): 
        with open(DEBUG_FILE_LOGPATH, 'a') as file:
            file.write(test_string)
            file.write('\n')
            if DEBUG_MODE:
                logging.info("Finished writing to Debug file")