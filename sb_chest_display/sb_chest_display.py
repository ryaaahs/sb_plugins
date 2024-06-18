import logging
import os
import util
import time
import json
import ctypes
import time
import math

from enum import Enum
from _remote import ffi, lib
from manager import PluginBase

BASEDIR = os.path.split(os.path.dirname(__file__))[0]

ITEMS_JSON = BASEDIR + '\\items.json'
BOOSTS_JSON = BASEDIR + '\\boosts.json'
DEBUG_MODE = False

ITEM_MODS = [
    "",
    "Modified",
    "Custom",
    "Experimental",
    "Prototype",
]

# Zones that we're ignoring
IGNORED_ZONE = (
    'home',
    'lobby'
)

class Plugin(PluginBase):
    def onInit(self, inputs=None):

        # Set config options 
        self.config.options('int', {
            'scd_text_display_size': 15,
            'scd_max_items_per_box': 20,
            'scd_width_edge_spacing': 15, # Default is 15
            'scd_text_y_spacing': 20,
            'scd_text_x_padding': 5,
            'scd_text_y_padding': 5,
        })

        self.config.options('color', {
            'scd_text_modified_label_colour': 0xff79f071,
            'scd_text_custom_label_colour': 0xff3d70f0,
            'scd_text_experimental_label_colour': 0xffd04ef0,
            'scd_text_prototype_label_colour': 0xfff0b03d,
            'scd_text_modified_colour': 0xff79f071,
            'scd_text_custom_colour': 0xff638cf3,
            'scd_text_experimental_colour': 0xffde83f4,
            'scd_text_prototype_colour': 0xfff6d291,
        })

        self.config.options('bool', {
            'scd_display_box': True,
        })
        
        # Set variables
        self.draw = False
        self.is_home = False
        self.new_subworld = False
        self.display_dict = {}
        self.longest_name = ""
        self.longest_boost_name = ""
        self.longest_boost_name_dict = {}
        self.longest_name_dict = {}
        self.total_boost_length = 0
        self.total_boost_length_dict = {}
        self.current_floor_chests_ids = []

        # Load the json items
        with open(ITEMS_JSON, 'r') as items:
            self.item_list = json.load(items)
        
        with open(BOOSTS_JSON, 'r') as items:
            self.boost_list = json.load(items)

        # Convert json lists to dictionarys
        self.item_list = {item['id']: item for item in self.item_list}

    def afterUpdate(self, inputs=None):
        self.draw = False
        
        client_world = self.refs.ClientWorld
        world_view = self.refs.WorldView

        if client_world == ffi.NULL or world_view == ffi.NULL: 
            return

        zone = util.getstr(client_world.asWorld.props.zone) or util.getstr(client_world.asWorld.props.music)
        
        if zone not in IGNORED_ZONE:
            if not self.new_subworld:
                self.new_subworld = True
                self.is_home = False

            for game_object in util.worldobjects(client_world.mySubWorld.asNativeSubWorld):

                    # We have a chest object 
                    if util.getClassName(game_object) == "Chest":
                        self.longest_name_object = util.PlainText(font='HemiHeadBold')
                        self.longest_boost_name_object = util.PlainText(font='HemiHeadBold')
                        self.total_boost_length = 0

                        chest = ffi.cast('struct Chest *', game_object)

                        if game_object.objId not in self.current_floor_chests_ids:

                            # Iterate through all the Items within the chest and store them within a display dict for later
                            self.display_dict[game_object.objId] = []
                            for item in reFieldToList(chest.items, 'struct ItemProperties *'):
                                
                                loot_item = self.item_list.get(item.type)

                                if (DEBUG_MODE):
                                    logging.info(self.item_list.get(item.type))
                                    logging.info(item.type)

                                boosts = reFieldToList(item.statboosts, 'struct StatBoost *')
                                logging_name = ITEM_MODS[len(boosts)] + " " + loot_item.get("name") if len(boosts) > 0 else loot_item.get("name")

                                item_display_name = addItemToLoggingDisplay(self, loot_item, logging_name, len(boosts), item.statboosts)
                                
                                if (self.longest_boost_name_object.text == "" or len(item_display_name["longest_boost_name_object"].text) > len(self.longest_boost_name_object.text)): 
                                    self.longest_boost_name_object = item_display_name["longest_boost_name_object"]

                                if (self.longest_name_object.text == "" or len(logging_name) > len(self.longest_name_object.text)): 
                                    self.longest_name_object = item_display_name["item_name_object"]

                                self.total_boost_length += len(boosts)
                                self.display_dict[game_object.objId].append(item_display_name)

                            self.current_floor_chests_ids.append(game_object.objId)
                        
                        if game_object.objId not in self.longest_name_dict:
                            self.longest_name_dict[game_object.objId] = self.longest_name_object
                            self.total_boost_length_dict[game_object.objId] = self.total_boost_length

                        if game_object.objId not in self.longest_boost_name_dict:
                            self.longest_boost_name_dict[game_object.objId] = self.longest_boost_name_object
        else: 
            # We exited from a subworld and need to cleanup
            if not self.is_home: 
                self.is_home = True
                self.new_subworld = False   

                self.display_dict = {}
                self.longest_name_dict = {}
                self.total_boost_length_dict = {}
                self.total_boosts_dict = {}

        self.draw = True

    def onPresent(self):

        # Draw checks and objects checks
        if not self.draw or not self.config.scd_display_box:
            return
        
        client_world = self.refs.ClientWorld
        world_view = self.refs.WorldView

        if client_world == ffi.NULL or world_view == ffi.NULL: 
            return

        canvas_width = self.refs.canvasW_[0]
        canvas_height = self.refs.canvasH_[0]
        
        # Item Display box
        for game_object in util.worldobjects(client_world.mySubWorld.asNativeSubWorld):
                if util.getClassName(game_object) == "Chest":

                    chest = ffi.cast('struct Chest *', game_object)
                    chest_props = game_object.props
                    
                    # Get chest X/Y to base our display off of
                    x = chest_props.xmp // 256 + chest_props.wmp // 512 - world_view.offset.x
                    y = chest_props.ymp // 256 - world_view.offset.y

                    # Window space coords
                    x = round(x / self.refs.scaleX)
                    y = round(y / self.refs.scaleY)

                    # Defining the scale of display
                    obj_longest_boost_name = self.longest_boost_name_dict[game_object.objId]
                    obj_longest_name = self.longest_name_dict[game_object.objId]

                    obj_longest_name_text = str(obj_longest_name.text, 'utf-8')
                    obj_longest_boost_name_text = str(obj_longest_boost_name.text, 'utf-8')

                    get_longest_name_object = obj_longest_name if len(obj_longest_name_text) > len(obj_longest_boost_name_text) else obj_longest_boost_name
                    height_scale = util.veclen(chest.angles) + self.total_boost_length_dict[game_object.objId] 

                    box_width = get_longest_name_object.w + self.config.scd_width_edge_spacing
                    # (self.config.scd_text_y_spacing * height_scale) + (self.config.scd_text_y_padding * 2)
                    #get_longest_name_object.h * height_scale + (self.config.scd_text_y_padding * height_scale) + self.config.scd_text_y_padding
                    box_height = (self.config.scd_text_y_spacing * height_scale) + (self.config.scd_text_y_padding * 2) 

                    # Remove display if the user opens the chest
                    if chest.pos == -1:
                        
                        if (height_scale > self.config.scd_max_items_per_box):
                            next_box_space = 0
                            item_display_box_array_index = 0

                            display_index = 0
                            item_display_list = [[], [], []]
                            sizes = [0, 0, 0]  
                            multi_display_height = height_scale
                            
                            box_height = (self.config.scd_text_y_spacing * self.config.scd_max_items_per_box) + (self.config.scd_text_y_padding * 2)

                            # Create dynamic display boxes
                            for i in range(math.ceil(height_scale / self.config.scd_max_items_per_box)):
                                if i == 0:
                                    next_box_space = (box_width) + (self.config.scd_text_x_padding)
                                    next_box_space = next_box_space * -1

                                else:
                                    next_box_space = (box_width * (i - 1)) + (self.config.scd_text_x_padding * (i - 1))
                                
                                # box x, box y, box width, box height, colour, mode
                                self.refs.XDL_FillRect(
                                    x - (box_width // 2) + next_box_space, y - box_height, box_width, box_height, 0xA0000000, lib.BLENDMODE_BLEND) 


                            # Organize the item display
                            # This will attempt to fill each box to 20
                            item_display_list_indexes = [[],[],[]]
                            sizes = [0, 0, 0]

                            for index, element in enumerate(self.display_dict[game_object.objId]):
                                item_length = len(element["boosts"]) + 1

                                for i in range(3): 
                                    if item_length + sizes[i] > 20:
                                        continue
                                    else:
                                        sizes[i] += item_length
                                        item_display_list_indexes[i].append(index)
                                        break

                            # Displaying the items
                            for i in range(len(item_display_list_indexes)):
                                display_index = 0

                                for j in range(len(item_display_list_indexes[i])):
                                    if i == 0:
                                        next_box_space = (box_width) + (self.config.scd_text_x_padding)
                                        next_box_space = next_box_space * -1
                                    else:
                                        next_box_space = (box_width * (i - 1)) + (self.config.scd_text_x_padding * (i - 1))
                                    
                                    loot = self.display_dict[game_object.objId][item_display_list_indexes[i][j]]
                                    loot["item"].draw((x - (box_width // 2) + next_box_space) + self.config.scd_text_x_padding, (y - box_height + (self.config.scd_text_y_spacing  * display_index)) + self.config.scd_text_y_padding)
                                    display_index += 1

                                    if (len(loot["boosts"]) != 0):
                                        for boost in loot["boosts"]:
                                            boost.draw((x - (box_width // 2) + next_box_space) + (self.config.scd_text_x_padding * 2), (y - box_height + (self.config.scd_text_y_spacing  * display_index)) + self.config.scd_text_y_padding)
                                            display_index += 1

                        else:
                            # If we only less than self.config.scd_max_items_per_box, only display one box
                            self.refs.XDL_FillRect(
                            x - (box_width // 2), y - box_height, box_width, box_height, 0xA0000000, lib.BLENDMODE_BLEND)

                            display_index = 0
                            for index, element in enumerate(self.display_dict[game_object.objId]):

                                element["item"].draw((x - (box_width // 2)) + self.config.scd_text_x_padding, (y - box_height + (self.config.scd_text_y_spacing  * display_index)) + self.config.scd_text_y_padding)
                                display_index += 1

                                if (len(element["boosts"]) != 0):
                                    for boost in element["boosts"]:
                                        boost.draw((x - (box_width // 2)) + (self.config.scd_text_x_padding * 2), (y - box_height + (self.config.scd_text_y_spacing  * display_index)) + self.config.scd_text_y_padding)
                                        display_index += 1
                            
                        if (DEBUG_MODE and chest.pos != util.veclen(chest.angles)):

                            box_width_text = util.PlainText(font='HemiHeadBold')
                            box_width_title_text = util.PlainText(font='HemiHeadBold')
                            box_height_text = util.PlainText(font='HemiHeadBold')
                            box_height_title_text = util.PlainText(font='HemiHeadBold')

                            
                            box_width_text.size = 20
                            box_width_text.text = str(box_width)
                        
                            box_height_text.size = 20
                            box_height_text.text = str(box_height)

                            box_width_text.draw(100, 500, anchorX=0.5, anchorY=-1)
                            box_height_text.draw(100, 500, anchorX=-3.5, anchorY=-1)
                            

                            box_width_title_text.size = 20
                            box_width_title_text.text = "Box Width"
                            box_height_title_text.size = 20
                            box_height_title_text.text = "Box Height"

                            
                            box_width_title_text.draw(100, 500, anchorX=0.5, anchorY=0.5)
                            
                            box_height_title_text.draw(100, 500, anchorX=-1, anchorY=0.5)

def writeToDebugFile(test_string): 
        with open(DEBUG_LOGPATH, 'a') as file:
            file.write(test_string)
            if DEBUG_MODE:
                logging.info("Finished writing to Debug file")

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

def addItemToLoggingDisplay(self, loot_item, name, boost_length, boosts):
    boosts_list = []
    label_colour = 0xffffff
    boost_colour = 0xffffff
    longest_boost_object = util.PlainText(font='HemiHeadBold')

    
    # Item
    item = util.PlainText(font='HemiHeadBold')
    item.size = self.config.scd_text_display_size
    item.text = name
    if boost_length != -1:
        if boost_length == 1:
            label_colour = self.config.scd_text_modified_label_colour
            boost_colour = self.config.scd_text_modified_colour
        if boost_length == 2:
            label_colour = self.config.scd_text_custom_label_colour
            boost_colour = self.config.scd_text_custom_colour
        if boost_length == 3:
            label_colour = self.config.scd_text_experimental_label_colour
            boost_colour = self.config.scd_text_experimental_colour
        if boost_length == 4:
            label_colour = self.config.scd_text_prototype_label_colour
            boost_colour = self.config.scd_text_prototype_colour

        item.color = label_colour

        # Boosts
        for boost in reFieldToList(boosts, 'struct StatBoost *'):
            text = "" 
            item_filtered_boost = ""

            if boost.stat == 43:
                if boost.val == 100:
                    filters = {
                        "name": "Armor Piercing",
                        "class": loot_item.get("class"),
                        "slot": loot_item.get("slot")
                    }
                
                else:
                    filters = {
                        "name": "Barbed",
                        "class": loot_item.get("class"),
                        "slot": loot_item.get("slot")
                    }

                item_filtered_boost = filter_boost(self.boost_list, boost.stat, filters)

                text += item_filtered_boost["name"]

            else:
                filters = {
                    "class": loot_item.get("class"),
                    "slot": loot_item.get("slot")
                }
                
                item_filtered_boost = filter_boost(self.boost_list, boost.stat, filters)
            
                text += item_filtered_boost["name"]
            
            if item_filtered_boost["display_type"] == 1:
                text += ": +" + str(boost.val)

            elif item_filtered_boost["display_type"] == 2:
                value = boost.val 
                if item_filtered_boost["divide_value"] == 1:
                    value = value / 100

                text += ": +" + str(value) + "%" 

            elif item_filtered_boost["display_type"] == 3:
                value = boost.val 
                if item_filtered_boost["divide_value"] == 1:
                    value = value / 100

                text += ": +" + str(value) + "x" 

            elif item_filtered_boost["display_type"] == 4:
                text += ": " + str(boost.val)

            elif item_filtered_boost["divide_value"] == 5:
                text += ": +" + str(boost.val) + "HP"

            boost_display = util.PlainText(font='HemiHeadBold')
            boost_display.size = self.config.scd_text_display_size
            boost_display.text = text
            boost_display.color = boost_colour 

            boosts_list.append(boost_display)

            if (longest_boost_object.text == "" or len(text) > len(longest_boost_object.text)): 
                longest_boost_object = boost_display

    return {
        "item": item,
        "boosts": boosts_list,
        "item_name_object": item,
        "longest_boost_name_object": longest_boost_object
    }

def filter_boost(boost_list, boost_id, filters):
    for boost in boost_list:        
        if boost.get("id") != boost_id:
            # Skip boosts that do not match the specified boost_id
            continue

        match = True
        for key, value in filters.items():
            if key == "slot" or key == "class":
                # Check if the value is an array
                if isinstance(value, list):
                    # Check if any value in the array matches boost's value
                    if not any(val in boost.get(key, []) for val in value):
                        match = False
                        break
                else:
                    if value not in boost[key]:
                        match = False
                        break
            else:
                # Check if the boost has the key and its value matches
                if key not in boost or value != boost[key]:
                    match = False
                    break

        if match:
            return boost
    
    return {}