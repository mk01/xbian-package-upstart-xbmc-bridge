#!/usr/bin/env python

import socket
import json
import subprocess

TCP_IP = '127.0.0.1'
TCP_PORT = 9090
BUFFER_SIZE = 256

logfilepath = '/run/upstart_xbmc_bridge.log'

logfile = open(logfilepath,'w')

def upstart_emit_event(event,data=None) :
	cmd = ['initctl','emit',event]
	if data :
		print data
		try :
			for key, value in data.items() :
				cmd.append('%s=%s'%(str(key),str(value)))
		except Exception, e:
			logfile.write('ERROR : cannot parse data %s : %s\n'%(str(data),e))
	try :
		subprocess.check_call(cmd)
		logfile.write('DEBUG : %s\n'%str(cmd))
	except Exception, e:
		logfile.write('ERROR : while running %s : %s\n'%(str(cmd),e))
			
logfile.write('NOTICE : starting upstart_xbmc_bridge\n')		
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try :
	s.connect((TCP_IP, TCP_PORT))
	logfile.write('NOTICE : connected to %s:%d\n'%(TCP_IP, TCP_PORT))
except Exception, e:
	logfile.write('Error : cannot connect to %s:%d : %s\n'%(TCP_IP, TCP_PORT,e))
	logfile.close()
	exit -1
			
try :
	while True :
		data = json.loads(s.recv(BUFFER_SIZE))
		#screen saver event
		if data['method'] == 'GUI.OnScreensaverActivated' :
			upstart_emit_event('xbmcscreensaveractivated',{'XBMCSCREENSAVER':True})
		elif data['method'] == 'GUI.OnScreensaverDeactivated' :
			upstart_emit_event('xbmcscreensaverdeactivated',{'XBMCSCREENSAVER':False})	
		#player event
		elif data['method'] == 'Player.OnPlay' :
			upstart_emit_event('xbmcstartplayer',{'XBMCPLAYER':True,'XBMCPLAYERTYPE':str(data['params']['data']['item']['type'])})	
		elif data['method'] == 'Player.OnStop' :
			upstart_emit_event('xbmcstopplayer',{'XBMCPLAYER':False,'XBMCPLAYERTYPE':None})	
		#video library event		
		elif data['method'] == 'VideoLibrary.OnCleanStarted' :
			upstart_emit_event('xbmcvideolibrarycleanstart',{'XBMCVIDEOLIBRARYCLEAN':True})
		elif data['method'] == 'VideoLibrary.OnCleanFinished' :
			upstart_emit_event('xbmcvideolibrarycleanstop',{'XBMCVIDEOLIBRARYCLEAN':False})		
		elif data['method'] == 'VideoLibrary.OnScanStarted' :
			upstart_emit_event('xbmcvideolibrarystart',{'XBMCVIDEOLIBRARYSCAN':True})	
		elif data['method'] == 'VideoLibrary.OnScanFinished' :
			upstart_emit_event('xbmcvideolibrarystop',{'XBMCVIDEOLIBRARYSCAN':False})	
		elif data['method'] == 'VideoLibrary.OnUpdate' :
			upstart_emit_event('xbmcvideodatabaseupdated',{'XBMCDATABASEMODIFIED':True})	
		#audio library event		
		elif data['method'] == 'AudioLibrary.OnCleanStarted' :
			upstart_emit_event('xbmcaudiolibrarycleanstart',{'XBMCAUDIOLIBRARYCLEAN':True})
		elif data['method'] == 'AudioLibrary.OnCleanFinished' :
			upstart_emit_event('xbmcaudiolibrarycleanstop',{'XBMCAUDIOLIBRARYCLEAN':False})		
		elif data['method'] == 'AudioLibrary.OnScanStarted' :
			upstart_emit_event('xbmcaudiolibrarystart',{'XBMCAUDIOLIBRARYSCAN':True})	
		elif data['method'] == 'AudioLibrary.OnScanFinished' :
			upstart_emit_event('xbmcaudiolibrarystop',{'XBMCAUDIOLIBRARYSCAN':False})	
		elif data['method'] == 'AudioLibrary.OnUpdate' :
			upstart_emit_event('xbmcaudiodatabaseupdated',{'XBMCDATABASEMODIFIED':True})									
except Exception, e:
	logfile.write('NOTICE : exit from main loop : %s\n'%e)
finally :
	s.close()
	logfile.close()
