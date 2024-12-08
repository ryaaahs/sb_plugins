# SB Chest Display
Credits: Alexrns + Starbreak Community

# About
Plugin to display all chest loot within a XDL display.

## Features:  
Custom Max Item per Display  
Balance Item Display
Label colour customization  
Remove Filtering  
Display Filtering  
Wildcard catching for both remove/display  
Disable on walkover  
Enable on walkover  

## How it works
The plugin iterates throughout all the items within the subworld.  
When we find a chest, we iterate through all the items and compare item id/modifier ids to the item/boost.json data.  
During this time we check to see if the item is within our filter list and move on or continue depending on which filter is selected.  
Once we get through all the filtering, we start with the display logic.  
Create the GraphicWindow to contain all the labels.  
Iterate through the collected items and create labels with the assoicated colours depending on mods.  
Once all the graphics are done, display it depending on the worlds x min and x max.  

# Usage
Get the files from here:  
https://github.com/ryaaahs/sb_plugins/releases/tag/sb_chest_display_release_1.0.1  

You would want the Source code (zip)  
The files you need from this zip folder are the following:  
`sb_chest_display.py`, Location: sb_chest_display  
`boosts.json`, Location: item_groups  
`items.json`, Location: item_groups  

Place `items.json/boost.json` in the root of your SBPE folder.
Place `sb_chest_display.py` in the plugin folder

`CONFIG.INI`
Place sb_chest_display last in manager priority
Add a display toggle under [plugin_keybinds], sb_chest_display scd_display_box toggle no yes = Right Alt
Add [plugin_sb_chest_display] above [plugin_keybinds]
```
[plugin_sb_chest_display]
scd_display_box = yes

scd_max_items_per_box = 15

scd_text_display_size = 15
scd_display_x_spacing = 25
scd_display_y_spacing = 15

scd_ec_uc_compress = no

# You can only have one filter on, default is remove if both are on
scd_remove_filter = no
scd_display_filter = no

# You can only have one walkover on, default is disable if both are on
scd_disable_on_walk_over = no
scd_enable_on_walk_over = no

scd_equal_chest_display = no

# Item Label Colours
scd_text_modified_label_colour = 79f071
scd_text_custom_label_colour = 3d70f0
scd_text_experimental_label_colour = d04ef0
scd_text_prototype_label_colour = f0b03d
scd_text_perf_item_label_colour = d22b2b

# Modifier Colours
scd_text_modified_modifier_colour = 79f071
scd_text_custom_modifier_colour = 638cf3
scd_text_experimental_modifier_colour = de83f4
scd_text_prototype_modifier_colour = f3bf63
scd_text_perf_item_modifier_colour = df6a6a 
```