# SB GUI
Credits: Alexrns

# About
Collection of GUI classes that support drawing nested data to the screen using XDL functions

`Graphic`   
    >> `GraphicWindow`    
    >> `PanelGroup`  
    >> `GraphicPanel`   
    >> >> `GraphicPanelDivider`  
    >> >> `GraphicPanelLabel`  

`Graphic`: Base class for the GUI, contains the main render logic to draw the display (fill/draw rect)  
`GraphicWindow`: Logic container to position the Graphic box and readjust size to childern elements. Can contain PanelGroups or direct items like Divider or Label  
`PanelGroup`: Logic Container for GraphicPanel items, similar to GraphicWindow.  
`GraphicPanel`: Base class for Panel items, pulls in refs data from GraphicWindow.  
`GraphicPanelDivider`: Displays an <hr> line within the display.
`GraphicPanelLabel`:  Displays text within the display.

# Usage
Bring the SB GUI classes into the plugin to use.