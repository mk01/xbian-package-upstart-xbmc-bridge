#!/usr/bin/env python

import socket
import json
import subprocess
import time


TCP_IP = '127.0.0.1'
TCP_PORT = 9090
BUFFER_SIZE = 256

logfilepath = '/run/upstart-xbmc-bridge.log'

class log :
    def __init__(self) :
        self.logfile = open(logfilepath,'w')
    
    def notice(self,msg) :
        self._log(msg,'NOTICE')
    
    def warning(self,msg) :
        self._log(msg,'WARNING')
    
    def error(self,msg) :
        self._log(msg,'ERROR')
    
    def _log(self,msg,level) :
        self.logfile.write('%s - %s : %s\n'%(time.strftime('%D - %H:%M',time.localtime()),str(level),str(msg)))
        print('%s - %s : %s\n'%(time.strftime('%D - %H:%M',time.localtime()),str(level),str(msg)))
    
    def __del__(self):
        self.logfile.close()
    
class xbmc_upstart_bridge :
    #bridge between xbmc and upstart
    #send upstart event :
    #Event :
    #   screensaver :
    #         send when xbmcscreensaver is activate/deactivate
    #         env variable : 
    #            ACTION = START/STOP
    #   player :
    #         send when player is start/stop/pause
    #         env variable :
    #            ACTION = PLAY/STOP/PAUSE
    #            TYPE = MOVIE/TVSHOW/AUDIO/NONE (to be check on xbmc api)
    #   library :
    #         send when action on library :
    #         env variable :
    #            ACTION = START/STOP/UPDATED
    #            MODE = UPDATE/CLEAN/NONE
    #            TYPE = AUDIO/VIDEO
    #
    #   it will also send special event xbmcplevel (xbmc priority level)
    #   it create profile for xbmc use and dynamic priority management in upstart script
    #   xbmcplevel :
    #          send when xbmc change his level
    #          env variable  :
    #             LEVEL = [012345]
    #                0 : xbmc is stopped    
    #                1 : xbmc very low priority (screensaver activated and player stop and library stop)
    #                2 : xbmc low priority (screensaver deactivated and (player start or library start))
    #                3 : xbmc normal priority (screensaver deactivated and player stop and library stop)
    #                4 : xbmc high priotity (screensaver deactivated and (player start or library start))
    #                5 : xbmc very high priotity (screensaver deactivated and player start and library start)
    #             PREVLEVEL = [012345] 
    #                Previous xbmc level
    
    
    def __init__(self) :
        #start logguer
        self.logguer = log()
        self.logguer.notice('upstart_xbmc_bridge started')
        
        #initialise event value
        #TODO : 
        #check in real time xbmc status with json api
        #suppose for now xbmc start and doing nothing on start and xbmc-upstart-bridge is run at the starting of xbmc
        self.screensaver = False
        self.player = False
        self.library = False
        
        self.cvlibrary = False #clean video library
        self.svlibrary = False #scan video library
        self.calibrary = False #clean audio library
        self.salibrary = False #scan audio library
        self.level = 3
        self.stopped = False
            
        #connect to TCP JSON XBMC API
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try :        
            self.s.connect((TCP_IP, TCP_PORT))
            self.logguer.notice('Connected to XBMC (%s:%d)'%(TCP_IP, TCP_PORT))        
        except Exception, e:
            self.logguer.error('Cannot connect to XBMC (%s:%d) : %s'%(TCP_IP, TCP_PORT,e))          
            self.stopped = True
                                        
    def emit_event(self,event,data=None) :
        cmd = ['initctl','emit',event]
        if data :
            print data
            try :
                for event in data :
					for key, value in event.items() :
						cmd.append('%s=%s'%(str(key),str(value)))
            except Exception, e:
                self.logguer.error('Cannot parse data %s : %s'%(str(data),e))
        try :
            subprocess.check_call(cmd)
            self.logguer.notice('Send event: %s\n'%str(cmd))
        except Exception, e:
            self.logguer.error('Cannot send event %s : %s'%(str(cmd),e))

    def main_loop(self) :
        while not self.stopped :
            data = json.loads(self.s.recv(BUFFER_SIZE))
            #try :
            if True :
                self.onEvent(data)  
            else :
            #except :
                self.logguer.error('Cannot parse event : %s '%str(data))            
                
    def onEvent(self,data) :
        change = True
        #screensaver event
        if data['method'] == 'GUI.OnScreensaverActivated' :
            self.logguer.notice('screen saver activated')
            self.screensaver = True
            self.emit_event('screensaver',[{'ACTION': 'START'}])                      
        elif data['method'] == 'GUI.OnScreensaverDeactivated' :
            self.logguer.notice('screen saver deactivated')
            self.screensaver = False
            self.emit_event('screensaver',[{'ACTION': 'STOP'}])
        #player event
        elif data['method'] == 'Player.OnPlay' :
            self.logguer.notice('player start')
            self.player = True
            self.emit_event('player',[{'ACTION': 'PLAY'},{'TYPE':str(data['params']['data']['item']['type'])}])
        elif data['method'] == 'Player.OnStop' :
            self.logguer.notice('player stop')
            self.player = False
            self.emit_event('player',[{'ACTION': 'STOP'},{'TYPE' :str(data['params']['data']['item']['type'])}])
        elif data['method'] == 'Player.OnPause' :
            self.logguer.notice('player pause')
            self.player = True
            self.emit_event('player',[{'ACTION': 'PAUSE'},{'TYPE':str(data['params']['data']['item']['type'])}])
        #library event
        #video library event        
        elif data['method'] == 'VideoLibrary.OnCleanStarted' :
            self.logguer.notice('video library clean started')
            self.cvlibrary = True
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'CLEAN'},{'TYPE' : 'VIDEO'}])
        elif data['method'] == 'VideoLibrary.OnCleanFinished' :
            self.logguer.notice('video library clean stopped')
            self.cvlibrary = False
            self.emit_event('library',[{'ACTION': 'STOP'},{'MODE' : 'CLEAN'},{'TYPE' : 'VIDEO'}])
        elif data['method'] == 'VideoLibrary.OnScanStarted' :
            self.logguer.notice('video library scan started')
            self.svlibrary = True
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'SCAN'},{'TYPE' : 'VIDEO'}])
        elif data['method'] == 'VideoLibrary.OnScanFinished' :
            self.logguer.notice('video library scan stopped')
            self.svlibrary = False
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'SCAN'},{'TYPE' : 'VIDEO'}])
        elif data['method'] == 'VideoLibrary.OnUpdate' :
            self.logguer.notice('video library updated')
            self.emit_event('library',[{'ACTION': 'UPDATED'},{'MODE' : 'NONE'},{'TYPE' : 'VIDEO'}])         
        #audio library event        
        elif data['method'] == 'AudioLibrary.OnCleanStarted' :
            self.logguer.notice('audio library clean started')
            self.calibrary = True
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'CLEAN'},{'TYPE' : 'AUDIO'}])
        elif data['method'] == 'AudioLibrary.OnCleanFinished' :
            self.logguer.notice('audio library scan stopeed')
            self.calibrary = False
            self.emit_event('library',[{'ACTION': 'STOP'},{'MODE' : 'CLEAN'},{'TYPE' : 'AUDIO'}])     
        elif data['method'] == 'AudioLibrary.OnScanStarted' :
            self.logguer.notice('audio library scan started')
            self.salibrary = True
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'SCAN'},{'TYPE' : 'AUDIO'}])
        elif data['method'] == 'AudioLibrary.OnScanFinished' :
            self.logguer.notice('audio library scan stopped')
            self.salibrary = False
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'SCAN'},{'TYPE' : 'AUDIO'}])
        elif data['method'] == 'AudioLibrary.OnUpdate' :
            self.logguer.notice('audio library updated')
            self.emit_event('library',[{'ACTION': 'UPDATED'},{'MODE' : 'NONE'},{'TYPE' : 'AUDIO'}])                             
        else :
            change = False  
        
        if change :
            self.library = self.salibrary or self.svlibrary or self.calibrary or self.cvlibrary
            #check for xbmc level
            #level 0 :
            #level 0 will be emitted with a special upstart script
            #level 1 :
            if self.screensaver and not self.player and not self.library and self.level != 1 :
                self.emit_event('xbmcplevel',[{'LEVEL':1},{'PREVLEVEL':self.level}])
                self.level = 1
            #level 2 :
            elif self.screensaver and (self.player != self.library) and self.level != 2 :  #!= stand for XOR
                self.emit_event('xbmcplevel',[{'LEVEL':2},{'PREVLEVEL':self.level}])
                self.level = 2
            #level 3 :
            elif not self.screensaver and not self.player and not self.library and self.level != 3 :
                self.emit_event('xbmcplevel',[{'LEVEL':3},{'PREVLEVEL':self.level}])
                self.level = 3
            #level 4 :
            elif not self.screensaver and (self.player != self.library) and self.level != 4 :   #!= stand for XOR
                self.emit_event('xbmcplevel',[{'LEVEL':4},{'PREVLEVEL':self.level}])
                self.level = 4
            #level 5 :
            elif not self.screensaver and self.player and self.library and self.level != 5 :
                self.emit_event('xbmcplevel',[{'LEVEL':5},{'PREVLEVEL':self.level}])
                self.level = 5


#############  MAIN ###############
main = xbmc_upstart_bridge()
main.main_loop()
