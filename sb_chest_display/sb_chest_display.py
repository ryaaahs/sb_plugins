import logging
import os
import util
import json

from sb_gui import *

# from plugins.sb_gui import *

from enum import Enum
from _remote import ffi, lib
from manager import PluginBase

BASEDIR = os.path.split(os.path.dirname(__file__))[0]

ITEMS_JSON = BASEDIR + "\\items.json"
BOOSTS_JSON = BASEDIR + "\\boosts.json"
DEBUG_MODE = False

ITEM_MODS = [
    "",
    "Modified",
    "Custom",
    "Experimental",
    "Prototype",
]

# Zones that we're ignoring
IGNORED_ZONE = ("home", "lobby")

class Graphic:  # make subclass of PluginBase?
    def __init__(self, refs):
        self.refs = refs
        self.x = -1
        self.y = -1
        self.w = 0
        self.h = 0
        self.draw_top_border = False
        self.draw_bottom_border = False
        self.draw_right_border = False
        self.draw_left_border = False
        self.fill_rect = 0xFF2B2B2B
        self.fill_rect_blend = lib.BLENDMODE_BLEND
        self.draw_rect = 0xFFA0A0A0
        self.draw_rect_blend = lib.BLENDMODE_BLEND

    # Toggle the border display
    def drawTopBorder(self):
        self.draw_top_border ^= True

    def drawBottomBorder(self):
        self.draw_bottom_border ^= True

    def drawRightBorder(self):
        self.draw_right_border ^= True

    def drawLeftBorder(self):
        self.draw_left_border ^= True

    def drawBorder(self):
        self.drawTopBorder()
        self.drawBottomBorder()
        self.drawRightBorder()
        self.drawLeftBorder()

    def draw(self):  # draws background
        cw = self.refs.canvasW_[0]
        ch = self.refs.canvasH_[0]

        self.refs.canvasW_[0] = self.refs.windowW
        self.refs.canvasH_[0] = self.refs.windowH

        if type(self.fill_rect) == "str":
            self.fill_rect = int(str(fill_rect), 16)
        if type(self.draw_rect) == "str":
            self.draw_rect = int(str(draw_rect), 16)

        self.refs.XDL_FillRect(
            self.x, self.y, self.w, self.h, self.fill_rect, self.fill_rect_blend
        )

        x = self.x if self.draw_top_border == True else 0
        y = self.y if self.draw_bottom_border == True else 0
        w = self.w if self.draw_right_border == True else 0
        h = self.h if self.draw_left_border == True else 0

        self.refs.XDL_DrawRect(x, y, w, h, self.draw_rect, self.fill_rect_blend)

        self.refs.canvasW_[0] = cw
        self.refs.canvasH_[0] = ch


class GraphicWindow(Graphic):
    def __init__(self, refs):
        super().__init__(refs)
        self.panel_spacing_w = 3
        self.panel_spacing_h = 20
        self.text_position = 0
        self.base_window_y = 0
        self.panels = []
        self.panel_is_first_item = True

    def addPanelGroup(self, panel_group):
        self.panels.append(panel_group)

    def addLabel(self, text=None, position=1, colour=0xFFFFFF):
        self.panels.append(
            GraphicPanelLabel(self.refs, self, self, text, position, colour)
        )

    def addPanelDivider(self, text=None):
        self.panels.append(GraphicPanelDivider(self.refs, self, self))

    def defineWindow(self, panels, in_child):
        if not in_child:
            self.w = 0
            self.h = 0

        for panel in panels:
            if isinstance(panel, PanelGroup):
                self.defineWindow(panel.panels, True)
            else:
                self.w = max(self.w, panel.w + 2 * self.panel_spacing_w)
                self.h += panel.h

    def renderNestedPanels(self, panels):
        for panel in panels:
            if isinstance(panel, PanelGroup):
                # levels = 1
                if self.panel_is_first_item:
                    self.text_position += panel.reset(
                        self.x, self.text_position + 1, self.w, 1, self.base_window_y
                    )
                    self.panel_is_first_item = False
                else:
                    self.text_position += panel.reset(
                        self.x, self.text_position, self.w, 1, self.base_window_y
                    )
                self.renderNestedPanels(panel.panels)
            else:
                if not isinstance(panel.parent, PanelGroup):
                    panel.x = self.panel_spacing_w
                    panel.y = self.text_position

                    self.text_position += panel.h 

                    self.x = min(self.x, self.refs.windowW - self.w)
                    self.y = (
                        self.y
                        if self.y + self.h < self.refs.windowH
                        else max(self.y - self.h, 0)
                    )
            self.panel_is_first_item = False
        
    def reset(self, x, y):
        self.text_position = 0
        self.x = x
        self.y = y
        self.base_window_y = y
        # Calculate window and panel values
        # self.defineWindow(self.panels)
        self.renderNestedPanels(self.panels)

    def draw(self):
        super().draw()
        for panel in self.panels:
            panel.draw()


class PanelGroup(Graphic):
    def __init__(self, refs, window, tag=None):
        super().__init__(refs)
        self.tag = tag
        self.window = window
        self.parent = None
        self.set_fill_rect = ""
        self.set_draw_rect = ""
        self.panel_spacing_w = 3
        self.panel_spacing_h = 20
        self.text_position = 0
        self.base_window_y = 0
        self.levels = 0
        self.panels = []

    def addPanelGroup(self, panel_group):
        self.panels.append(panel_group)
        panel_group.parent = self

    def addLabel(self, text=None, position=1, colour=0xFFFFFF):
        self.panels.append(
            GraphicPanelLabel(self.refs, self.window, self, text, position, colour)
        )

    def addPanelDivider(self, text=None):
        self.panels.append(GraphicPanelDivider(self.refs, self.window, self))

    def changeFillRectColour(self, hexcode):
        self.set_fill_rect = hexcode

    def changeDrawRectColour(self, hexcode):
        self.set_draw_rect = hexcode

    def defineWindow(self, panels):
        for panel in panels:
            if isinstance(panel, PanelGroup):
                self.defineWindow(panel.panels)
            else:
                self.w = max(self.w, panel.w + 2 * self.panel_spacing_w)
                self.h += panel.h

    def setDisplayColour(self):
        if self.set_fill_rect == "" and self.parent != None:
            if self.parent.set_fill_rect != "":
                self.fill_rect = self.parent.set_fill_rect
        elif self.set_fill_rect != "":
            self.fill_rect = self.set_fill_rect

        if self.set_draw_rect == "" and self.parent != None:
            if self.parent.set_draw_rect != "":
                self.draw_rect = self.parent.set_draw_rect
        elif self.set_draw_rect != "":
            self.draw_rect = self.set_draw_rect

    def renderNestedPanels(self, panels, x, y):
        for panel in panels:
            if isinstance(panel, PanelGroup):
                self.text_position += panel.reset(
                    x, self.text_position + self.panel_spacing_h, self.w, 1, self.base_window_y
                )
            else:
                panel.x = self.panel_spacing_w + (self.levels * 5)
                panel.y = self.text_position

                self.text_position += panel.h 

                self.x = min(x, self.refs.windowW - self.w)
                self.y = (
                    (y + self.base_window_y)
                    if y + self.h < self.refs.windowH
                    else max(y - self.h, 0)
                )

    def reset(self, x, y, width, levels, base_window_y):
        # Grab parent colours if we have none
        self.setDisplayColour()

        # Calculate window and panel values
        self.base_window_y = base_window_y
        self.levels += levels

        self.text_position = y
        
        self.defineWindow(self.panels)
        self.w = self.w - 1
        self.h = self.h - 2
        
        self.renderNestedPanels(self.panels, x, y)

        return self.h

    def draw(self):
        super().draw()
        for panel in self.panels:
            panel.draw()


class GraphicPanel(Graphic):  # TODO: get refs from window
    def __init__(self, refs, window):
        super().__init__(refs)

        self.window = window

    def draw(self):
        pass


class GraphicPanelDivider(GraphicPanel):
    def __init__(self, refs, window, parent):
        super().__init__(refs, window)
        self.h = 4
        self.parent = parent

    def draw(self):
        cw = self.refs.canvasW_[0]
        ch = self.refs.canvasH_[0]
        self.refs.canvasW_[0] = self.refs.windowW
        self.refs.canvasH_[0] = self.refs.windowH
        # XDL_DrawLine(int x0, int y0, int x1, int y1, XDL_Color color, enum BlendMode blendMode)
        self.refs.XDL_DrawLine(
            self.window.x + 11,
            self.window.y + self.y,
            self.window.x + self.window.w - 11,
            self.window.y + self.y,
            0xFF808080,
            lib.BLENDMODE_BLEND,
        )
        self.refs.canvasW_[0] = cw
        self.refs.canvasH_[0] = ch


class GraphicPanelLabel(GraphicPanel):
    def __init__(self, refs, window, parent, text=None, position=1, colour=0xFFFFFF):
        super().__init__(refs, window)
        self.h = 22
        self.position = position
        self.parent = parent
        self.text_spacing_x = 10 * position
        self.label_spacing_x = 32
        self.text_spacing_y = 5
        self.colour = colour
        self.text_obj = util.PlainText(
            size=13, outlineSize=0
        )  # Size should be 12 but real font size is set to 10
        self.text_obj.color = self.colour
        self.text_ready = False
        if text != None:
            self.setText(text)

    def setText(self, string):
        if string:
            self.text_obj.text = string
            self.text_obj.updateTexture()
            self.w = self.text_obj.w + 2 * self.label_spacing_x
            self.text_ready = True
        else:
            self.w = 2 * self.label_spacing_x
            self.text_ready = False

    def draw(self):
        if self.text_ready:
            self.text_obj.draw(
                self.window.x + self.x + self.text_spacing_x,
                self.window.y + self.y + self.text_spacing_y,
            )

class Plugin(PluginBase):
    def onInit(self, inputs=None):

        # Set config options
        self.config.options(
            "int",
            {
                "scd_text_display_size": 15,
                "scd_max_items_per_box": 20,
                "scd_width_edge_spacing": 15,  # Default is 15
                "scd_text_y_spacing": 20,
                "scd_text_x_padding": 5,
                "scd_text_y_padding": 5,
            },
        )

        self.config.options(
            "color",
            {
                "scd_text_modified_label_colour": 0xFF1DB113,
                "scd_text_custom_label_colour": 0xFF3D70F0,
                "scd_text_experimental_label_colour": 0xFFD04EF0,
                "scd_text_prototype_label_colour": 0xFFF0B03D,
                "scd_text_modified_colour": 0xFF79F071,
                "scd_text_custom_colour": 0xFF638CF3,
                "scd_text_experimental_colour": 0xFFDE83F4,
                "scd_text_prototype_colour": 0xFFF6D291,
            },
        )

        self.config.options(
            "bool",
            {
                "scd_display_box": True,
                "scd_ec_uc_compress": True,
            },
        )

        # Set variables
        self.draw = False
        self.is_home = False
        self.new_subworld = False
        self.display_dict = {}
        self.ec_dict = {}
        self.uc_dict = {}
        self.longest_name = ""
        self.longest_boost_name = ""
        self.longest_boost_name_dict = {}
        self.longest_name_dict = {}
        self.chest_length_dict = {}
        self.current_floor_chests_ids = []

        # Load the json items
        with open(ITEMS_JSON, "r") as items:
            self.item_list = json.load(items)

        with open(BOOSTS_JSON, "r") as items:
            self.boost_list = json.load(items)

        # Convert json lists to dictionarys
        self.item_list = {item["id"]: item for item in self.item_list}

    def afterUpdate(self, inputs=None):
        self.draw = False

        client_world = self.refs.ClientWorld
        world_view = self.refs.WorldView

        if client_world == ffi.NULL or world_view == ffi.NULL:
            return

        zone = util.getstr(client_world.asWorld.props.zone) or util.getstr(
            client_world.asWorld.props.music
        )

        if zone not in IGNORED_ZONE:
            if not self.new_subworld:
                self.new_subworld = True
                self.is_home = False

            for game_object in util.worldobjects(
                client_world.mySubWorld.asNativeSubWorld
            ):

                # We have a chest object
                if util.getClassName(game_object) == "Chest":
                    chest_length = 0
                    total_ec_value = 0
                    total_uc_value = 0


                    chest = ffi.cast("struct Chest *", game_object)

                    if game_object.objId not in self.current_floor_chests_ids:

                        # Iterate through all the Items within the chest and store them within a display dict for later
                        self.display_dict[game_object.objId] = []
                        self.ec_dict[game_object.objId] = 0
                        self.uc_dict[game_object.objId] = 0
                        for item in reFieldToList(
                            chest.items, "struct ItemProperties *"
                        ):

                            loot_item = self.item_list.get(item.type)

                            if DEBUG_MODE:
                                logging.info(self.item_list.get(item.type))
                                logging.info(item.type)

                            boosts = reFieldToList(
                                item.statboosts, "struct StatBoost *"
                            )

                            if (self.config.scd_ec_uc_compress):
                                item_name = loot_item.get("name")
                                if "EC" in item_name:
                                    total_ec_value += int(item_name.split(' ', 1)[0])
                                    continue
                                elif "UC" in item_name:
                                    total_uc_value += int(item_name.split(' ', 1)[0])
                                    continue

                            logging_name = (
                                ITEM_MODS[len(boosts)] + " " + loot_item.get("name")
                                if len(boosts) > 0
                                else loot_item.get("name")
                            )

                            item_display_name = addItemToLoggingDisplay(
                                self,
                                loot_item,
                                logging_name,
                                len(boosts),
                                item.statboosts,
                            )

                            chest_length += len(boosts) + 1 if len(boosts) > 0 else 1
                            self.display_dict[game_object.objId].append(item_display_name)

                        self.current_floor_chests_ids.append(game_object.objId)
                        
                        if (total_ec_value > 0):
                            self.display_dict[game_object.objId].append(addPlainToLoggingDisplay(
                                self,
                                str(total_ec_value) + " EC"
                            ))
                        if (total_uc_value > 0):
                            self.display_dict[game_object.objId].append(addPlainToLoggingDisplay(
                                self,
                                str(total_uc_value) + " UC"
                            ))

                    if game_object.objId not in self.chest_length_dict:
                        self.chest_length_dict[game_object.objId] = chest_length
        else:
            # We exited from a subworld and need to cleanup
            if not self.is_home:
                self.is_home = True
                self.new_subworld = False

                self.display_dict = {}
                self.chest_length_dict = {}
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

                chest = ffi.cast("struct Chest *", game_object)
                chest_props = game_object.props
                display_x_spacing = 25
                display_y_spacing = 15

                # Get chest X/Y to base our display off of
                x = (
                    chest_props.xmp // 256
                    + chest_props.wmp // 512
                    - world_view.offset.x
                )
                y = chest_props.ymp // 256 - world_view.offset.y

                # Window space coords
                x = round(x / self.refs.scaleX)
                y = round(y / self.refs.scaleY)

                # Remove display if the user opens the chest
                if chest.pos == -1:
                    displays = []
                    # Base display [ [1**] [] [] ]
                    displays.append(GraphicWindow(self.refs))
                    
                    max_item_base = 20
                    
                    display_index = 0
                    panel_group_number = 0
                    text_element_index = 0
                    # chest_length = 0
                    total_displays = 0

                    # for element in self.display_dict[game_object.objId]:
                    #     if len(element["boosts"]) > 0:
                    #         for boost_elements in element["boosts"]:
                    #             chest_length += 1
                    #     chest_length += 1

                    if (self.chest_length_dict[game_object.objId] <= max_item_base):
                        total_displays = 1
                    elif (self.chest_length_dict[game_object.objId] <= (max_item_base * 2)):
                        total_displays = 2
                    else:
                        total_displays = 3
                    
                    max_item_display = max_item_base if total_displays == 1 else int(self.chest_length_dict[game_object.objId] / total_displays)

                    for index, element in enumerate(self.display_dict[game_object.objId]):
                        if (text_element_index >= max_item_display):
                            displays.append(GraphicWindow(self.refs))
                            display_index += 1
                            text_element_index = 0

                        if len(element["boosts"]) == 0:
                            text_element_index += 1

                            displays[display_index].addLabel(element["item"]["text"])

                             # First check to see if we are not on the max display
                            # Second, check to see if we are at the end of the display dict list
                            if text_element_index < max_item_display and index != len(self.display_dict[game_object.objId]) - 1: 
                                displays[display_index].addPanelDivider() 
                            
                            
                        else:
                            panel_group_number += 1
                            panel_group = PanelGroup(
                                self.refs, displays[display_index], "pg" + str(panel_group_number)
                            )
                            
                            text_element_index += 1
                            panel_group.addLabel(
                                element["item"]["text"],
                                0,
                                element["item"]["label_colour"],
                            )
                            

                            for boost_elements in element["boosts"]:
                                text_element_index += 1 
                                panel_group.addLabel(
                                    boost_elements["text"], 1, boost_elements["colour"]
                                )   
                            # First check to see if we are not on the max display
                            # Second, check to see if we overflow on max display
                            # Third, check to see if we are at the end of the display dict list
                            if text_element_index < max_item_display and index != len(self.display_dict[game_object.objId]) - 1: 
                                panel_group.addPanelDivider()

                            displays[display_index].addPanelGroup(panel_group)

                    for element in displays:
                        element.drawBorder()
                        element.defineWindow(element.panels, False)
                    
                    if len(displays) == 1:
                        # Base display [ [1**] [] [] ]
                        displays[0].reset(x - int(displays[0].w / 2), y - displays[0].h - display_y_spacing)
                        displays[0].draw()
                    elif len(displays) == 2:
                        # Base display [ [1**] [2**] [] ]
                        displays[0].reset(x - int(displays[0].w) - int(display_x_spacing / 2), y - displays[0].h - display_y_spacing)
                        displays[1].reset(x + int(display_x_spacing / 2), y - displays[1].h - display_y_spacing)

                        displays[0].draw()
                        displays[1].draw()
                    elif len(displays) == 3:
                        # Base display [ [1**] [2**] [3**] ]
                        displays[0].reset(x - int(displays[0].w) - (chest_props.wmp // 512) - displays[1].w + display_x_spacing, y - displays[0].h - display_y_spacing)
                        displays[1].reset(x - int(displays[1].w / 2), y - displays[1].h - display_y_spacing)
                        displays[2].reset(x + (chest_props.wmp // 512) + displays[1].w - display_x_spacing, y - displays[2].h - display_y_spacing)

                        displays[0].draw()
                        displays[1].draw()
                        displays[2].draw()

def writeToDebugFile(test_string):
    with open(DEBUG_LOGPATH, "a") as file:
        file.write(test_string)
        if DEBUG_MODE:
            logging.info("Finished writing to Debug file")


def reFieldToList(rf, itemtype=None):
    """
    struct RepeatedField_int -> list
    struct RepeatedPtrField works too if there is a single struct to cast on all elements
    """

    if rf.elements == ffi.NULL:
        return []
    lst = ffi.unpack(rf.elements, rf.current_size)
    if itemtype != None:
        for e in range(len(lst)):
            lst[e] = ffi.cast(itemtype, lst[e])
    return lst


def addPlainToLoggingDisplay(self, string):
    return {
        "item": {
            "text": string,
            "size": self.config.scd_text_display_size,
            "label_colour": 0xFFFFFF,
        },
        "boosts": [],
    }

def addItemToLoggingDisplay(self, loot_item, name, boost_length, boosts):
    boosts_list = []
    label_colour = 0xFFFFFF
    boost_colour = 0xFFFFFF

    # Item
    item_size = self.config.scd_text_display_size
    item_text = name
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

        item_color = label_colour

        # Boosts
        for boost in reFieldToList(boosts, "struct StatBoost *"):
            text = ""
            item_filtered_boost = ""

            if boost.stat == 43:
                if boost.val == 100:
                    filters = {
                        "name": "Armor Piercing",
                        "class": loot_item.get("class"),
                        "slot": loot_item.get("slot"),
                    }

                else:
                    filters = {
                        "name": "Barbed",
                        "class": loot_item.get("class"),
                        "slot": loot_item.get("slot"),
                    }

                item_filtered_boost = filter_boost(self.boost_list, boost.stat, filters)

                text += item_filtered_boost["name"]

            else:
                filters = {
                    "class": loot_item.get("class"),
                    "slot": loot_item.get("slot"),
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

            boost_display = {}
            boost_display["size"] = self.config.scd_text_display_size
            boost_display["text"] = text
            boost_display["colour"] = boost_colour

            boosts_list.append(boost_display)

    return {
        "item": {
            "text": item_text,
            "size": item_size,
            "label_colour": item_color,
        },
        "boosts": boosts_list,
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
