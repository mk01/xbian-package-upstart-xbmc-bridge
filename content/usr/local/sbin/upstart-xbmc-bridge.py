#!/usr/bin/env python

import socket
import time
import struct
import json
import subprocess
import time
import logging
import os
import signal

TCP_IP = '127.0.0.1'
TCP_PORT = 9090
BUFFER_SIZE = 1024

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
    #                2 : xbmc low priority (screensaver activated and (player start or library start))
    #                3 : xbmc normal priority (screensaver deactivated and player stop and library stop)
    #                4 : xbmc high priotity (screensaver deactivated and (player start or library start))
    #                5 : xbmc very high priotity (screensaver deactivated and player start and library start)
    #             PREVLEVEL = [012345] 
    #                Previous xbmc level
    
    
    def onExit(self):
        logging.info('Closing')
        self.s.close()

    def handleSigTERM(self, signum, a):
        logging.info('sigterm')
        self.stopped = True

    def __init__(self) :
        #start logguer
        logging.basicConfig(filename='/var/log/upstart-xbmc-bridge.log',level=logging.INFO,format='%(asctime)s %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
        logging.info('upstart_xbmc_bridge started')
        
        #initialise event value
        #TODO : 
        #check in real time xbmc status with json api
        #suppose for now xbmc start and doing nothing on start and xbmc-upstart-bridge is run at the starting of xbmc
        self.screensaver = False
        self.player = False
        self.library = False

        self.pvr = False
        
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
            l_onoff = 1
            l_linger = 0
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', l_onoff, l_linger))
            logging.info('Connected to XBMC (%s:%d)'%(TCP_IP, TCP_PORT))        
        except Exception, e:
            logging.error('Cannot connect to XBMC (%s:%d) : %s'%(TCP_IP, TCP_PORT,e))          
            time.sleep(30)
            self.stopped = True
                                        
    def emit_event(self,event,data=None) :
        cmd = ['initctl','emit','-n',event]
        if data :
            print data
            try :
                for event in data :
					for key, value in event.items() :
						cmd.append('%s=%s'%(str(key),str(value)))
            except Exception, e:
                logging.error('Cannot parse data %s : %s'%(str(data),e))
        try :
            subprocess.check_call(cmd)
            logging.info('Send event: %s\n'%str(cmd))
        except Exception, e:
            logging.error('Cannot send event %s : %s'%(str(cmd),e))

    def main_loop(self) :
        while not self.stopped :
            try:
                strReceived = self.s.recv(BUFFER_SIZE)
            except IOError:
                if not self.stopped:
                    logging.error('Cannot read from socket')
                    self.stopped = True
            else:
                try:
                    data = json.loads(strReceived)
                except:
                    if not self.stopped:
                        logging.error('Cannot parse event : %s '%str(strReceived))
                        if str(strReceived) == '':
                            self.stopped = True
                        else:
                            time.sleep(5)
                else:
                    self.onEvent(data)

    def onEvent(self,data) :
        change = True
        #screensaver event
        logging.info(data['method'])
        if data['method'] == 'System.OnQuit' :
            logging.info('Quit requested: %s '%str(data['params']['data']))
            f = open('/run/lock/xbmc.quit', 'w')
            f.write(str(data['params']['data']))
            os.system('pid=$(initctl status xbmc | cut -d " " -f 4); sleep 15 && kill $pid || kill -9 $pid;')
            self.stopped = True
            return 0

        try:
            str(data['params']['data']['item']['type'])
        except:
            pass
        else:
            if str(data['params']['data']['item']['type']) == 'channel' and  data['method'] == 'Player.OnPlay':
                self.pvr = True

        if data['method'] == 'GUI.OnScreensaverActivated' :
            logging.info('screen saver activated')
            self.screensaver = True
            self.emit_event('screensaver',[{'ACTION': 'START'}])
        elif data['method'] == 'GUI.OnScreensaverDeactivated' :
            logging.info('screen saver deactivated')
            self.screensaver = False
            self.emit_event('screensaver',[{'ACTION': 'STOP'}])
        #player event
        elif data['method'] == 'Player.OnPlay' :
            logging.info('player start')
            self.player = True
            self.emit_event('player',[{'ACTION': 'PLAY'},{'TYPE':str(data['params']['data']['item']['type'])}])
        elif data['method'] == 'Player.OnStop' :
            logging.info('player stop')
            self.player = False
            self.emit_event('player',[{'ACTION': 'STOP'},{'TYPE' :str(data['params']['data']['item']['type'])}])
        elif data['method'] == 'Player.OnPause' :
            logging.info('player pause')
            self.player = True
            self.emit_event('player',[{'ACTION': 'PAUSE'},{'TYPE':str(data['params']['data']['item']['type'])}])
        #library event
        #video library event        
        elif data['method'] == 'VideoLibrary.OnCleanStarted' :
            logging.info('video library clean started')
            self.cvlibrary = True
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'CLEAN'},{'TYPE' : 'VIDEO'}])
        elif data['method'] == 'VideoLibrary.OnCleanFinished' :
            logging.info('video library clean stopped')
            self.cvlibrary = False
            self.emit_event('library',[{'ACTION': 'STOP'},{'MODE' : 'CLEAN'},{'TYPE' : 'VIDEO'}])
        elif data['method'] == 'VideoLibrary.OnScanStarted' :
            logging.info('video library scan started')
            self.svlibrary = True
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'SCAN'},{'TYPE' : 'VIDEO'}])
        elif data['method'] == 'VideoLibrary.OnScanFinished' :
            logging.info('video library scan stopped')
            self.svlibrary = False
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'SCAN'},{'TYPE' : 'VIDEO'}])
        elif data['method'] == 'VideoLibrary.OnUpdate' :
            logging.info('video library updated')
            self.emit_event('library',[{'ACTION': 'UPDATED'},{'MODE' : 'NONE'},{'TYPE' : 'VIDEO'}])         
        #audio library event        
        elif data['method'] == 'AudioLibrary.OnCleanStarted' :
            logging.info('audio library clean started')
            self.calibrary = True
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'CLEAN'},{'TYPE' : 'AUDIO'}])
        elif data['method'] == 'AudioLibrary.OnCleanFinished' :
            logging.info('audio library scan stopeed')
            self.calibrary = False
            self.emit_event('library',[{'ACTION': 'STOP'},{'MODE' : 'CLEAN'},{'TYPE' : 'AUDIO'}])     
        elif data['method'] == 'AudioLibrary.OnScanStarted' :
            logging.info('audio library scan started')
            self.salibrary = True
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'SCAN'},{'TYPE' : 'AUDIO'}])
        elif data['method'] == 'AudioLibrary.OnScanFinished' :
            logging.info('audio library scan stopped')
            self.salibrary = False
            self.emit_event('library',[{'ACTION': 'START'},{'MODE' : 'SCAN'},{'TYPE' : 'AUDIO'}])
        elif data['method'] == 'AudioLibrary.OnUpdate' :
            logging.info('audio library updated')
            self.emit_event('library',[{'ACTION': 'UPDATED'},{'MODE' : 'NONE'},{'TYPE' : 'AUDIO'}])                             
        else :
            change = False

        if change :
            self.library = self.salibrary or self.svlibrary or self.calibrary or self.cvlibrary
            #check for xbmc level
            #level 0 :
            #level 0 will be emitted with a special upstart script
            #level 1 :
            if self.pvr :
                self.emit_event('xbmcplevel',[{'LEVEL':5},{'PREVLEVEL':self.level}])
                self.level = 5
                self.pvr = False
            elif self.screensaver and not self.player and not self.library and self.level != 1 :
                self.emit_event('xbmcplevel',[{'LEVEL':1},{'PREVLEVEL':self.level}])
                self.level = 1
            #level 2 :
            elif self.screensaver and (self.player or self.library) and self.level != 2 :
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

logging.info('Installing signal handler')
signal.siginterrupt(signal.SIGTERM, False)
signal.signal(signal.SIGTERM, main.handleSigTERM)
signal.siginterrupt(signal.SIGINT, False)
signal.signal(signal.SIGINT, main.handleSigTERM)

main.main_loop()
main.onExit()
