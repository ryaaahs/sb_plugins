sb_loot_logger.py  
Credits: Alexrns    

Plugin to log all non-player loot from within Starbreak subworlds.  
This works by iterating through all the game objects and logging the Loot objects as you progress throughout the   map.  

![Loot State Diagram](image.png)

Loot logging is done in two steps:  
Subworld Floors  
Subworld  

With a subworld floor, we track all loot that is dropped within the floor and only log it under these conditions  
Either:  
    You leave early (Homing, Entrance portal on Floor 0),  
    You move to the next floor  

With the subworld itself, once you leave the subworld you're in and return to the lobby/home, we take all the   Subworld Floors loot  
and condense them into a array that you can iterate and manipulate to your extent.  

Future Features:  
Slot filtering  
Item filtering  
Boost filtering  
