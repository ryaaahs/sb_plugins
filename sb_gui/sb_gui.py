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

class Graphic:  # make subclass of PluginBase?
    def __init__(self, refs):
        self.refs = refs
        self.x = -1
        self.y = -1
        self.w = 0
        self.h = 0
        self.fill_rect = "0xff2b2b2b"
        self.fill_rect_blend = lib.BLENDMODE_BLEND
        self.draw_rect = "0xffa0a0a0"
        self.draw_rect_blend = lib.BLENDMODE_BLEND

    def draw(self):  # draws background
        cw = self.refs.canvasW_[0]
        ch = self.refs.canvasH_[0]
        self.refs.canvasW_[0] = self.refs.windowW
        self.refs.canvasH_[0] = self.refs.windowH

        self.refs.XDL_FillRect(self.x, self.y, self.w, self.h, int(self.fill_rect, 16), self.fill_rect_blend)
        self.refs.XDL_DrawRect(self.x, self.y, self.w, self.h, int(self.draw_rect, 16), self.draw_rect_blend)

        self.refs.canvasW_[0] = cw
        self.refs.canvasH_[0] = ch

class GraphicWindow(Graphic):
    def __init__(self, refs):
        super().__init__(refs)
        self.panel_spacing_w = 3
        self.panel_spacing_h = 5
        self.text_position = 0
        self.panels = []

    def addPanelGroup(self, panel_group): self.panels.append(panel_group)
    def addLabel(self, text=None, position=1): self.panels.append(GraphicPanelLabel(self.refs, self, self, text, position))
    def addPanelDivider(self, text=None): self.panels.append(GraphicPanelDivider(self.refs, self, self))

    # def reset(self, x, y):
    #     # Calculate window and panel values
    #     self.w = 0
    #     self.h = self.panel_spacing_h
        
    #     for panel in self.panels:
    #         panel.x = self.panel_spacing_w
    #         panel.y = self.h
    #         self.w = max(self.w, panel.w + 2 * self.panel_spacing_w)
    #         self.h += panel.h + 1
    #     self.h += self.panel_spacing_h

    #     self.x = min(x, self.refs.windowW - self.w)
    #     self.y = y if y + self.h < self.refs.windowH else max(y - self.h, 0)

    def defineWindow(self, panels):
        for panel in panels:
            if isinstance(panel, PanelGroup):
                self.defineWindow(panel.panels)
            else:
                self.w = max(self.w, panel.w + 2 * self.panel_spacing_w)
                self.h += panel.h 

    def renderNestedPanels(self, panels, x, y):
        for panel in panels:
            if isinstance(panel, PanelGroup):    
                # levels = 1
                # logging.info("a: " + str(self.text_position))
                self.text_position += panel.reset(x, self.text_position, self.w, 1)
                # logging.info("b: " + str(self.text_position))
                self.renderNestedPanels(panel.panels, x, y)
                #Render all the blocks with full content
            else:
                if not isinstance(panel.parent, PanelGroup):
                    panel.x = self.panel_spacing_w 
                    panel.y = self.text_position

                    self.text_position += panel.h

                    self.x = min(x, self.refs.windowW - self.w)

                    # logging.info(self.refs.windowH)

                    self.y = y if y + self.h < self.refs.windowH else max(y - self.h, 0)
                
    def reset(self, x, y):
        # Calculate window and panel values
        self.defineWindow(self.panels)
        self.renderNestedPanels(self.panels, x, y)

        self.h += self.panel_spacing_h

    def draw(self):
        # pass
        # logging.info(self.y)
        super().draw()
        for panel in self.panels:
            panel.draw()

class PanelGroup(Graphic): 
    def __init__(self, refs, window, tag=None):
        super().__init__(refs)
        self.tag = tag
        self.window = window
        self.parent = None
        logging.info(window.fill_rect)
        self.set_fill_rect = ""
        self.set_draw_rect = ""
        self.panel_spacing_w = 3
        self.panel_spacing_h = 5
        self.text_position = 0;
        self.levels = 0
        self.panels = []

    def addPanelGroup(self, panel_group): 
        self.panels.append(panel_group)
        panel_group.parent = self
    def addLabel(self, text=None, position=1): self.panels.append(GraphicPanelLabel(self.refs, self.window, self, text, position))
    def addPanelDivider(self, text=None): self.panels.append(GraphicPanelDivider(self.refs, self.window, self))

    def changeFillRectColour(self, hexcode): self.set_fill_rect = hexcode
    def changeDrawRectColour(self, hexcode): self.set_draw_rect = hexcode

    def defineWindow(self, panels):
        for panel in panels:
            if isinstance(panel, PanelGroup):
                self.defineWindow(panel.panels)
            else:
                # self.w = max(self.w, panel.w + 2 * self.panel_spacing_w)
                self.h += panel.h 

    def setDisplayColour(self):
        if (self.set_fill_rect == "" and self.parent != None):
            if (self.parent.set_fill_rect != ""):
                self.fill_rect = self.parent.set_fill_rect
        elif (self.set_fill_rect != ""):
            self.fill_rect = self.set_fill_rect

        if (self.set_draw_rect == "" and self.parent != None):
            if (self.parent.set_draw_rect != ""):
                self.draw_rect = self.parent.set_draw_rect
        elif (self.set_draw_rect != ""):
            self.draw_rect = self.set_draw_rect


    def renderNestedPanels(self, panels, x, y):
       
        for panel in panels:
            if isinstance(panel, PanelGroup):
                # logging.info("a" + self.tag + " " + str(self.levels))
                # logging.info("b" + self.tag + " " + str(self.levels))
                # logging.info("a: " + str(self.text_position))
                self.text_position += panel.reset(x, self.text_position, self.w, 1)
                # logging.info("b: " + str(self.text_position))
            else:
                
                # logging.info(self.levels)
                # logging.info("a" + self.tag + " " + str(self.levels))
                panel.x = self.panel_spacing_w + (self.levels * 5)
                panel.y = self.text_position 

                self.h += panel.h
                self.text_position += panel.h

    def reset(self, x, y, width, levels):
        # Calculate window and panel values
        # logging.info(self.tag)
        # logging.info(y)
        self.setDisplayColour()

        self.levels += levels

        self.h = 0
        self.text_position = y
        self.w = width
        
        self.renderNestedPanels(self.panels, x, y)

        self.x = min(x, self.refs.windowW - self.w)
        self.y = self.window.y + y if y + self.h < self.refs.windowH else max(y - self.h, 0)

        return self.h

    def draw(self):
        pass
        # self.reset(20, 20)
        # logging.info(self.y)
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
        self.refs.XDL_DrawLine(self.window.x + 11, self.window.y + self.y + 2, self.window.x + self.window.w - 11, self.window.y + self.y + 2, 0xff808080, lib.BLENDMODE_BLEND)
        self.refs.canvasW_[0] = cw
        self.refs.canvasH_[0] = ch

class GraphicPanelLabel(GraphicPanel):
    def __init__(self, refs, window, parent, text=None, position=1):
        super().__init__(refs, window)
        self.h = 22
        self.position = position
        self.parent = parent
        self.text_spacing_x = 10 * position
        self.label_spacing_x = 32
        self.text_spacing_y = 5
        self.text_obj = util.PlainText(size=13, outlineSize=0)  # Size should be 12 but real font size is set to 10
        self.text_ready = False
        if text != None: self.setText(text)

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
        # logging.info(self.y)
        # logging.info(self.window.x)
        if self.text_ready:
            self.text_obj.draw(self.window.x + self.x + self.text_spacing_x, self.window.y + self.y + self.text_spacing_y)

class Plugin(PluginBase):
    def onPresent(self):
        main_window = GraphicWindow(self.refs)
        main_window_two = GraphicWindow(self.refs)
        main_window_three = GraphicWindow(self.refs)

        main_window.addLabel("Test333333")
        main_window.addPanelDivider()

        panel_group_one = PanelGroup(self.refs, main_window, "pg1")
        panel_group_one.changeFillRectColour("0xffb27070")
        panel_group_one.changeDrawRectColour("0xffb27070")
        panel_group_one.addLabel("A")
        panel_group_one.addLabel("A")
        panel_group_one.addLabel("A")
        panel_group_one.addLabel("A")
        panel_group_one.addLabel("A")

        panel_group_two = PanelGroup(self.refs, main_window, "pg2")
        panel_group_two.changeFillRectColour("0xffbedbb1")
        panel_group_two.addLabel("B")
        panel_group_two.addLabel("B")
        panel_group_two.addLabel("B")
        panel_group_two.addLabel("B")
        panel_group_two.addLabel("B")
        panel_group_two.addPanelDivider()

        panel_group_three = PanelGroup(self.refs, main_window, "pg3")
        panel_group_three.changeFillRectColour("0xff7d7495")
        panel_group_three.addLabel("Test1222222222222222222222222222222222222222111111111111111111111", 1)

        # panel_group_three.fill_rect_blend = lib.BLENDMODE_MOD

        panel_group_four = PanelGroup(self.refs, main_window, "pg4")
        panel_group_four.changeFillRectColour("0xff21527f")
        panel_group_four.addLabel("C")
        panel_group_four.addPanelDivider()

        panel_group_five = PanelGroup(self.refs, main_window, "pg5")
        panel_group_five.changeFillRectColour("0xff7d7495")
        panel_group_five.addLabel("D")

        panel_group_six = PanelGroup(self.refs, main_window, "pg6")
        # panel_group_six.changeFillRectColour("0xff7d7495")
        panel_group_six.addLabel("E", 1)
        panel_group_six.addLabel("E", 1)
        panel_group_six.addLabel("E", 1)
        panel_group_six.addLabel("E", 1)
        panel_group_six.addLabel("E", 1)
        panel_group_six.addLabel("E", 1)


        panel_group_one.addPanelGroup(panel_group_six)
        panel_group_two.addPanelGroup(panel_group_three)
        panel_group_three.addPanelGroup(panel_group_four)
        panel_group_four.addPanelGroup(panel_group_five)
        
            
        main_window.addPanelGroup(panel_group_one)
        main_window.addPanelGroup(panel_group_two)
        

        main_window.addLabel("Test333333")
        main_window.addPanelDivider()

        main_window.addLabel("Test333333")
        main_window.addPanelDivider()
        
        # main_window.addLabel("Test1")
        # main_window.addLabel("Test2", 2)
        # main_window.addLabel("Test1", 2)
        # main_window.addLabel("Test2", 2)
        # main_window.addPanelDivider()
        # main_window.addLabel("Test1")
        # main_window.addLabel("Test2")
        main_window.reset(20, 20)

        main_window_two.addLabel("Test2")
        main_window_two.addPanelDivider()
        main_window_two.addLabel("Test2")
        main_window_two.addLabel("Test1")
        main_window_two.addLabel("Test2")
        main_window_two.addPanelDivider()
        main_window_two.reset(25 + main_window.w, 20)

        main_window_three.addLabel("Test3")
        main_window_three.reset(30 + main_window.w + main_window_two.w, 20)
      
        main_window.draw()
        main_window_two.draw()
        main_window_three.draw()