# SB Chest Display
Credits: Alexrns + Starbreak Community

# About
Plugin to display all chest loot within a XDL display.

## Features:  
Custom Max Item per Display  
Balance Item Display
Display/Item Label/Mod Label colour/opacity customization  
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
Get the files from the latest release

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