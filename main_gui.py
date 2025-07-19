#this is the gui of the bot version
import sys
import wx
from main import ApplicationController, setup_logging

if __name__ == "__main__":
    # Setup logging to a file for the GUI session as well.
    setup_logging() 
    
    # In GUI mode, we instantiate the controller and tell it to run in GUI mode.
    # The controller itself will now handle the wx.App lifecycle and the
    # initial configuration dialog if needed.
    controller = ApplicationController(nogui_mode=False)
    
    # The controller's start() method will now check for config,
    # show the config dialog if necessary, and then launch the main window
    # and the wx.App main loop.
    controller.start() 
    
    sys.exit(0)