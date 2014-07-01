import xbmc
import xbmcaddon

import subprocess

try:
    import simplejson as json
except ImportError:
    import json

__addonname__ = xbmcaddon.Addon().getAddonInfo('name')
del xbmcaddon

NORMAL_LEVEL = 3
EXIT_CODE_FILE = '/run/lock/xbmc.quit'

def log(msg, level=xbmc.LOGNOTICE):
    xbmc.log('%s: %s' % (__addonname__, msg), level)

class UpstartBridge(object):
    def __init__(self):
        self.monitor = XBMCMonitor(self)
        self.player = XBMCPlayer()
        log('started', xbmc.LOGDEBUG)

        # This comes from add-on "XBian Config" (version as of 2014-06-20)
        self._notify_xbmc_loaded()

        self.current_level = self._calculate_priority_level()

    def _calculate_priority_level(self):
        level = NORMAL_LEVEL

        if self.monitor.screensaver:
            level -= 1

        if any(self.monitor.library_statuses.values()):
            level += 1
        elif self.monitor.screensaver:
            level -= 1

        if self.player.isPlaying():
            level += 1
            if self.player.isPlayingLiveTV():
                # Always force 5 when on Live TV
                level += 1
        elif self.monitor.screensaver:
            level -= 1

        # Ensure we return a value between 1 and 5
        level = max(1, min(5, level))
        log('calculated priority: %d, based on monitor.screensaver=%s, monitor.library_statuses=%s, player.isPlaying()=%s, player.isPlayingLiveTV()=%s' % (level, self.monitor.screensaver, self.monitor.library_statuses, self.player.isPlaying(), self.player.isPlayingLiveTV()), xbmc.LOGDEBUG)
        return level

    def emit_event(self, event, env_vars={}, change_level=True):
        emit_cmd = ['sudo', 'initctl', 'emit', '-n', '-q', event]

        # Old versions (the Python script) emitted type=audio for "music"
        if event == 'library' and env_vars['type'] == 'music':
            env_vars['type'] = 'audio'

        if env_vars:
            for key, value in env_vars.items():
                emit_cmd.append('%s=%s' % (key.upper(), str(value).upper()))

        log('emitting Upstart event: %s' % ' '.join(emit_cmd), xbmc.LOGDEBUG)
        try:
            subprocess.check_call(emit_cmd)
        except subprocess.CalledProcessError as e:
            log("the following error occurred while emitting event '%s': %s" % (' '.join(emit_cmd), e), xbmc.LOGERROR)

        if change_level:
            new_level = self._calculate_priority_level()
            if new_level != self.current_level:
                # Ensure we don't produce an infinite loop by passing change_level=False
                self.emit_event('xbmcplevel', {'level': new_level, 'prevlevel': self.current_level}, change_level=False)
                self.current_level = new_level

    def _notify_xbmc_loaded(self):
        start_cmd = ['sudo', 'start', '-n', '-q', 'xbmc-loaded']
        log('notifying Upstart that XBMC has started correctly: %s' % ' '.join(start_cmd), xbmc.LOGDEBUG)
        try:
            subprocess.call(start_cmd)
        except OSError as e:
            log("the following error occurred while executing '%s': %s" % (' '.join(start_cmd), e), xbmc.LOGDEBUG)

    def stop(self, exit_code):
        stop_cmd = ['sudo', 'stop', '-n', '-q', 'xbmc']

        log('saving exit status code (%d) to %s' % (exit_code, EXIT_CODE_FILE), xbmc.LOGDEBUG)
        with open(EXIT_CODE_FILE, 'w') as exit_code_f:
            exit_code_f.write(str(exit_code))

        log('asking Upstart to stop XBMC: %s' % ' '.join(stop_cmd), xbmc.LOGDEBUG)
        try:
            subprocess.call(stop_cmd)
        except OSError as e:
            log("the following error occurred while executing '%s': %s" % (' '.join(stop_cmd), e), xbmc.LOGERROR)

class XBMCMonitor(xbmc.Monitor):
    def __init__(self, upstartbridge_instance):
        xbmc.Monitor.__init__(self)
        self.upstartbridge_instance = upstartbridge_instance

        # Being this a service add-on started on startup, we can quite safely assume that:
        # * the screensaver is not active;
        # * XBMC is not cleaning any library.
        self.screensaver = False
        self.library_statuses = {
            'cleaning_music': False,
            'cleaning_video': False,
            'scanning_music': bool(xbmc.getCondVisibility('Library.IsScanningMusic')),
            'scanning_video': bool(xbmc.getCondVisibility('Library.IsScanningVideo'))
        }

    def onAbortRequested(self): # noqa
        log('got notification for event onAbortRequested', xbmc.LOGDEBUG)
        self.upstartbridge_instance = None

    def onCleanFinished(self, library): # noqa
        log('got notification for event onCleanFinished, library: %s' % library, xbmc.LOGDEBUG)
        self.library_statuses['cleaning_' + library] = False
        self.upstartbridge_instance.emit_event('library', {'action': 'stop', 'mode': 'clean', 'type': library})

    def onCleanStarted(self, library): # noqa
        log('got notification for event onCleanStarted, library: %s' % library, xbmc.LOGDEBUG)
        self.library_statuses['cleaning_' + library] = True
        self.upstartbridge_instance.emit_event('library', {'action': 'start', 'mode': 'clean', 'type': library})

    def onDatabaseScanStarted(self, database): # noqa
        log('got notification for event onDatabaseScanStarted, database: %s' % database, xbmc.LOGDEBUG)
        self.library_statuses['scanning_' + database] = True
        self.upstartbridge_instance.emit_event('library', {'action': 'start', 'mode': 'scan', 'type': database})

    def onDatabaseUpdated(self, database): # noqa
        log('got notification for event onDatabaseUpdated, database: %s' % database, xbmc.LOGDEBUG)
        self.library_statuses['scanning_' + database] = False
        # onDatabaseUpdated gets fired on '{Audio,Video}Library.OnScanFinished', so we emit 2 events here as old
        # versions of this add-on (it was actually a Python script) used the JSON-RPC API, which fired more
        # specific events, though they're actually the same event.
        self.upstartbridge_instance.emit_event('library', {'action': 'stop', 'mode': 'scan', 'type': database})
        self.upstartbridge_instance.emit_event('library', {'action': 'updated', 'mode': 'none', 'type': database}, change_level=False) # We just did with the emit_event above

    def onNotification(self, sender, method, data): # noqa
        if method == 'System.OnQuit':
            exit_code = json.loads(data)
            log('got notification for event System.OnQuit, exit status code: %d' % exit_code, xbmc.LOGDEBUG)
            self.upstartbridge_instance.stop(exit_code)
        # We don't use the onPlayBack* callbacks as to find the "type" we need to call xbmc.getCondVisibility()/xbmc.getInfoLabel()
        # but they sometimes incorrectly return an empty string and/or a wrong boolean value.
        elif method == 'Player.OnPlay': # playback started or resumed
            log('got notification for event Player.OnPlay. player.isPlayingLiveTV() = %s' % self.upstartbridge_instance.player.isPlayingLiveTV(), xbmc.LOGDEBUG)
            self.upstartbridge_instance.emit_event('player', {'action': 'play', 'type': json.loads(data)['item']['type']})
        elif method == 'Player.OnPause':
            log('got notification for event Player.OnPause', xbmc.LOGDEBUG)
            self.upstartbridge_instance.emit_event('player', {'action': 'pause', 'type': json.loads(data)['item']['type']})
        elif method == 'Player.OnStop':
            log('got notification for event Player.OnStop', xbmc.LOGDEBUG)
            self.upstartbridge_instance.emit_event('player', {'action': 'stop', 'type': json.loads(data)['item']['type']})

    def onScreensaverActivated(self): # noqa
        log('got notification for event onScreensaverActivated', xbmc.LOGDEBUG)
        self.screensaver = True
        self.upstartbridge_instance.emit_event('screensaver', {'action': 'start'})

    def onScreensaverDeactivated(self): # noqa
        log('got notification for event onScreensaverDeactivated', xbmc.LOGDEBUG)
        self.screensaver = False
        self.upstartbridge_instance.emit_event('screensaver', {'action': 'stop'})

class XBMCPlayer(xbmc.Player):
    def isPlayingLiveTV(self): # noqa
        if self.isPlaying():
            return self.getPlayingFile().startswith("pvr://")
        else:
            return False

if __name__ == '__main__':
    service = UpstartBridge()
    while not xbmc.abortRequested:
        xbmc.sleep(100)
