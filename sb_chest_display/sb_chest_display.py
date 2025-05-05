import logging
import os
import json
import util

from enum import Enum
from collections import Counter
from _remote import ffi, lib
from manager import PluginBase


DEBUG_MODE = False

BASEDIR = os.path.split(os.path.dirname(__file__))[0]

ITEMS_JSON = BASEDIR + "\\items.json"
BOOSTS_JSON = BASEDIR + "\\boosts.json"

ITEM_MODS = [
    "",
    "Modified",
    "Custom",
    "Experimental",
    "Prototype",
]

# Zones that we're ignoring
IGNORED_ZONE = [ 
    "home", 
    "lobby"
]

EC_LIST = [
    "1 EC",
    "5 EC",
    "10 EC",
    "25 EC"
]

UC_LIST = [
    "1 UC", 
    "5 UC"
]

# You can only have one filter type at a time (default filter if both are enabled is remove).
# If EC/UC compression is on, use the following names within the filter lists to display/remove it
# {"name": "EC"}
# {"name": "UC"}
# If compression is off, use the following filters:
# {"name": "1 EC"}
# {"name": "5 EC"}
# {"name": "10 EC"}
# {"name": "25 EC"}
# {"name": "1 UC"}
# {"name": "5 UC"}

# Filter options
# NOTE: Non modifiers items need to use the "catch all" filter format
# -------------------------------------------------------------
# *Catch all: {"name": "Jansky Repeater"} // All Jansky
# Case sensitive: {"name": "Jansky Repeater", "modifiers": []} // Jansky with no modifiers
# Case sensitive: {"name": "Jansky Repeater", "modifiers": ["Shots", "Precise"]} // Jansky with two modifiers

# Remove filter removes the items within the list you defined
# If enabled and the list is empty, the logic will not remove any items from the gui display
# Case sensitive with the information you pass into it 
# Review modifiers names in boost.json
remove_filter_list = [
    # Format
    # {"name": "Jansky Repeater"},
    # {"name": "Health Boost 1"},
    # {"name": "Jansky Repeater", "modifiers": []},
    # {"name": "Jansky Repeater", "modifiers": ["Shots", "Precise"]}
    # -------------------------------------------------------------------
]

# Display filter only displays the items within the list you defined
# If enabled and the list is empty, the gui will display nothing
# Case sensitive with the information you pass into it 
# Review modifiers names in boost.json
display_filter_list = [
    # Format
    # {"name": "Jansky Repeater"},
    # {"name": "Health Boost 1"},
    # {"name": "Jansky Repeater", "modifiers": []},
    # {"name": "Jansky Repeater", "modifiers": ["Shots", "Precise"]}
    # -------------------------------------------------------------------
]

# Perf tracking allows you to track specific items and give them a varient name (DPS/ COMB/ Range...)
# These items appear differently than others and can be customized within the config.ini
# When getting one of these items it will be displayed as X Name, where X is the varient name
# Name: Full name of the item (case sensitive)
# variant: varient name (DPS/ COMB/ Range...)
# tracking: enable or disable the tracking (True/False)
# modifiers: modifiers to track
# Review modifiers names in boost.json

# Create your own or use the ones within items_groups folder perf_items.txt

# NOTE: Please keep in mind that filters affect the display of perf tracking. Be mindful of that when creating your filters
perf_tracking = [
    # Format
    # {"name": "Jansky Repeater", "variant": "DPS", "tracking": True, "modifiers": ["Shots", "Armor Piercing", "Penetrating", "Explosive Ammo"]},
    # {"name": "Jansky Repeater", "variant": "COMB", "tracking": True, "modifiers": ["Shots", "Range", "Penetrating", "Explosive Ammo"]},
    {"name": "Kantikoy Repeater", "variant": "Range", "tracking": True, "modifiers": ["Shots", "Armor Piercing"]},
]

class Graphic:
    def __init__(self, refs):
        self.refs = refs
        self.x = -1
        self.y = -1
        self.w = 0
        self.h = 0
        self.fill_rect_colour = "2B2B2B"
        self.fill_rect_opacity = 255
        self.draw_rect_colour = "A0A0A0"
        self.draw_rect_opacity = 255
        self.draw_top_border = False
        self.draw_bottom_border = False
        self.draw_right_border = False
        self.draw_left_border = False
        self.display_fill_rect = True
        self.fill_rect_blend = lib.BLENDMODE_BLEND
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

    def setFillRectOpacity(self, opacity):
        self.fill_rect_opacity = opacity

    def setDrawRectOpacity(self, opacity):
        self.draw_rect_opacity = opacity
    
    def setFillRectColour(self, colour):
        self.fill_rect_colour = colour

    def setDrawRectColour(self, colour):
        self.draw_rect_colour = colour
    
    def displayFillRect(self, show):
        self.display_fill_rect = show

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
        
        if (self.display_fill_rect):
            self.refs.XDL_FillRect(
                self.x, self.y, self.w, self.h, 
                strcColourToHex(
                    self.fill_rect_colour, 
                    self.fill_rect_opacity
                ), 
                self.fill_rect_blend
            )

        x = self.x if self.draw_top_border == True else 0
        y = self.y if self.draw_bottom_border == True else 0
        w = self.w if self.draw_right_border == True else 0
        h = self.h if self.draw_left_border == True else 0

        if DEBUG_MODE:
            test = util.PlainText(font='HemiHeadBold')
            test.size = 15
            test.text = "x"
            test.draw(x, y, anchorX=0.5, anchorY=0.5)

        self.refs.XDL_DrawRect(x, y, w, h, 
            strcColourToHex(
                self.draw_rect_colour, 
                self.draw_rect_opacity
            ), 
            self.fill_rect_blend
        )

        self.refs.canvasW_[0] = cw
        self.refs.canvasH_[0] = ch


class GraphicWindow(Graphic):
    def __init__(self, refs):
        super().__init__(refs)
        self.panel_spacing_w = 3
        self.panel_spacing_h = 20
        self.text_position = 0
        self.base_window_y = 0
        self.base_window_x = 0
        self.panels = []
        self.panel_is_first_item = True

    def addPanelGroup(self, panel_group):
        self.panels.append(panel_group)

    def addLabel(self, text=None, position=1, colour="ffffff", opacity=1):
        self.panels.append(
            GraphicPanelLabel(self.refs, self, self, text, position, int(colour, 16), opacity)
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
                        self.x, self.text_position + 1, 1, self.base_window_y, self.base_window_x
                    )
                    self.panel_is_first_item = False
                else:
                    self.text_position += panel.reset(
                        self.x, self.text_position, 1, self.base_window_y, self.base_window_x
                    )
                self.renderNestedPanels(panel.panels)
            else:
                if not isinstance(panel.parent, PanelGroup):
                    panel.x = self.panel_spacing_w
                    panel.y = self.text_position

                    self.text_position += panel.h 

                    self.x = self.x
                    self.y = self.y
            self.panel_is_first_item = False
        
    def reset(self, x, y):
        self.text_position = 0
        self.x = x
        self.y = y
        self.base_window_y = y
        self.base_window_x = x
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
        self.set_fill_rect = ""
        self.set_draw_rect = ""
        self.set_fill_rect_opacity = 0
        self.set_draw_rect_opacity = 0
        self.panel_spacing_w = 3
        self.panel_spacing_h = 20
        self.text_position = 0
        self.base_window_y = 0
        self.base_window_x = 0
        self.levels = 0
        self.panels = []

    def addPanelGroup(self, panel_group):
        self.panels.append(panel_group)
        panel_group.parent = self

    def addLabel(self, text=None, position=1, colour="FFFFFF", opacity=1):
        self.panels.append(
            GraphicPanelLabel(self.refs, self.window, self, text, position, int(colour, 16), opacity)
        )

    def addPanelDivider(self, text=None):
        self.panels.append(GraphicPanelDivider(self.refs, self.window, self))

    def changeFillRectColour(self, hexcode_str, opacity):
        self.set_fill_rect = hexcode_str
        self.set_fill_rect_opacity = opacity

    def changeDrawRectColour(self, hexcode_str, opacity):
        self.set_draw_rect = hexcode_str
        self.set_draw_rect_opacity = opacity

    def defineWindow(self, panels):
        for panel in panels:
            if isinstance(panel, PanelGroup):
                self.defineWindow(panel.panels)
            else:
                self.w = self.window.w
                self.h += panel.h

    def setDisplayColour(self):
        if self.set_fill_rect == "" and self.window != None:
            if self.window.fill_rect_colour != "":
                self.setFillRectColour(self.window.fill_rect_colour)
                self.setFillRectOpacity(self.window.fill_rect_opacity)
        elif self.set_fill_rect != "":
            self.setFillRectColour(self.set_fill_rect)
            self.setFillRectOpacity(self.set_fill_rect_opacity)

        if self.set_draw_rect == "" and self.window != None:
            if self.window.draw_rect_colour != "":
                self.setDrawRectColour(self.window.draw_rect_colour)
                self.setDrawRectOpacity(self.window.draw_rect_opacity)
        elif self.set_draw_rect != "":
            self.setDrawRectColour(self.set_draw_rect)
            self.setDrawRectOpacity(self.set_draw_rect_opacity)

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

                self.x = self.x
                self.y = self.y

    def reset(self, x, y, levels, base_window_y, base_window_x):
        # Grab parent colours if we have none
        self.setDisplayColour()

        # Calculate window and panel values
        self.base_window_y = base_window_y
        self.levels += levels

        self.y = base_window_y + y
        self.x = base_window_x

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
    def __init__(self, refs, window, parent, text=None, position=1, colour=0xFFFFFF, opacity=1):
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
        self.text_obj.alpha = opacity
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

        self.config.options(
            "int",
            {
                "scd_text_display_size": 15,
                "scd_max_items_per_box": 20,
                "scd_display_x_spacing": 25, 
                "scd_display_y_spacing": 15,

                "scd_display_background_colour_opacity": 255,
                "scd_display_border_colour_opacity": 255,

                "scd_common_fill_background_colour_opacity": 255,
                "scd_modified_fill_background_colour_opacity": 255,
                "scd_custom_fill_background_colour_opacity": 255,
                "scd_experimental_fill_background_colour_opacity": 255,
                "scd_prototype_fill_background_colour_opacity": 255,
                "scd_perf_item_fill_background_colour_opacity": 255,
            },
        )

        self.config.options(
            "float",
            {
                "scd_text_common_label_colour_opacity": 1.0,
                "scd_text_modified_label_colour_opacity": 1.0,
                "scd_text_custom_label_colour_opacity": 1.0,
                "scd_text_experimental_label_colour_opacity": 1.0,
                "scd_text_prototype_label_colour_opacity": 1.0,
                "scd_text_perf_item_label_colour_opacity": 1.0,

                "scd_text_modified_modifier_colour_opacity": 1.0,
                "scd_text_custom_modifier_colour_opacity": 1.0,
                "scd_text_experimental_modifier_colour_opacity": 1.0,
                "scd_text_prototype_modifier_colour_opacity": 1.0,
                "scd_text_perf_item_modifier_colour_opacity": 1.0,
            },
        )

        self.config.options(
            "str",
            {
                "scd_common_fill_background_colour":  "ffffff",
                "scd_modified_fill_background_colour":  "79f071",
                "scd_custom_fill_background_colour":  "3d70f0",
                "scd_experimental_fill_background_colour":  "d04ef0",
                "scd_prototype_fill_background_colour":  "f0b03d",
                "scd_perf_item_fill_background_colour":  "d22b2b",

                "scd_text_common_label_colour": "FFFFFF",
                "scd_text_modified_label_colour": "1DB113",
                "scd_text_custom_label_colour": "3D70F0",
                "scd_text_experimental_label_colour": "D04EF0",
                "scd_text_prototype_label_colour": "F0B03D",
                "scd_text_perf_item_label_colour": "D22B2B", 
                
                "scd_text_modified_modifier_colour": "79F071",
                "scd_text_custom_modifier_colour": "638CF3",
                "scd_text_experimental_modifier_colour": "DE83F4",
                "scd_text_prototype_modifier_colour": "F6D291",
                "scd_text_perf_item_modifier_colour": "DF6A6A", 

                "scd_display_background_colour": "2B2B2B",
                "scd_display_border_colour": "A0A0A0", 
            },
        )
    
        self.config.options(
            "bool",
            {
                "scd_display_box": True,
                "scd_display_container_background": True,
                "scd_display_panel_group_background": False,
                "scd_ec_uc_compress": False,
                "scd_item_compress": False,
                "scd_remove_filter": False,
                "scd_display_filter": False,
                "scd_disable_on_walk_over": False,
                "scd_enable_on_walk_over": False,
                "scd_equal_chest_display": False,
            },
        )

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
        self.floor = ""
        
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
        
        cleint_world_props = client_world.asWorld.props

        zone = util.getstr(client_world.asWorld.props.zone) or util.getstr(
            client_world.asWorld.props.music
        )

        if zone not in IGNORED_ZONE:
            if not self.new_subworld:
                self.new_subworld = True
                self.is_home = False

            if (self.floor == "" or floor != cleint_world_props.floor):
                # Reset variable tracking on floor change
                self.display_dict = {}
                self.ec_dict = {}
                self.uc_dict = {}
                self.longest_name = ""
                self.longest_boost_name = ""
                self.longest_boost_name_dict = {}
                self.longest_name_dict = {}
                self.chest_length_dict = {}
                self.current_floor_chests_ids = []
                floor = cleint_world_props.floor
            
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
                            item_name = loot_item.get("name")
                            item_boosts_names = []
                            perf_item_match = False
                            perf_item_variant_name = ""

                            # Collect the boosts names to be used within filters
                            for boost in reFieldToList(item.statboosts, "struct StatBoost *"):
                                filters = {
                                    "class": loot_item.get("class"),
                                    "slot": loot_item.get("slot"),
                                }
                                item_filtered_boost = filterBoost(self.boost_list, boost.stat, filters)
                                item_boosts_names.append(item_filtered_boost["name"])

                            # Check for PERF items
                            for perf_item in perf_tracking:
                                if (
                                    item_name == perf_item["name"]
                                    and Counter(perf_item["modifiers"]) == Counter(item_boosts_names)
                                    and perf_item["tracking"]
                                ):
                                    # We have a match!
                                    perf_item_match = True
                                    perf_item_variant_name = perf_item["variant"]
                                        
                            if (self.config.scd_remove_filter):
                                wildcard_filter_list = []
                                for filter_item in remove_filter_list:
                                    if "modifiers" not in filter_item:
                                        wildcard_filter_list.append(filter_item['name'])

                                if (self.config.scd_ec_uc_compress):
                                    if "EC" in item_name:
                                        if "EC" in wildcard_filter_list: 
                                            continue
                                        total_ec_value += int(item_name.split(' ', 1)[0])
                                        continue 
                                    if "UC" in item_name:
                                        if "UC" in wildcard_filter_list: 
                                            continue
                                        total_uc_value += int(item_name.split(' ', 1)[0])
                                        continue

                                if (item_name in wildcard_filter_list):
                                    continue
                                elif (len(item_boosts_names) > 0): 
                                    matched_item = False

                                    for filter_item in remove_filter_list:
                                        if (item_name == filter_item["name"] and Counter(filter_item["modifiers"]) == Counter(item_boosts_names)):
                                                matched_item = True
                                                break
                                    
                                    if (matched_item):
                                        matched_item = False
                                        continue

                            elif (self.config.scd_display_filter):
                                wildcard_filter_list = []
                                for filter_item in display_filter_list:
                                    if "modifiers" not in filter_item:
                                        wildcard_filter_list.append(filter_item['name'])

                                if (self.config.scd_ec_uc_compress):
                                    if "EC" in item_name and "EC" in wildcard_filter_list: 
                                        total_ec_value += int(item_name.split(' ', 1)[0])
                                        continue
                                    elif "UC" in item_name and "UC" in wildcard_filter_list: 
                                        total_uc_value += int(item_name.split(' ', 1)[0])
                                        continue
                                    elif "EC" in item_name or "UC" in item_name:
                                        continue
                                
                                # Continue logic if item is in wc_filter list
                                if item_name not in wildcard_filter_list:
                                    # If the item is not within the list, check if the item matches boosts to display
                                    if (len(item_boosts_names) > 0):
                                        matched_item = False

                                        for filter_item in display_filter_list:                                            
                                            if (item_name == filter_item["name"] and Counter(filter_item["modifiers"]) == Counter(item_boosts_names)):
                                                matched_item = True
                                                break
                                        
                                        if (matched_item):
                                            matched_item = False
                                        else:
                                            continue
                                    else:
                                        continue

                            else: 
                                if (self.config.scd_ec_uc_compress):
                                    if "EC" in item_name:
                                        total_ec_value += int(item_name.split(' ', 1)[0])
                                        continue
                                    elif "UC" in item_name:
                                        total_uc_value += int(item_name.split(' ', 1)[0])
                                        continue

                            if DEBUG_MODE:
                                logging.info(self.item_list.get(item.type))
                                logging.info(item.type)

                            boosts = reFieldToList(
                                item.statboosts, "struct StatBoost *"
                            )

                            if perf_item_match: 
                                logging_name = perf_item_variant_name + " " + item_name
                            else: 
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
                                perf_item_match
                            )

                            # Determine if the item exists and we need to compress
                            # Given we are storing the contents within a readable format, we need to check after we transform the infomation
                            if (self.config.scd_item_compress):
                                item_exists = False

                                item_boosts = []
                                for boost in item_display_name["boosts"]:
                                    item_boosts.append(boost["text"])
                                    
                                for chest_items in self.display_dict[game_object.objId]:
                                    if (item_display_name["item"]["text"] == chest_items["item"]["text"]):
                                        
                                        chest_boosts = []
                                        for boost in chest_items["boosts"]:
                                            chest_boosts.append(boost["text"])

                                        # If they have empty arrays, increment the counter instead of adding it to display
                                        if (len(item_boosts) == 0 and len(chest_boosts) == 0):
                                            chest_items["item"]["amount"] += 1
                                            item_exists = True
                                            break
                                        elif (Counter(item_boosts) == Counter(chest_boosts)):
                                            # Compare the boosts between the items
                                            chest_items["item"]["amount"] += 1
                                            item_exists = True
                                            break

                                if (not item_exists):
                                    chest_length += len(boosts) + 1 if len(boosts) > 0 else 1
                                    self.display_dict[game_object.objId].append(item_display_name)
                            else:
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

                # Reset variable tracking on home
                self.display_dict = {}
                self.ec_dict = {}
                self.uc_dict = {}
                self.longest_name = ""
                self.longest_boost_name = ""
                self.longest_boost_name_dict = {}
                self.longest_name_dict = {}
                self.chest_length_dict = {}
                self.current_floor_chests_ids = []
                self.floor = ""

        self.draw = True

    def onPresent(self):
        # Draw checks and objects checks
        if not self.draw or not self.config.scd_display_box:
            return

        client_world = self.refs.ClientWorld
        world_view = self.refs.WorldView

        if client_world == ffi.NULL or world_view == ffi.NULL or client_world.player == ffi.NULL:
            return

        canvas_width = self.refs.canvasW_[0]
        canvas_height = self.refs.canvasH_[0]

        # Item Display box
        for game_object in util.worldobjects(client_world.mySubWorld.asNativeSubWorld):
            if util.getClassName(game_object) == "Chest":

                chest = ffi.cast("struct Chest *", game_object)
                chest_props = game_object.props

                chest_x = (
                    chest_props.xmp // 256
                    + chest_props.wmp // 512
                    - world_view.offset.x
                )
                chest_y = chest_props.ymp // 256 - world_view.offset.y

                # Correct Window space coords when changing the zoom level
                chest_x = round(chest_x / self.refs.scaleX)
                chest_y = round(chest_y / self.refs.scaleY)

                player = ffi.cast('struct WorldObject *', client_world.player)
                player_x = player.props.xmp // 256 + player.props.wmp // 512 - world_view.offset.x
                player_y = player.props.ymp // 256 - world_view.offset.y

                # Correct Window space coords when changing the zoom level
                player_x = round(player_x / self.refs.scaleX)
                player_y = round(player_y / self.refs.scaleY)

                if DEBUG_MODE:
                    # Place a visual marker onto the player and chest
                    player_marker = util.PlainText(font='HemiHeadBold')
                    player_marker.size = 20
                    player_marker.text = "p"
                    player_marker.draw(player_x, player_y, anchorX=0.5, anchorY=0.5)

                    chest_marker = util.PlainText(font='HemiHeadBold')
                    chest_marker.size = 20
                    chest_marker.text = "c"
                    chest_marker.draw(chest_x, chest_y, anchorX=0.5, anchorY=0.5)

                # Remove display if the user opens the chest
                if chest.pos == -1:
                    displays = []
                    # Base display [ [1**] [] [] ]
                    displays.append(GraphicWindow(self.refs))
                    display_index = 0
                    #  Update draw configuration before passing it to children
                    displays[display_index].setFillRectColour(self.config.scd_display_background_colour)
                    displays[display_index].setDrawRectColour(self.config.scd_display_border_colour)
                    displays[display_index].setFillRectOpacity(self.config.scd_display_background_colour_opacity)
                    displays[display_index].setDrawRectOpacity(self.config.scd_display_border_colour_opacity)
                    
                    panel_group_number = 0
                    text_element_index = 0
                    total_displays = 0
                    chest_length = self.chest_length_dict[game_object.objId]

                    if (chest_length <= self.config.scd_max_items_per_box):
                        total_displays = 1
                    elif (chest_length <= (self.config.scd_max_items_per_box * 2)):
                        total_displays = 2
                    else:
                        total_displays = 3

                    max_item_display = self.config.scd_max_items_per_box 

                    if (self.config.scd_equal_chest_display and total_displays > 1):
                        max_item_display = int(chest_length / total_displays)
                    
                    # Catch race condition issue with the chest id not appearing within the display_dict
                    if game_object.objId in self.display_dict:
                        for index, element in enumerate(self.display_dict[game_object.objId]):
                            if (text_element_index >= max_item_display and display_index != total_displays - 1):
                                displays.append(GraphicWindow(self.refs))
                                display_index += 1
                                displays[display_index].setFillRectColour(self.config.scd_display_background_colour)
                                displays[display_index].setDrawRectColour(self.config.scd_display_border_colour)
                                displays[display_index].setFillRectOpacity(self.config.scd_display_background_colour_opacity)
                                displays[display_index].setDrawRectOpacity(self.config.scd_display_border_colour_opacity)

                                text_element_index = 0

                            if len(element["boosts"]) == 0:
                                text_element_index += 1

                                if (element["item"]["amount"] == 1):
                                    displays[display_index].addLabel(
                                        element["item"]["text"], 
                                        1, 
                                        self.config.scd_text_common_label_colour, 
                                        self.config.scd_text_common_label_colour_opacity
                                    )
                                else:
                                    displays[display_index].addLabel(
                                        str(element["item"]["amount"]) + " " + element["item"]["text"],
                                        1, 
                                        self.config.scd_text_common_label_colour, 
                                        self.config.scd_text_common_label_colour_opacity
                                    )
                                
                                # First check to see if we are not on the max display
                                # Second, check to see if we are at the end of the display dict list
                                if (display_index == total_displays - 1 and index != len(self.display_dict[game_object.objId]) - 1):
                                    displays[display_index].addPanelDivider() 
                                elif text_element_index < max_item_display and index != len(self.display_dict[game_object.objId]) - 1: 
                                    displays[display_index].addPanelDivider() 
                                
                            else:
                                panel_group_number += 1
                                panel_group = PanelGroup(
                                    self.refs, displays[display_index], "pg" + str(panel_group_number)
                                )
                                panel_group.displayFillRect(self.config.scd_display_panel_group_background)
                                panel_group.changeFillRectColour(element["item"]["fill_background"], element["item"]["fill_background_opacity"])
                                
                                text_element_index += 1
                                if (element["item"]["amount"] == 1):
                                    panel_group.addLabel(
                                        element["item"]["text"],
                                        0,
                                        element["item"]["label_colour"],
                                        element["item"]["label_opacity"],
                                    )
                                else:
                                    panel_group.addLabel(
                                        str(element["item"]["amount"]) + " " + element["item"]["text"],
                                        0,
                                        element["item"]["label_colour"],
                                        element["item"]["label_opacity"],
                                    )
                                
                                for boost_elements in element["boosts"]:
                                    text_element_index += 1 
                                    panel_group.addLabel(
                                        boost_elements["text"], 1, boost_elements["colour"], boost_elements["opacity"]
                                )   

                                # First check to see if we are not on the max display
                                # Second, check to see if we overflow on max display
                                if (display_index == total_displays - 1 and index != len(self.display_dict[game_object.objId]) - 1):
                                    panel_group.addPanelDivider()
                                elif text_element_index < max_item_display and index != len(self.display_dict[game_object.objId]) - 1: 
                                    panel_group.addPanelDivider()

                                displays[display_index].addPanelGroup(panel_group)

                    for element in displays:
                        element.drawBorder()
                        element.displayFillRect(self.config.scd_display_container_background)
                        element.defineWindow(element.panels, False)
                    
                    if len(displays) == 1:
                        # Base display [ [1**] [] [] ]
                        display_one_x = chest_x - int(displays[0].w / 2)
                        display_one_y = chest_y - displays[0].h - self.config.scd_display_y_spacing
                        
                        touch_box_y1 = display_one_y
                        touch_box_y2 = chest_y - self.config.scd_display_y_spacing
                        touch_box_x1 = display_one_x
                        touch_box_x2 = display_one_x + displays[0].w
                        
                        displays[0].reset(display_one_x, display_one_y)

                        if DEBUG_MODE:
                            x1y1 = util.PlainText(font='HemiHeadBold')
                            x1y1.size = 20
                            x1y1.text = "x1y1"
                            x1y1.draw(touch_box_x1, touch_box_y1, anchorX=0.5, anchorY=0.5)

                            x2y1 = util.PlainText(font='HemiHeadBold')
                            x2y1.size = 20
                            x2y1.text = "x2y1"
                            x2y1.draw(touch_box_x2, touch_box_y1, anchorX=0.5, anchorY=0.5)

                            x1y2 = util.PlainText(font='HemiHeadBold')
                            x1y2.size = 20
                            x1y2.text = "x1y2"
                            x1y2.draw(touch_box_x1, touch_box_y2, anchorX=0.5, anchorY=0.5)
 
                            x2y2 = util.PlainText(font='HemiHeadBold')
                            x2y2.size = 20
                            x2y2.text = "x2y2"
                            x2y2.draw(touch_box_x2, touch_box_y2, anchorX=0.5, anchorY=0.5)

                        if (self.config.scd_disable_on_walk_over):
                            if (not ((player_y >= touch_box_y1) and (player_y <= touch_box_y2))
                                or not ((player_x >= touch_box_x1) and (player_x <= touch_box_x2))):
                                    displays[0].draw()   
                        elif(self.config.scd_enable_on_walk_over):
                            if (((player_y >= touch_box_y1) and (player_y <= touch_box_y2))
                                and ((player_x >= touch_box_x1) and (player_x <= touch_box_x2))):
                                    displays[0].draw()
                        else:
                            displays[0].draw()

                    elif len(displays) == 2:
                        # Base display [ [1**] [2**] [] ]
                        
                        # Get tallest display and use that as a baseline
                        max_height = max([displays[0].h, displays[1].h])
                        
                        display_one_x = chest_x - int(displays[0].w) - int(self.config.scd_display_x_spacing / 2)
                        display_two_x = chest_x + int(self.config.scd_display_x_spacing / 2)
                        
                        touch_box_y1 = chest_y - max_height - self.config.scd_display_y_spacing
                        touch_box_y2 = chest_y - self.config.scd_display_y_spacing
                        touch_box_x1 = display_one_x
                        touch_box_x2 = display_two_x + displays[1].w
                        
                        if display_one_x < 0:
                            display_one_x = chest_x - int(displays[0].w / 2)
                            display_two_x = chest_x + int(displays[0].w / 2) + self.config.scd_display_x_spacing

                            touch_box_x1 = display_one_x
                            touch_box_x2 = display_two_x + displays[1].w
                        elif display_two_x + displays[1].w > self.refs.windowW:
                            display_one_x = chest_x - int(displays[0].w / 2)
                            display_two_x = chest_x - int(displays[0].w / 2) - displays[1].w - self.config.scd_display_x_spacing
                            
                            touch_box_x1 = display_two_x
                            touch_box_x2 = display_one_x + displays[0].w


                        displays[0].reset(display_one_x, chest_y - displays[0].h - self.config.scd_display_y_spacing)
                        displays[1].reset(display_two_x, chest_y - displays[1].h - self.config.scd_display_y_spacing)

                        if DEBUG_MODE:
                            x1y1 = util.PlainText(font='HemiHeadBold')
                            x1y1.size = 20
                            x1y1.text = "x1y1"
                            x1y1.draw(touch_box_x1, touch_box_y1, anchorX=0.5, anchorY=0.5)

                            x2y1 = util.PlainText(font='HemiHeadBold')
                            x2y1.size = 20
                            x2y1.text = "x2y1"
                            x2y1.draw(touch_box_x2, touch_box_y1, anchorX=0.5, anchorY=0.5)

                            x1y2 = util.PlainText(font='HemiHeadBold')
                            x1y2.size = 20
                            x1y2.text = "x1y2"
                            x1y2.draw(touch_box_x1, touch_box_y2, anchorX=0.5, anchorY=0.5)
 
                            x2y2 = util.PlainText(font='HemiHeadBold')
                            x2y2.size = 20
                            x2y2.text = "x2y2"
                            x2y2.draw(touch_box_x2, touch_box_y2, anchorX=0.5, anchorY=0.5)
                        
                        if (self.config.scd_disable_on_walk_over):
                            if (not ((player_y >= touch_box_y1) and (player_y <= touch_box_y2))
                                or not ((player_x >= touch_box_x1) and (player_x <= touch_box_x2))):
                                    displays[0].draw()
                                    displays[1].draw()  
                        elif(self.config.scd_enable_on_walk_over):
                            if (((player_y >= touch_box_y1) and (player_y <= touch_box_y2))
                                and ((player_x >= touch_box_x1) and (player_x <= touch_box_x2))):
                                    displays[0].draw()
                                    displays[1].draw() 
                        else:
                            displays[0].draw()
                            displays[1].draw()

                        
                    elif len(displays) == 3:
                        # Base display [ [1**] [2**] [3**] ]

                        # Get tallest display and use that as a baseline
                        max_height = max([displays[0].h, displays[1].h, displays[2].h])

                        display_one_x = chest_x - int(displays[0].w / 2)
                        display_two_x = chest_x - int(displays[0].w / 2) - displays[1].w - self.config.scd_display_x_spacing
                        display_three_x = chest_x + int(displays[0].w / 2) + self.config.scd_display_x_spacing

                        touch_box_y1 = chest_y - max_height - self.config.scd_display_y_spacing
                        touch_box_y2 = chest_y - self.config.scd_display_y_spacing
                        touch_box_x1 = display_two_x
                        touch_box_x2 = display_three_x + displays[2].w

                        if display_two_x < 0:
                            display_one_x = chest_x - int(displays[0].w / 2)
                            display_two_x = chest_x + int(displays[0].w / 2) + self.config.scd_display_x_spacing
                            display_three_x = chest_x + int(displays[0].w / 2) + displays[1].w + (self.config.scd_display_x_spacing * 2)

                            # Check again if display needs to be corrected with scale 
                            if display_one_x < 0:
                                # Correct display to use scale correction   
                                display_one_x = chest_x - int(displays[0].w / 2)

                                x_difference = display_one_x * -1
                                
                                display_one_x += int(x_difference * self.refs.scaleX)
                                display_two_x += int(x_difference * self.refs.scaleX)
                                display_three_x += int(x_difference * self.refs.scaleX)

                            touch_box_x1 = display_one_x
                            touch_box_x2 = display_three_x + displays[2].w
                        elif display_three_x + displays[2].w > self.refs.windowW:
                            display_one_x = chest_x - int(displays[0].w / 2)
                            display_two_x = chest_x - int(displays[0].w / 2) - displays[1].w - self.config.scd_display_x_spacing
                            display_three_x = chest_x - int(displays[0].w / 2) - displays[1].w - displays[2].w - (self.config.scd_display_x_spacing * 2)

                            touch_box_x1 = display_three_x
                            touch_box_x2 = display_one_x + displays[0].w

                        displays[0].reset(display_one_x, chest_y - displays[0].h - self.config.scd_display_y_spacing)
                        displays[1].reset(display_two_x, chest_y - displays[1].h - self.config.scd_display_y_spacing)
                        displays[2].reset(display_three_x, chest_y - displays[2].h - self.config.scd_display_y_spacing)

                        if DEBUG_MODE:
                            x1y1 = util.PlainText(font='HemiHeadBold')
                            x1y1.size = 20
                            x1y1.text = "x1y1"
                            x1y1.draw(touch_box_x1, touch_box_y1, anchorX=0.5, anchorY=0.5)

                            x2y1 = util.PlainText(font='HemiHeadBold')
                            x2y1.size = 20
                            x2y1.text = "x2y1"
                            x2y1.draw(touch_box_x2, touch_box_y1, anchorX=0.5, anchorY=0.5)

                            x1y2 = util.PlainText(font='HemiHeadBold')
                            x1y2.size = 20
                            x1y2.text = "x1y2"
                            x1y2.draw(touch_box_x1, touch_box_y2, anchorX=0.5, anchorY=0.5)
 
                            x2y2 = util.PlainText(font='HemiHeadBold')
                            x2y2.size = 20
                            x2y2.text = "x2y2"
                            x2y2.draw(touch_box_x2, touch_box_y2, anchorX=0.5, anchorY=0.5)

                        if (self.config.scd_disable_on_walk_over):
                            if (not ((player_y >= touch_box_y1) and (player_y <= touch_box_y2))
                                or not ((player_x >= touch_box_x1) and (player_x <= touch_box_x2))):
                                    displays[0].draw()
                                    displays[1].draw()
                                    displays[2].draw() 
                        elif(self.config.scd_enable_on_walk_over):
                            if (((player_y >= touch_box_y1) and (player_y <= touch_box_y2))
                                and ((player_x >= touch_box_x1) and (player_x <= touch_box_x2))):
                                    displays[0].draw()
                                    displays[1].draw()
                                    displays[2].draw() 
                        else:
                            displays[0].draw()
                            displays[1].draw()
                            displays[2].draw()

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
            "amount": 1,
            "size": self.config.scd_text_display_size,
            "label_colour": "ffffff",
            "label_opacity": 255,
        },
        "boosts": [],
    }

def addItemToLoggingDisplay(self, loot_item, name, boost_length, boosts, perf_item):
    boosts_list = []
    label_colour = "ffffff"
    label_opacity = 255
    boost_colour = "ffffff"
    boost_opacity = 255
    fill_background = "ffffff"
    fill_background_opacity = 255

    # Item
    item_size = self.config.scd_text_display_size
    item_text = name

    if perf_item:
        label_colour = self.config.scd_text_perf_item_label_colour
        label_opacity = self.config.scd_text_perf_item_label_colour_opacity
        boost_colour = self.config.scd_text_perf_item_modifier_colour
        boost_opacity = self.config.scd_text_perf_item_modifier_colour_opacity
        fill_background = self.config.scd_perf_item_fill_background_colour
        fill_background_opacity = self.config.scd_perf_item_fill_background_colour_opacity

    if boost_length != -1:
        if not perf_item:
            if boost_length == 1:
                label_colour = self.config.scd_text_modified_label_colour
                label_opacity = self.config.scd_text_modified_label_colour_opacity
                boost_colour = self.config.scd_text_modified_modifier_colour
                boost_opacity = self.config.scd_text_modified_modifier_colour_opacity
                fill_background = self.config.scd_modified_fill_background_colour
                fill_background_opacity = self.config.scd_modified_fill_background_colour_opacity

            elif boost_length == 2:
                label_colour = self.config.scd_text_custom_label_colour
                label_opacity = self.config.scd_text_custom_label_colour_opacity
                boost_colour = self.config.scd_text_custom_modifier_colour
                boost_opacity = self.config.scd_text_custom_modifier_colour_opacity
                fill_background = self.config.scd_custom_fill_background_colour
                fill_background_opacity = self.config.scd_custom_fill_background_colour_opacity

            elif boost_length == 3:
                label_colour = self.config.scd_text_experimental_label_colour
                label_opacity = self.config.scd_text_experimental_label_colour_opacity
                boost_colour = self.config.scd_text_experimental_modifier_colour
                boost_opacity = self.config.scd_text_experimental_modifier_colour_opacity
                fill_background = self.config.scd_experimental_fill_background_colour
                fill_background_opacity = self.config.scd_experimental_fill_background_colour_opacity

            elif boost_length == 4:
                label_colour = self.config.scd_text_prototype_label_colour
                label_opacity = self.config.scd_text_prototype_label_colour_opacity
                boost_colour = self.config.scd_text_prototype_modifier_colour
                boost_opacity = self.config.scd_text_prototype_modifier_colour_opacity
                fill_background = self.config.scd_prototype_fill_background_colour
                fill_background_opacity = self.config.scd_prototype_fill_background_colour_opacity

        # Boosts
        for boost in reFieldToList(boosts, "struct StatBoost *"):
            text = ""
            item_filtered_boost = ""

            # TODO Figure out why I needed to define the raw boost values without a comment
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

                item_filtered_boost = filterBoost(self.boost_list, boost.stat, filters)
                text += item_filtered_boost["name"]

            elif ((loot_item.get("class") == "Ironclad" and loot_item.get("slot") == "Main") and boost.stat == 36):
                if boost.val == 1:
                    filters = {
                        "name": "Height",
                        "class": loot_item.get("class"),
                        "slot": loot_item.get("slot"),
                    }
                elif boost.val == 2:
                    filters = {
                        "name": "Plinks",
                        "class": loot_item.get("class"),
                        "slot": loot_item.get("slot"),
                    }

                    item_filtered_boost = filterBoost(self.boost_list, boost.stat, filters)
                    text += item_filtered_boost["name"]
            else:
                filters = {
                    "class": loot_item.get("class"),
                    "slot": loot_item.get("slot"),
                }

                item_filtered_boost = filterBoost(self.boost_list, boost.stat, filters)
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

            elif item_filtered_boost["display_type"] == 5:
                text += ": +" + str(boost.val) + "HP"

            elif item_filtered_boost["display_type"] == 6:
                text += ": -" + str(boost.val) + "%"

            boost_display = {}
            boost_display["size"] = self.config.scd_text_display_size
            boost_display["text"] = text
            boost_display["colour"] = boost_colour
            boost_display["opacity"] = boost_opacity

            boosts_list.append(boost_display)

    return {
        "item": {
            "text": item_text,
            "size": item_size,
            "amount": 1,
            "label_colour": label_colour,
            "label_opacity": label_opacity,
            "fill_background": fill_background,
            "fill_background_opacity": fill_background_opacity,
        },
        "boosts": boosts_list,
    }


def strcColourToHex(colour, opacity):
    # Check opacity bounds
    if (opacity < 0 or opacity > 255): 
        opacity = 255

    return int(hex(opacity) + colour, 16)


def filterBoost(boost_list, boost_id, filters):
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
        
    logging.info("No boost match. Report below information to Plugin Developer")
    logging.info("Boost ID: " + str(boost_id))
    logging.info("Filters: " + str(filters))

    return {
        'id': -1, 
        'name': 'NULL', 
        'display_type': 0, 
        'divide_value': 0, 
        'class': ['NULL'],
        'slot': ['NULL']
    }
